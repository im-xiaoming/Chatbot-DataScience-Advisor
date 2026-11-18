from __future__ import annotations

import logging

from sqlalchemy import select, update

from sqlalchemy.orm import Session
from .models import ModelDoc, ModelChunk

from rag.types import ChunkRecord, DocRecord

from common import logs


logger = logging.getLogger(__name__)


class DocumentQuery:
    def __init__(self, session: Session):
        self.session = session
        
    async def get_by_id(self, id: str) -> ModelDoc:
        stmt = select(ModelDoc).where(
            ModelDoc.doc_id == id
        )
        return await self.session.scalar(stmt)
    
    async def update(self, doc_id: str, data: DocRecord) -> ModelDoc:
        stmt = (
            update(ModelDoc)
            .where(ModelDoc.doc_id == doc_id)
            .values(**data.model_dump())
        )
        
        try:
            await self.session.execute(stmt)
        except Exception as e:
            logger.exception(str(e))
            await self.session.rollback()
            
    
    async def query(self, stmt):
        try:
            return await self.session.execute(stmt)
        except Exception as e:
            logger.exception(str(e))
            
    
    async def insert(self, doc: DocRecord) -> ModelDoc:
        if await self.session.get(ModelDoc, doc.doc_id):
            logger.info(f"doc_id: {doc.doc_id} already in database. Update.")
            await self.update(doc_id=doc.doc_id, data=doc)
            return
        
        try:
            d = ModelDoc(**doc.model_dump())
            self.session.add(d)
            await self.session.flush()
            return d
        
        except Exception as e:
            logger.exception("Add to database error: " + str(e))
            await self.session.rollback()
            
    
    async def insert_all(self, docs: list[DocRecord]) -> list[ModelDoc]:
        try:
            docs = [await self.insert(doc) for doc in docs]
            await self.session.flush()
            return docs
        
        except Exception as e:
            logger.exception("Exception create_all: " + str(e))
    
    
class ChunkQuery:
    def __init__(self, session: Session):
        self.session = session
        
    async def get_by_id(self, chunk_id: str) -> ModelChunk | None:
        stmt = select(ModelChunk).where(
            ModelChunk.chunk_id == chunk_id
        )
        return await self.session.scalar(stmt)
    
    
    async def update(self, chunk_id: str, data: ChunkRecord) -> ModelChunk:
        stmt = (
            update(ModelChunk)
            .where(ModelChunk.chunk_id == chunk_id)
            .values(**data.model_dump())
        )
        
        try:
            await self.session.execute(stmt)
        except Exception as e:
            logger.exception(str(e))
            await self.session.rollback()
    
    
    async def query(self, stmt):
        try:
            return await self.session.execute(stmt)
        except Exception as e:
            logger.exception(str(e))
            

    async def insert(self, chunk: ChunkRecord) -> ModelChunk:
        if await self.session.get(ModelChunk, chunk.chunk_id):
            logger.info(f"chunk_id: {chunk.chunk_id} already in database. Update.")
            await self.update(chunk_id=chunk.chunk_id, data=chunk)
            return
        
        try:
            c = ModelChunk(**chunk.model_dump())
            self.session.add(c)
            await self.session.flush()
            return c

        except Exception as e:
            logger.exception("Add to database error: " + str(e))
            await self.session.rollback()


    async def insert_all(self, chunks: list[ChunkRecord]) -> list[ModelChunk]:
        try:
            chunks = [await self.insert(chunk) for chunk in chunks]
            await self.session.flush()
            return chunks

        except Exception as e:
            logger.exception("Exception create_all: " + str(e))
    
