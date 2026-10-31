import os
import sys
from pathlib import Path

# Add backend directory to path
repo_root = Path(__file__).resolve().parent.parent.parent.parent
backend_dir = repo_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.password import hash_password
from app.database.base import Base
import app.models  # Ensures all ORM models are registered
from app.models.user import User, UserRole


def bootstrap():
    env = os.environ.get("ENVIRONMENT", "test")
    assert env == "test", f"Refusing to bootstrap: ENVIRONMENT is '{env}', expected 'test'"

    db_path = repo_root / "test-results" / "orchestra_e2e.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db_url = os.environ.get("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    assert "test" in db_url.lower() or "sqlite" in db_url.lower(), (
        f"Refusing to bootstrap: DATABASE_URL '{db_url}' is not a test database"
    )

    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args)

    # Drop and recreate schema
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # LangGraph checkpoint tables (managed outside Base.metadata)
    with engine.begin() as conn:
        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id VARCHAR(255) NOT NULL,
            checkpoint_ns VARCHAR(255) NOT NULL DEFAULT '',
            checkpoint_id VARCHAR(255) NOT NULL,
            parent_checkpoint_id VARCHAR(255),
            type VARCHAR(100),
            checkpoint TEXT NOT NULL,
            metadata TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
        );
        """)
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_checkpoints_thread_id ON checkpoints (thread_id);")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_checkpoints_created_at ON checkpoints (created_at);")

        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS checkpoint_writes (
            thread_id VARCHAR(255) NOT NULL,
            checkpoint_ns VARCHAR(255) NOT NULL DEFAULT '',
            checkpoint_id VARCHAR(255) NOT NULL,
            task_id VARCHAR(255) NOT NULL,
            idx INTEGER NOT NULL,
            channel VARCHAR(255) NOT NULL,
            type VARCHAR(100),
            value TEXT NOT NULL,
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
        );
        """)
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_checkpoint_writes_thread_id ON checkpoint_writes (thread_id);")

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        # Seed deterministic test personas
        hashed_pwd = hash_password("TestPassword123!")

        admin = User(
            email="admin@orchestra.io",
            password_hash=hashed_pwd,
            role=UserRole.ADMIN,
        )
        member = User(
            email="member@orchestra.io",
            password_hash=hashed_pwd,
            role=UserRole.MEMBER,
        )
        viewer = User(
            email="viewer@orchestra.io",
            password_hash=hashed_pwd,
            role=UserRole.VIEWER,
        )

        session.add_all([admin, member, viewer])
        session.commit()
        print("Bootstrap test database SUCCESS: seeded admin, member, viewer personas.")
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    bootstrap()
