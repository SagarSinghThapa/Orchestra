from typing import Generator
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings


engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def normalize_database_url(url: str) -> str:
    """
    Normalizes generic PostgreSQL connection strings to explicitly use the psycopg (psycopg3) dialect.
    Preserves other dialects (e.g. SQLite for tests or mock engines).
    """
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def dispose_engine() -> None:
    """
    Safely disposes of the connection pool upon application shutdown.
    """
    global engine
    if engine is not None:
        engine.dispose()


if settings.database_url:
    target_url = normalize_database_url(settings.database_url)
    engine_kwargs: dict = {
        "pool_pre_ping": True,
    }

    # QueuePool parameters are applied to relational servers (e.g. PostgreSQL)
    if not target_url.startswith("sqlite"):
        engine_kwargs.update(
            {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_timeout": settings.db_pool_timeout,
                "pool_recycle": settings.db_pool_recycle,
            }
        )

    engine = create_engine(
        target_url,
        **engine_kwargs,
    )
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        settings.validate_runtime_requirements()
        raise RuntimeError("Database engine not initialized: DATABASE_URL is not set.")

    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()