"""Campaign save discovery, creation, validation, and activation."""

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database.connection import Base, SessionLocal, configure_database, create_database_engine
from app.models import CampaignMetadata, Guild, GuildResources


CURRENT_SCHEMA_VERSION = 1
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
            Base.metadata.create_all(engine)
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
        with sqlite3.connect(path) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise ValueError("O save da campanha esta corrompido.")
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "campaign_metadata" not in tables:
                raise ValueError("O arquivo nao e um save de campanha reconhecido.")
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
            except (ValueError, sqlite3.DatabaseError, OSError):
                continue
        return result

    def activate_campaign(self, campaign_id: str) -> CampaignInfo:
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
            tutorial_status=metadata.tutorial_status,
            confirmation_preferences=metadata.confirmation_preferences,
        )
