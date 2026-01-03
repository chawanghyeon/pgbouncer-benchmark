import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

# Determine DB URL
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    if os.getenv("USE_CONNECTION_POOLING") == "1":
        DATABASE_URL = os.getenv("DATABASE_URL_POOLED")
    else:
        DATABASE_URL = os.getenv("DATABASE_URL_DIRECT")

if not DATABASE_URL:
    DATABASE_URL = "postgresql+psycopg://postgres:password@localhost:5432/benchmark_db"

# Ensure using psycopg v3 driver
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")

# Psycopg 3 specific: disable prepared statements for PgBouncer transaction mode
connect_args = {}
# Heuristic for PgBouncer usage
if "pgbouncer" in str(DATABASE_URL) or os.getenv("USE_CONNECTION_POOLING") == "1":
    connect_args["prepare_threshold"] = None

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
    # Application-side pooling configuration
    # Small pool since we might rely on PgBouncer or sidecar
    pool_size=10,
    max_overflow=20
)

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
