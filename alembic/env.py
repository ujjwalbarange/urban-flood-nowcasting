"""Alembic async migration environment for MUFNS.

Loads DATABASE_URL from .env, configures SSL for Aiven,
and uses the project's existing Base metadata for autogenerate.
"""

import asyncio
import os
import ssl
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── Load .env from project root ──
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

# ── Alembic Config ──
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import our Base so Alembic knows about all ORM models ──
# This import also triggers model registration via models.py
from services.database.connection import Base  # noqa: E402
import services.database.models  # noqa: E402, F401  — force model registration

target_metadata = Base.metadata

# ── Read DATABASE_URL from env and inject into Alembic config ──
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://ufn_user:changeme_in_production@localhost:5432/urban_flood",
)
# Strip ssl param from URL since we pass it via connect_args
clean_url = DATABASE_URL.replace("?ssl=require", "").replace("&ssl=require", "")
config.set_main_option("sqlalchemy.url", clean_url)


def _build_connect_args() -> dict:
    """Build SSL connect_args for Aiven or other remote hosts."""
    url = os.getenv("DATABASE_URL", "")
    if "aivencloud.com" in url or "ssl=require" in url:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return {"ssl": ctx}
    return {}


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connect_args = _build_connect_args()

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
