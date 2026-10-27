"""Campaign save discovery, creation, validation, and activation."""

from dataclasses import dataclass
from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from alembic.script import Script, ScriptDirectory
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.database.connection import SessionLocal, configure_database, create_database_engine
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


def default_saves_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("LOCALAPPDATA nao esta definido; informe o diretorio de saves explicitamente.")
    return Path(local_app_data) / "GuildIdleManager" / "saves"


class CampaignService:
    def __init__(self, saves_directory: str | Path | None = None):
        self.saves_directory = Path(saves_directory) if saves_directory else default_saves_directory()

    def _path_for(self, campaign_id: str) -> Path:
        try:
            canonical_id = str(UUID(campaign_id))
        except (ValueError, AttributeError) as exc:
            raise ValueError("Identificador de campanha invalido.") from exc
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

    def _ensure_schema(self, database_path: Path, campaign_id: str) -> None:
        config = self._alembic_config(database_path)
        script = ScriptDirectory.from_config(config)
        head = script.get_current_head()
        if head is None:
            raise RuntimeError("A cadeia Alembic local nao possui uma revisao head.")
        with closing(sqlite3.connect(database_path)) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not tables:
                current = "__empty__"
            elif "alembic_version" not in tables:
                raise ValueError("Save sem revisao Alembic; arquivo preservado e nao migrado.")
            else:
                try:
                    revisions = [row[0] for row in connection.execute("SELECT version_num FROM alembic_version")]
                except sqlite3.DatabaseError as exc:
                    raise ValueError("Tabela de revisao Alembic invalida; arquivo preservado.") from exc
                if len(revisions) != 1 or not revisions[0]:
                    raise ValueError("Save sem uma revisao Alembic valida; arquivo preservado.")
                current = revisions[0]
        if current == "__empty__":
            command.upgrade(config, head)
            return
        self._validate_revision_ancestry(script, current, head)
        if current != head:
            self._backup_before_schema_change(database_path, campaign_id, current)
            command.upgrade(config, head)
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "UPDATE campaign_metadata SET schema_version = ? WHERE campaign_id = ?",
                    (CURRENT_SCHEMA_VERSION, campaign_id),
                )
                connection.commit()

    @staticmethod
    def _validate_revision_ancestry(script: ScriptDirectory, current: str, head: str) -> None:
        try:
            current_script = script.get_revision(current)
        except Exception as exc:
            raise ValueError(f"Save usa revisao Alembic desconhecida ({current}); arquivo preservado.") from exc
        if current_script is None:
            raise ValueError(f"Save usa revisao Alembic desconhecida ({current}); arquivo preservado.")
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
                f"Revisao Alembic do save ({current}) nao pertence a cadeia suportada; arquivo preservado."
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
        engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
        try:
            self._ensure_schema(database_path, campaign_id)
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            with factory() as db:
                metadata = CampaignMetadata(
                    campaign_id=campaign_id,
                    campaign_name=name,
                    schema_version=CURRENT_SCHEMA_VERSION,
                    content_version=0,
                    last_session_state="initializing",
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
                metadata.last_session_state = "active"
                metadata.updated_at_utc = datetime.now(timezone.utc)
                db.commit()
                return self._to_info(metadata, database_path)
        except Exception:
            engine.dispose()
            for suffix in ("", "-wal", "-shm"):
                candidate = Path(f"{database_path}{suffix}")
                if candidate.exists():
                    candidate.unlink()
            raise
        finally:
            engine.dispose()

    def inspect_campaign(self, campaign_id: str) -> CampaignInfo:
        path = self._path_for(campaign_id)
        if not path.is_file():
            raise FileNotFoundError("Save da campanha nao encontrado.")
        with closing(sqlite3.connect(path)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise ValueError("O save da campanha esta corrompido.")
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "campaign_metadata" not in tables:
                raise ValueError("O arquivo nao e um save de campanha reconhecido.")
            if "alembic_version" not in tables:
                raise ValueError("Save sem revisao Alembic; arquivo preservado e nao migrado.")
            config = self._alembic_config(path)
            script = ScriptDirectory.from_config(config)
            head = script.get_current_head()
            revision_rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
            if not head or len(revision_rows) != 1 or not revision_rows[0][0]:
                raise ValueError("Save sem uma revisao Alembic valida; arquivo preservado.")
            self._validate_revision_ancestry(script, revision_rows[0][0], head)
        engine = create_database_engine(f"sqlite:///{path.as_posix()}")
        try:
            factory = sessionmaker(bind=engine, expire_on_commit=False)
            with factory() as db:
                metadata = db.get(CampaignMetadata, str(UUID(campaign_id)))
                if metadata is None or metadata.save_format_version != 1:
                    raise ValueError("Formato do save da campanha nao suportado.")
                if metadata.schema_version > CURRENT_SCHEMA_VERSION:
                    raise ValueError("O save foi criado por uma versao mais recente do aplicativo.")
                return self._to_info(metadata, path)
        finally:
            engine.dispose()

    def list_campaigns(self) -> list[CampaignInfo]:
        if not self.saves_directory.exists():
            return []
        result = []
        for path in sorted(self.saves_directory.glob("*.db")):
            try:
                campaign_id = str(UUID(path.stem))
                result.append(self.inspect_campaign(campaign_id))
            except (ValueError, sqlite3.DatabaseError, SQLAlchemyError, OSError):
                continue
        return result

    def activate_campaign(self, campaign_id: str) -> CampaignInfo:
        path = self._path_for(campaign_id)
        if not path.is_file():
            raise FileNotFoundError("Save da campanha nao encontrado.")
        self._ensure_schema(path, str(UUID(campaign_id)))
        info = self.inspect_campaign(campaign_id)
        with _activation_lock:
            configure_database(f"sqlite:///{info.database_path.as_posix()}")
            with SessionLocal() as db:
                metadata = db.get(CampaignMetadata, info.campaign_id)
                if metadata is None:
                    raise ValueError("O save desapareceu durante a abertura.")
                metadata.last_session_state = "active"
                metadata.updated_at_utc = datetime.now(timezone.utc)
                db.commit()
        return info

    def close_active_campaign(self, campaign_id: str) -> None:
        with _activation_lock:
            with SessionLocal() as db:
                metadata = db.get(CampaignMetadata, str(UUID(campaign_id)))
                if metadata is None:
                    raise FileNotFoundError("Save da campanha ativa nao encontrado.")
                now = datetime.now(timezone.utc)
                metadata.last_clean_shutdown_utc = now
                metadata.last_session_state = "closed"
                metadata.updated_at_utc = now
                db.commit()
            configure_database("sqlite:///:memory:")

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
