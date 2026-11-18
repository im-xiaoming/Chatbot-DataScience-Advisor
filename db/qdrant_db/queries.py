from __future__ import annotations

import logging

from sqlalchemy import select

from sqlalchemy.orm import Session
from .models import ModelDoc, ModelChunk

from rag.types import ChunkRecord, DocRecord

from common import logs


logger = logging.getLogger(__name__)


class DocumentQuery:
    def __init__(self, session: Session):
        self.session = session
        
    def get_by_id(self, id: str) -> ModelDoc:
        stmt = select(ModelDoc).where(
            ModelDoc.doc_id == id
        )
        return self.session.scalar(stmt)
    
    def query(self, stmt):
        try:
            return self.session.execute(stmt)
        except Exception as e:
            logger.exception(str(e))
            raise
    
    def create(self, doc: dict | DocRecord) -> ModelDoc:
        try:
            if isinstance(doc, dict):
                d = ModelDoc(**doc)
            else:
                d = ModelDoc(**doc.model_dump())
            self.session.add(d)
            self.session.flush()
            return d
        
        except Exception as e:
            logger.exception("Add to database error: " + str(e))
            self.session.rollback()
            
            raise
    
    def create_all(self, docs: list[dict | ChunkRecord]) -> list[ModelDoc]:
        try:
            docs = [self.create(doc) for doc in docs]
            self.session.flush()
            return docs
        
        except Exception as e:
            logger.exception("Exception create_all: " + str(e))
            raise
    
    
class ChunkQuery:
    def __init__(self, session: Session):
        self.session = session
        
    def get_by_id(self, chunk_id: str) -> ModelChunk | None:
        stmt = select(ModelChunk).where(
            ModelChunk.chunk_id == chunk_id
        )
        return self.session.scalar(stmt)
    
    def query(self, stmt):
        try:
            return self.session.execute(stmt)
        except Exception as e:
            logger.exception(str(e))
            
            raise

    def create(self, chunk: dict | ChunkRecord) -> ModelChunk:
        try:
            if isinstance(chunk, dict):
                c = ModelChunk(**chunk)
            else:
                c = ModelChunk(**chunk.model_dump())
            self.session.add(c)
            self.session.flush()
            return c

        except Exception as e:
            logger.exception("Add to database error: " + str(e))
            self.session.rollback()
            raise

    def create_all(self, chunks: list[dict | ChunkRecord]) -> list[ModelChunk]:
        try:
            chunks = [self.create(chunk) for chunk in chunks]
            self.session.flush()
            return chunks

        except Exception as e:
            logger.exception("Exception create_all: " + str(e))
            raise
    
