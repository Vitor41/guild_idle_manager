import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_mode: str = os.getenv("APP_MODE", "web").lower()
    active_campaign_id: str | None = os.getenv("ACTIVE_CAMPAIGN_ID")
    database_url: str = (
        "sqlite:///:memory:"
        if os.getenv("APP_MODE", "web").lower() == "desktop"
        else os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@localhost:5432/guild_idle_manager",
        )
    )
    secret_key: str = os.getenv("SECRET_KEY", "change-this-secret")
    app_env: str = os.getenv("APP_ENV", "local")
    github_releases_owner: str | None = os.getenv("GIM_GITHUB_RELEASES_OWNER")
    github_releases_repo: str | None = os.getenv("GIM_GITHUB_RELEASES_REPO")
    github_releases_channel: str | None = os.getenv("GIM_GITHUB_RELEASES_CHANNEL")
    github_releases_public_key: str | None = os.getenv("GIM_GITHUB_RELEASES_PUBLIC_KEY")
    github_releases_manifest_asset: str = os.getenv(
        "GIM_GITHUB_RELEASES_MANIFEST_ASSET", "gim-release.json"
    )
    debug: bool = os.getenv("DEBUG", "true").lower() in {"1", "true", "yes", "on"}
    session_global_seconds: int = int(os.getenv("SESSION_GLOBAL_SECONDS", "18000"))
    session_idle_seconds: int = int(os.getenv("SESSION_IDLE_SECONDS", "3600"))


settings = Settings()
