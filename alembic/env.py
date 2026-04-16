"""
alembic/env.py
--------------
Alembic reads this file to know:
  1. Which DB to connect to (reads DATABASE_URL from .env)
  2. Which models exist (imports Base from our app)

Two run modes:
  offline — generates SQL scripts without a live DB connection
  online  — connects to PostgreSQL and runs migrations directly
            We use async mode to match our app's async engine.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Load app settings to get DATABASE_URL
from app.database import settings

# Import Base so Alembic can see all our models
from app.database import Base
import app.models  # noqa: F401 — ensures models are registered on Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Tell Alembic which metadata to track (our tables)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Generate SQL migration scripts without a live DB.
    Useful for reviewing what will be applied before running it.
    """
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Connect to PostgreSQL asynchronously and apply migrations."""
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
