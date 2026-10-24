from typing import Generator
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings


engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None

if settings.database_url:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
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
    finally:
        db.close()