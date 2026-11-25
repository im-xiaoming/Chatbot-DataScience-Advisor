from __future__ import annotations

import logging

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from config import QdrantDatabaseConfig

logger = logging.getLogger(__name__)


@lru_cache(maxsize=16)
def create() -> tuple:
    config = QdrantDatabaseConfig()
    
    engine = create_async_engine(
        url=config.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        connect_args={"timeout": 5}
    )

    Session = async_sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False
    )
    
    return engine, Session
    
    

