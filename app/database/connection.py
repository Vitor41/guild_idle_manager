from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


def create_database_engine(database_url: str):
    if database_url.startswith("sqlite"):
        sqlite_engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )

        @event.listens_for(sqlite_engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return sqlite_engine
    return create_engine(database_url, pool_pre_ping=True)


engine = create_database_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def configure_database(database_url: str) -> None:
    """Rebind the request session factory to the selected campaign database."""
    global engine
    previous = engine
    engine = create_database_engine(database_url)
    SessionLocal.configure(bind=engine)
    previous.dispose()


def get_engine():
    return engine


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

