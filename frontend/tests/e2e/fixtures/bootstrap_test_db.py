import os
import sys
from pathlib import Path


def find_repo_root() -> Path:
    curr = Path(__file__).resolve().parent
    for _ in range(6):
        if (curr / "backend").is_dir() and (curr / "frontend").is_dir():
            return curr
        curr = curr.parent
    return Path(__file__).resolve().parents[4]


repo_root = find_repo_root()
backend_dir = repo_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.password import hash_password
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

    # 1. Reset test database file if using sqlite file
    if db_url.startswith("sqlite:///") and db_path.exists():
        try:
            os.remove(db_path)
        except OSError:
            pass

    # 2. Run real production Alembic migrations to head
    print(f"[Bootstrap] Running Alembic migrations to head on {db_url}...")
    alembic_ini = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(alembic_cfg, "head")

    # 3. Seed deterministic personas
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        hashed_pwd = hash_password("TestPassword123!")
        existing = session.query(User).filter(
            User.email.in_(["admin@orchestra.io", "member@orchestra.io", "viewer@orchestra.io"])
        ).all()
        existing_emails = {u.email for u in existing}
        new_users = []
        if "admin@orchestra.io" not in existing_emails:
            new_users.append(User(email="admin@orchestra.io", password_hash=hashed_pwd, role=UserRole.ADMIN))
        if "member@orchestra.io" not in existing_emails:
            new_users.append(User(email="member@orchestra.io", password_hash=hashed_pwd, role=UserRole.MEMBER))
        if "viewer@orchestra.io" not in existing_emails:
            new_users.append(User(email="viewer@orchestra.io", password_hash=hashed_pwd, role=UserRole.VIEWER))

        if new_users:
            session.add_all(new_users)
            session.commit()
        print("Bootstrap test database SUCCESS: migrations applied and personas seeded.")
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    bootstrap()
