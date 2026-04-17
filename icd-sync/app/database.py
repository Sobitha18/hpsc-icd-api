"""
database.py
-----------
Wires up the async PostgreSQL connection for the entire app.

Concepts used here:
  - AsyncEngine   : the actual connection pool to PostgreSQL (one per app)
  - AsyncSession  : a short-lived transaction per request
  - Base          : all SQLAlchemy models (tables) inherit from this
  - get_db()      : FastAPI dependency — gives each endpoint its own session
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from pydantic_settings import BaseSettings


# ---------------------------------------------------------------------------
# Settings — reads DATABASE_URL from the .env file automatically
# ---------------------------------------------------------------------------
class Settings(BaseSettings):
    DATABASE_URL: str   # e.g. postgresql+asyncpg://user:pass@localhost/icd_db

    class Config:
        env_file = ".env"


settings = Settings()


# ---------------------------------------------------------------------------
# Engine — one connection pool shared across the whole application
# pool_size=10  : keep up to 10 open connections at a time
# echo=False    : don't print every SQL statement (set True to debug)
# ---------------------------------------------------------------------------
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    echo=False,
)


# ---------------------------------------------------------------------------
# Session factory
# Each incoming API request calls get_db(), which opens one session from
# this factory, runs the endpoint, then closes it automatically.
# expire_on_commit=False means we can still read object fields after commit.
# ---------------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Base — every model (icd_codes, sync_history) will inherit from this.
# SQLAlchemy uses it to know which Python classes are DB tables.
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# get_db — FastAPI dependency
#
# Usage in any router:
#   async def my_endpoint(db: AsyncSession = Depends(get_db)):
#       result = await db.execute(...)
#
# The `async with` ensures the session is always closed even if an
# exception is raised inside the endpoint.
# ---------------------------------------------------------------------------
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
