import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Determine DB URL
# If DATABASE_URL is explicitly set (e.g. by Orchestrator), use it.
# Otherwise check USE_CONNECTION_POOLING flag.
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    if os.getenv("USE_CONNECTION_POOLING") == "1":
        DATABASE_URL = os.getenv("DATABASE_URL_POOLED")
    else:
        DATABASE_URL = os.getenv("DATABASE_URL_DIRECT")

if not DATABASE_URL:
    # Fallback for local testing
    DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/benchmark_db"

# PgBouncer transaction mode requires disabling prepared statements in asyncpg
connect_args = {}
# We detect if we should disable prepared statements.
# Simple heuristic: if using pooled url or explicit flag
if "pgbouncer" in str(DATABASE_URL) or os.getenv("USE_CONNECTION_POOLING") == "1":
    connect_args["statement_cache_size"] = 0

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
