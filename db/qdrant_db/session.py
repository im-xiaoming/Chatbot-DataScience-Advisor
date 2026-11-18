from __future__ import annotations

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import QdrantDatabaseConfig

logger = logging.getLogger(__name__)


config = QdrantDatabaseConfig()

def create():
    engine = create_engine(
        url=config.DATABASE_URL,
        echo=True,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )

    session = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False
    )
    
    

