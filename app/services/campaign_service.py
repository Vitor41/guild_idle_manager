"""Campaign save discovery, creation, validation, and activation."""

from dataclasses import dataclass
from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import shutil
from threading import RLock
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from alembic.script import Script, ScriptDirectory
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.database.connection import SessionLocal, configure_database, create_database_engine, get_engine
from app.models import CampaignMetadata, Guild, GuildResources


CURRENT_SCHEMA_VERSION = 2
INITIAL_CONTENT_VERSION = 1
_activation_lock = RLock()


@dataclass(frozen=True)
class CampaignInfo:
    campaign_id: str
    campaign_name: str
    database_path: Path
    created_at_utc: datetime
    updated_at_utc: datetime
    content_version: int
    schema_version: int
    last_clean_shutdown_utc: datetime | None = None
    last_session_state: str = "created"
    tutorial_status: str = "pending"
    confirmation_preferences: str = "{}"


@dataclass(frozen=True)
class CampaignMigration:
    previous_revision: str
    current_revision: str
    previous_save_version: int
    current_save_version: int
    backup_created: bool = True

    def notice_payload(self) -> dict[str, object]:
        return {
            "previous_revision": self.previous_revision,
            "current_revision": self.current_revision,
            "previous_save_version": self.previous_save_version,
            "current_save_version": self.current_save_version,
            "backup_created": self.backup_created,
        }


class CampaignListing(list):
    """Valid campaigns plus visible recovery entries for detected save files."""

    def __init__(self):
        super().__init__()
        self.unavailable: list[dict[str, str]] = []


def default_saves_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("A pasta de dados local não está disponível. Não foi possível localizar as campanhas.")
    return Path(local_app_data) / "GuildIdleManager" / "saves"


class CampaignService:
    def __init__(self, saves_directory: str | Path | None = None):
        self.saves_directory = Path(saves_directory) if saves_directory else default_saves_directory()

    def _path_for(self, campaign_id: str) -> Path:
        try:
            canonical_id = str(UUID(campaign_id))
        except (ValueError, AttributeError) as exc:
            raise ValueError("O identificador da campanha é inválido.") from exc
        return self.saves_directory / f"{canonical_id}.db"

    def _alembic_config(self, database_path: Path) -> Config:
        project_root = Path(__file__).resolve().parents[2]
        config = Config(str(project_root / "alembic.ini"))
        config.set_main_option("script_location", str(project_root / "alembic"))
        database_url = f"sqlite:///{database_path.resolve().as_posix()}"
        config.attributes["database_url"] = database_url
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
        return config

    def _backup_before_schema_change(self, database_path: Path, campaign_id: str, revision: str) -> Path:
        backup_dir = self.saves_directory.parent / "backups" / campaign_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        backup_path = backup_dir / f"pre-migration-{revision}-{timestamp}.db"
        with closing(sqlite3.connect(database_path)) as source, closing(sqlite3.connect(backup_path)) as destination:
            source.backup(destination)
        backups = sorted(backup_dir.glob("pre-migration-*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
        for stale_backup in backups[3:]:
            stale_backup.unlink()
        return backup_path

    @staticmethod
    def _restore_sqlite_backup(backup_path: Path, database_path: Path) -> None:
        with closing(sqlite3.connect(backup_path)) as source, closing(sqlite3.connect(database_path)) as destination:
            destination.execute("PRAGMA foreign_keys=OFF")
            source.backup(destination)
            destination.commit()

    @staticmethod
    def _assert_outside_checkout(path: Path) -> Path:
        target = path.expanduser().resolve()
        checkout = Path(__file__).resolve().parents[2]
        if target == checkout or checkout in target.parents:
            raise ValueError("Os arquivos da campanha, cópias de segurança e exportações devem ficar fora da pasta do aplicativo.")
        return target

    def _ensure_schema(self, database_path: Path, campaign_id: str) -> CampaignMigration | None:
        config = self._alembic_config(database_path)
        script = ScriptDirectory.from_config(config)
        head = script.get_current_head()
        if head is None:
            raise RuntimeError("Não foi possível verificar a versão dos dados da campanha.")
        if not database_path.exists():
            command.upgrade(config, head)
            return None
        with closing(sqlite3.connect(database_path)) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not tables:
                raise ValueError("O arquivo da campanha está vazio; ele foi preservado e não foi alterado.")
            elif "alembic_version" not in tables:
                raise ValueError("O arquivo da campanha não tem uma versão reconhecida; ele foi preservado e não foi alterado.")
            else:
                try:
                    revisions = [row[0] for row in connection.execute("SELECT version_num FROM alembic_version")]
                except sqlite3.DatabaseError as exc:
                    raise ValueError("Não foi possível ler a versão do arquivo da campanha; ele foi preservado.") from exc
                if len(revisions) != 1 or not revisions[0]:
                    raise ValueError("O arquivo da campanha não tem uma versão válida; ele foi preservado.")
                current = revisions[0]
                has_campaign_metadata = "campaign_metadata" in tables
                previous_save_version = CURRENT_SCHEMA_VERSION
                if has_campaign_metadata:
                    row = connection.execute(
                        "SELECT schema_version FROM campaign_metadata WHERE campaign_id = ?",
                        (campaign_id,),
                    ).fetchone()
                    if row is None:
                        raise ValueError("Os dados de identificação da campanha estão ausentes; o arquivo foi preservado.")
                    previous_save_version = int(row[0])
        self._validate_revision_ancestry(script, current, head)
        if current != head or previous_save_version != CURRENT_SCHEMA_VERSION:
            backup_path = self._backup_before_schema_change(database_path, campaign_id, current)
            try:
                if current != head:
                    command.upgrade(config, head)
                if has_campaign_metadata:
                    with closing(sqlite3.connect(database_path)) as connection:
                        connection.execute(
                            "UPDATE campaign_metadata SET schema_version = ? WHERE campaign_id = ?",
                            (CURRENT_SCHEMA_VERSION, campaign_id),
                        )
                        connection.commit()
            except Exception as migration_error:
                try:
                    self._restore_sqlite_backup(backup_path, database_path)
                except Exception as restore_error:
                    raise RuntimeError(
                        f"A atualização falhou e não foi possível restaurar os dados automaticamente. "
                        f"Preserve o arquivo da campanha e use esta cópia de segurança para recuperá-lo: {backup_path}"
                    ) from restore_error
                raise RuntimeError(
                    f"A atualização dos dados da campanha falhou. O arquivo original foi restaurado; "
                    f"cópia de segurança para recuperação: {backup_path}"
                ) from migration_error
            return CampaignMigration(
                previous_revision=current,
                current_revision=head,
                previous_save_version=previous_save_version,
                current_save_version=CURRENT_SCHEMA_VERSION,
            )
        return None

    def _validate_campaign_before_open(self, database_path: Path, campaign_id: str) -> None:
        """Validate an existing save completely before any migration can modify it."""
        with closing(sqlite3.connect(database_path)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise ValueError("O arquivo da campanha está corrompido; ele foi preservado.")
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if "campaign_metadata" not in tables:
                raise ValueError("O arquivo selecionado não é uma campanha reconhecida; ele foi preservado.")
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(campaign_metadata)")
            }
            required = {"campaign_id", "save_format_version", "schema_version"}
            if not required.issubset(columns):
                raise ValueError("Os dados da campanha estão incompletos; o arquivo foi preservado e não foi alterado.")
            rows = connection.execute(
                "SELECT campaign_id, save_format_version, schema_version FROM campaign_metadata"
            ).fetchall()
            if len(rows) != 1 or rows[0][0] != campaign_id:
                raise ValueError("O identificador da campanha não corresponde ao arquivo selecionado.")
            if rows[0][1] != 1:
                raise ValueError("Este formato de campanha não é compatível com o aplicativo; o arquivo foi preservado.")
            if rows[0][2] > CURRENT_SCHEMA_VERSION:
                raise ValueError("A campanha foi criada por uma versão mais recente do aplicativo.")
            if "alembic_version" not in tables:
                raise ValueError("O arquivo da campanha não tem uma versão reconhecida; ele foi preservado e não foi alterado.")
            revision_rows = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchall()
            if len(revision_rows) != 1 or not revision_rows[0][0]:
                raise ValueError("O arquivo da campanha não tem uma versão válida; ele foi preservado.")
            config = self._alembic_config(database_path)
            script = ScriptDirectory.from_config(config)
            head = script.get_current_head()
            if head is None:
                raise RuntimeError("Não foi possível verificar a versão dos dados da campanha.")
            self._validate_revision_ancestry(script, revision_rows[0][0], head)

    @staticmethod
    def _validate_revision_ancestry(script: ScriptDirectory, current: str, head: str) -> None:
        try:
            current_script = script.get_revision(current)
        except Exception as exc:
            raise ValueError(f"O arquivo da campanha tem uma versão desconhecida ({current}); ele foi preservado.") from exc
        if current_script is None:
            raise ValueError(f"O arquivo da campanha tem uma versão desconhecida ({current}); ele foi preservado.")
        ancestors = set()
        pending = [head]
        while pending:
            revision_id = pending.pop()
            if revision_id in ancestors:
                continue
            ancestors.add(revision_id)
            revision = script.get_revision(revision_id)
            if revision is not None:
                down_revisions = revision.down_revision
                if down_revisions:
                    pending.extend(down_revisions if isinstance(down_revisions, tuple) else (down_revisions,))
        if current not in ancestors:
            raise ValueError(
                f"A versão dos dados da campanha ({current}) não é compatível com este aplicativo; o arquivo foi preservado."
            )

    def create_campaign(self, campaign_name: str, guild_name: str | None = None) -> CampaignInfo:
        name = campaign_name.strip()
        guild_name = (guild_name or name).strip()
        if not name or len(name) > 120:
            raise ValueError("O nome da campanha deve ter entre 1 e 120 caracteres.")
        if not guild_name or len(guild_name) > 120:
            raise ValueError("O nome da guilda deve ter entre 1 e 120 caracteres.")

        campaign_id = str(uuid4())
        self.saves_directory.mkdir(parents=True, exist_ok=True)
        database_path = self._path_for(campaign_id)
        engine = None
        try:
            self._ensure_schema(database_path, campaign_id)
            engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            with factory() as db:
                metadata = CampaignMetadata(
                    campaign_id=campaign_id,
                    campaign_name=name,
                    schema_version=CURRENT_SCHEMA_VERSION,
                    content_version=0,
                    last_session_state="created",
                )
                db.add(metadata)
                db.flush()
                guild = Guild(campaign_id=campaign_id, name=guild_name, level=1, reputation=0)
                db.add(guild)
                db.flush()
                db.add(GuildResources(guild_id=guild.id, gold=100, wood=0, ore=0, crystals=0))
                db.commit()

                from app.seeds.campaign_content import apply_initial_campaign_content

                apply_initial_campaign_content(db)
                metadata.content_version = INITIAL_CONTENT_VERSION
                metadata.updated_at_utc = datetime.now(timezone.utc)
                db.commit()
                return self._to_info(metadata, database_path)
        except Exception:
            if engine is not None:
                engine.dispose()
            for suffix in ("", "-wal", "-shm"):
                candidate = Path(f"{database_path}{suffix}")
                if candidate.exists():
                    candidate.unlink()
            raise
        finally:
            if engine is not None:
                engine.dispose()

    def inspect_campaign(self, campaign_id: str) -> CampaignInfo:
        path = self._path_for(campaign_id)
        if not path.is_file():
            raise FileNotFoundError("Arquivo da campanha não encontrado.")
        with closing(sqlite3.connect(path)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise ValueError("O arquivo da campanha está corrompido.")
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "campaign_metadata" not in tables:
                raise ValueError("O arquivo selecionado não é uma campanha reconhecida.")
            if "alembic_version" not in tables:
                raise ValueError("O arquivo da campanha não tem uma versão reconhecida; ele foi preservado e não foi alterado.")
            config = self._alembic_config(path)
            script = ScriptDirectory.from_config(config)
            head = script.get_current_head()
            revision_rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
            if not head or len(revision_rows) != 1 or not revision_rows[0][0]:
                raise ValueError("O arquivo da campanha não tem uma versão válida; ele foi preservado.")
            self._validate_revision_ancestry(script, revision_rows[0][0], head)
        engine = create_database_engine(f"sqlite:///{path.as_posix()}")
        try:
            factory = sessionmaker(bind=engine, expire_on_commit=False)
            with factory() as db:
                metadata = db.get(CampaignMetadata, str(UUID(campaign_id)))
                if metadata is None or metadata.save_format_version != 1:
                    raise ValueError("Este formato de campanha não é compatível com o aplicativo.")
                if metadata.schema_version > CURRENT_SCHEMA_VERSION:
                    raise ValueError("A campanha foi criada por uma versão mais recente do aplicativo.")
                return self._to_info(metadata, path)
        finally:
            engine.dispose()

    def list_campaigns(self) -> list[CampaignInfo]:
        if not self.saves_directory.exists():
            return CampaignListing()
        result = CampaignListing()
        for path in sorted(self.saves_directory.glob("*.db")):
            try:
                campaign_id = str(UUID(path.stem))
                result.append(self.inspect_campaign(campaign_id))
            except (ValueError, sqlite3.DatabaseError, SQLAlchemyError, OSError) as exc:
                if isinstance(exc, sqlite3.DatabaseError):
                    reason = "O arquivo está corrompido ou não é um banco SQLite válido."
                elif isinstance(exc, SQLAlchemyError):
                    reason = "Não foi possível verificar os dados da campanha. O arquivo foi preservado; tente restaurar uma cópia de segurança compatível."
                else:
                    reason = str(exc).strip() or "O arquivo não pôde ser validado."
                try:
                    recovery_id = str(UUID(path.stem))
                except ValueError:
                    recovery_id = ""
                result.unavailable.append({"filename": path.name, "campaign_id": recovery_id, "reason": reason[:240]})
        return result

    def rename_campaign(self, campaign_id: str, campaign_name: str) -> CampaignInfo:
        name = campaign_name.strip()
        if not name or len(name) > 120:
            raise ValueError("O nome da campanha deve ter entre 1 e 120 caracteres.")
        info = self.inspect_campaign(campaign_id)
        with closing(sqlite3.connect(info.database_path)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE campaign_metadata SET campaign_name = ?, updated_at_utc = CURRENT_TIMESTAMP WHERE campaign_id = ?",
                (name, info.campaign_id),
            )
            connection.commit()
        return self.inspect_campaign(campaign_id)

    def create_manual_backup(self, campaign_id: str) -> Path:
        info = self.inspect_campaign(campaign_id)
        with closing(sqlite3.connect(info.database_path)) as connection:
            revision_row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        revision = revision_row[0] if revision_row else "unknown"
        return self._backup_before_schema_change(info.database_path, info.campaign_id, f"manual-{revision}")

    def restore_backup(self, campaign_id: str, backup_path: str | Path) -> CampaignInfo:
        database_path = self._path_for(campaign_id)
        if not database_path.is_file():
            raise FileNotFoundError("Arquivo da campanha não encontrado.")
        engine_database = get_engine().url.database
        if engine_database and Path(engine_database).resolve() == database_path.resolve():
            raise ValueError("Feche a campanha antes de restaurar uma cópia de segurança.")
        source_path = Path(backup_path).expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError("A cópia de segurança selecionada não foi encontrada.")
        canonical_id = str(UUID(campaign_id))
        self._validate_campaign_before_open(source_path, canonical_id)
        diagnostic_dir = self.saves_directory.parent / "backups" / canonical_id
        diagnostic_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        diagnostic_path = diagnostic_dir / f"pre-restore-{timestamp}.db"
        shutil.copy2(database_path, diagnostic_path)
        sidecars: list[tuple[Path, Path]] = []
        for suffix in ("-wal", "-shm"):
            original_sidecar = Path(f"{database_path}{suffix}")
            if original_sidecar.exists():
                shutil.copy2(original_sidecar, Path(f"{diagnostic_path}{suffix}"))
                parked_sidecar = Path(f"{database_path}.restore-old{suffix}")
                sidecars.append((original_sidecar, parked_sidecar))
        staged_path = database_path.with_suffix(".restore.tmp")
        try:
            self._restore_sqlite_backup(source_path, staged_path)
            parked: list[tuple[Path, Path]] = []
            try:
                for original_sidecar, parked_sidecar in sidecars:
                    os.replace(original_sidecar, parked_sidecar)
                    parked.append((original_sidecar, parked_sidecar))
                os.replace(staged_path, database_path)
            except Exception:
                for original_sidecar, parked_sidecar in reversed(parked):
                    if parked_sidecar.exists():
                        os.replace(parked_sidecar, original_sidecar)
                raise
            else:
                for _original_sidecar, parked_sidecar in parked:
                    parked_sidecar.unlink(missing_ok=True)
        finally:
            staged_path.unlink(missing_ok=True)
        return self.inspect_campaign(campaign_id)

    def delete_campaign(self, campaign_id: str, active_campaign_id: str | None = None) -> Path:
        info = self.inspect_campaign(campaign_id)
        if active_campaign_id and info.campaign_id == str(UUID(active_campaign_id)):
            raise ValueError("Feche a campanha antes de excluí-la.")
        engine_database = get_engine().url.database
        if engine_database and Path(engine_database).resolve() == info.database_path.resolve():
            raise ValueError("Feche a campanha antes de excluí-la.")
        backup_path = self.create_manual_backup(info.campaign_id)
        info.database_path.unlink()
        for suffix in ("-wal", "-shm"):
            Path(f"{info.database_path}{suffix}").unlink(missing_ok=True)
        return backup_path

    def export_campaign(
        self, campaign_id: str, destination: str | Path, overwrite: bool = False
    ) -> Path:
        info = self.inspect_campaign(campaign_id)
        target = self._assert_outside_checkout(Path(destination))
        if target == info.database_path.resolve():
            raise ValueError("Escolha um arquivo diferente do arquivo original da campanha.")
        if target.exists() and not overwrite:
            raise FileExistsError("Já existe um arquivo neste local. Confirme a substituição antes de continuar.")
        target.parent.mkdir(parents=True, exist_ok=True)
        staged_path = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            self._restore_sqlite_backup(info.database_path, staged_path)
            with closing(sqlite3.connect(staged_path)) as connection:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()
                if not integrity or integrity[0] != "ok":
                    raise ValueError("Não foi possível verificar a integridade do arquivo exportado.")
            staged_path.replace(target)
            return target
        finally:
            staged_path.unlink(missing_ok=True)

    def import_campaign(self, source: str | Path) -> CampaignInfo:
        source_path = Path(source).expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError("Arquivo da campanha não encontrado.")
        self._assert_outside_checkout(source_path)
        with closing(sqlite3.connect(source_path)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise ValueError("O arquivo selecionado está corrompido.")
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "campaign_metadata" not in tables:
                raise ValueError("O arquivo selecionado não contém uma campanha reconhecida.")
            rows = connection.execute("SELECT campaign_id FROM campaign_metadata").fetchall()
            if len(rows) != 1 or not rows[0][0]:
                raise ValueError("O arquivo selecionado não contém dados válidos da campanha.")
            source_campaign_id = str(UUID(rows[0][0]))
        self._validate_campaign_before_open(source_path, source_campaign_id)

        self.saves_directory.mkdir(parents=True, exist_ok=True)
        campaign_id = str(uuid4())
        final_path = self._path_for(campaign_id)
        staged_path = final_path.with_suffix(".import.tmp")
        try:
            self._restore_sqlite_backup(source_path, staged_path)
            with closing(sqlite3.connect(staged_path)) as connection:
                connection.execute("PRAGMA foreign_keys=OFF")
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE campaign_metadata "
                    "SET campaign_id = ?, last_session_state = 'created', last_clean_shutdown_utc = NULL "
                    "WHERE campaign_id = ?",
                    (campaign_id, source_campaign_id),
                )
                connection.execute(
                    "UPDATE guilds SET campaign_id = ? WHERE campaign_id = ?",
                    (campaign_id, source_campaign_id),
                )
                connection.commit()
                violations = connection.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise ValueError("A campanha importada contém dados relacionados inválidos. Tente exportá-la novamente a partir do aplicativo.")
            self._validate_campaign_before_open(staged_path, campaign_id)
            staged_path.replace(final_path)
        finally:
            staged_path.unlink(missing_ok=True)
        return self.inspect_campaign(campaign_id)

    def activate_campaign(self, campaign_id: str, mark_active: bool = True) -> CampaignInfo:
        info, _migration = self.activate_campaign_with_migration(campaign_id, mark_active)
        return info

    def activate_campaign_with_migration(
        self, campaign_id: str, mark_active: bool = True
    ) -> tuple[CampaignInfo, CampaignMigration | None]:
        path = self._path_for(campaign_id)
        if not path.is_file():
            raise FileNotFoundError("Arquivo da campanha não encontrado.")
        self._validate_campaign_before_open(path, str(UUID(campaign_id)))
        migration = self._ensure_schema(path, str(UUID(campaign_id)))
        info = self.inspect_campaign(campaign_id)
        with _activation_lock:
            configure_database(f"sqlite:///{info.database_path.as_posix()}")
            if mark_active:
                with SessionLocal() as db:
                    metadata = db.get(CampaignMetadata, info.campaign_id)
                    if metadata is None:
                        raise ValueError("O arquivo da campanha não foi encontrado durante a abertura.")
                    metadata.last_session_state = "active"
                    metadata.updated_at_utc = datetime.now(timezone.utc)
                    db.commit()
        return info, migration

    def close_active_campaign(self, campaign_id: str, closed_at_utc: datetime | None = None) -> None:
        with _activation_lock:
            with SessionLocal() as db:
                metadata = db.get(CampaignMetadata, str(UUID(campaign_id)))
                if metadata is None:
                    raise FileNotFoundError("Arquivo da campanha ativa não encontrado.")
                now = closed_at_utc or datetime.now(timezone.utc)
                metadata.last_clean_shutdown_utc = now
                metadata.last_session_state = "closed"
                metadata.updated_at_utc = now
                db.commit()
            configure_database("sqlite:///:memory:")

    def suspend_active_campaign(self, campaign_id: str) -> None:
        with _activation_lock:
            with SessionLocal() as db:
                metadata = db.get(CampaignMetadata, str(UUID(campaign_id)))
                if metadata is None:
                    raise FileNotFoundError("Arquivo da campanha ativa não encontrado.")
                metadata.last_session_state = "suspended"
                metadata.last_clean_shutdown_utc = None
                metadata.updated_at_utc = datetime.now(timezone.utc)
                db.commit()
            configure_database("sqlite:///:memory:")

    def mark_campaign_closed(self, campaign_id: str, closed_at_utc: datetime) -> None:
        path = self._path_for(campaign_id)
        self._validate_campaign_before_open(path, str(UUID(campaign_id)))
        now = closed_at_utc.astimezone(timezone.utc)
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE campaign_metadata SET last_clean_shutdown_utc = ?, last_session_state = 'closed', "
                "updated_at_utc = ? WHERE campaign_id = ?",
                (now.isoformat(), now.isoformat(), str(UUID(campaign_id))),
            )
            connection.commit()

    @staticmethod
    def _to_info(metadata: CampaignMetadata, path: Path) -> CampaignInfo:
        return CampaignInfo(
            campaign_id=metadata.campaign_id,
            campaign_name=metadata.campaign_name,
            database_path=path,
            created_at_utc=metadata.created_at_utc,
            updated_at_utc=metadata.updated_at_utc,
            content_version=metadata.content_version,
            schema_version=metadata.schema_version,
            last_clean_shutdown_utc=metadata.last_clean_shutdown_utc,
            last_session_state=metadata.last_session_state,
            tutorial_status=metadata.tutorial_status,
            confirmation_preferences=metadata.confirmation_preferences,
        )
