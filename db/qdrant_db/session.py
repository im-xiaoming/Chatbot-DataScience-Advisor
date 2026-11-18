from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from config import QdrantDatabaseConfig

logger = logging.getLogger(__name__)




def create() -> tuple:
    config = QdrantDatabaseConfig()
    
    engine = create_async_engine(
        url=config.DATABASE_URL,
        echo=True,
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
    
    

