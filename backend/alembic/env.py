import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure backend root is in sys.path
backend_root = str(Path(__file__).resolve().parent.parent)
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from app.core.config import settings
from app.database.base import Base
from app.models.user import User
from app.models.project import Project
from app.models.session import Session
from app.models.message import Message

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate and migrations
target_metadata = Base.metadata


def get_url() -> str:
    """Retrieves target database URL from environment or configuration."""
    if settings.database_url:
        url = settings.database_url
        if url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    ini_url = config.get_main_option("sqlalchemy.url")
    if ini_url and "driver://user:pass" not in ini_url:
        return ini_url
    return "postgresql+psycopg://postgres:postgres@localhost:5432/orchestra"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section, {}) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
