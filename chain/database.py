"""
chain/database.py — Self-contained SQLAlchemy async engine.
No app.* imports.
"""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from chain.config import settings

logger = logging.getLogger(__name__)

_db_url = settings.DATABASE_URL
# SQLite needs aiosqlite driver; Postgres needs asyncpg
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)

_connect_args = {}
if "sqlite" in _db_url:
    _connect_args = {"check_same_thread": False}
    engine = create_async_engine(_db_url, echo=False, connect_args=_connect_args)
else:
    engine = create_async_engine(
        _db_url,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        echo=False,
    )

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables if they don't exist, and apply idempotent column migrations."""
    from chain import models  # noqa: F401 — ensure models are registered
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Idempotent column migrations — add columns that may be missing from older DB schemas.
    # These use IF NOT EXISTS so they are always safe to re-run.
    _migrations = [
        # storage_proofs / consensus_votes were added after the initial schema was deployed
        "ALTER TABLE chain_blocks ADD COLUMN IF NOT EXISTS storage_proofs JSONB DEFAULT '[]'",
        "ALTER TABLE chain_blocks ADD COLUMN IF NOT EXISTS consensus_votes JSONB DEFAULT '[]'",
    ]
    async with engine.begin() as conn:
        for stmt in _migrations:
            try:
                await conn.execute(text(stmt))
            except Exception as exc:
                # SQLite doesn't support IF NOT EXISTS on ADD COLUMN in older versions;
                # skip silently — SQLite is dev-only, Postgres is production.
                logger.debug("Migration skipped (%s): %s", exc.__class__.__name__, stmt)

    logger.info("Chain database tables initialised.")


async def get_db():
    """FastAPI dependency — yields an async session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
