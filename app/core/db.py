

import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv

load_dotenv()

# Use the asyncpg driver for PostgreSQL async compliance
DATABASE_URL = os.getenv("DATABASE_URL")

# 1. Create the asynchronous engine
async_engine = create_async_engine(
    str(DATABASE_URL),
    echo=False,          # Set to True if you want to see raw SQL logs in your terminal
    pool_size=20,        # Maximum number of persistent connections to hold open
    max_overflow=10      # Extra transient connections allowed during traffic spikes
)

# 2. Create the session factory
# expire_on_commit=False prevents SQLAlchemy from breaking object attributes after DB commits
AsyncSessionFactory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

