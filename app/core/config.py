import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/guild_idle_manager",
    )
    secret_key: str = os.getenv("SECRET_KEY", "change-this-secret")
    app_env: str = os.getenv("APP_ENV", "local")
    debug: bool = os.getenv("DEBUG", "true").lower() in {"1", "true", "yes", "on"}
    session_global_seconds: int = int(os.getenv("SESSION_GLOBAL_SECONDS", "18000"))
    session_idle_seconds: int = int(os.getenv("SESSION_IDLE_SECONDS", "3600"))


settings = Settings()
