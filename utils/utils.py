from __future__ import annotations

import logging

from db.qdrant_db.session import create
from db.qdrant_db.queries import ChunkQuery, DocumentQuery

from rag.types import DocRecord, ChunkRecord


logger = logging.getLogger(__name__)


async def save_to_db(docs: list[DocRecord], chunks: list[ChunkRecord]):
    engine, Session = create()
    try:
        async with Session() as session, session.begin():
            await DocumentQuery(session=session).insert_all(docs=docs)
            await ChunkQuery(session=session).insert_all(chunks=chunks)
            
        logger.info("Insert to db successfully.")
        
    except Exception as e:
        logger.exception("Save to DB error: " + str(e))
        raise
    finally:
        await engine.dispose()