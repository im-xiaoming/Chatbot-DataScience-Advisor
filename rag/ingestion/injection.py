from __future__ import annotations

import copy
import asyncio

from config import LLMConfig
from agent.models import load_llm_model
from rag.types import DocRecord, ChunkRecord

from langchain.messages import SystemMessage, HumanMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.qdrant_db.models import ModelChunk

class Injection:
    def __init__(
        self,
        *,
        Session: Session,
        config: LLMConfig,
        temperature: float,
        CONTEXT_USER_PROMPT: str,
        CONTEXT_SYSTEM_PROMPT: str,
    ):
        self.session = Session()
        self.model = load_llm_model(
            model_name=config.model_name,
            model_provider=config.model_provider,
            temperature=temperature
        )
        self.CONTEXT_SYSTEM_PROMPT = CONTEXT_SYSTEM_PROMPT
        self.CONTEXT_USER_PROMPT = CONTEXT_USER_PROMPT
        
    async def _inject(
        self,
        doc: DocRecord,
        chunks: list[ModelChunk]
    ) -> list[ChunkRecord]:
        
        messages = [
            [
                SystemMessage(self.CONTEXT_SYSTEM_PROMPT),
                HumanMessage(self.CONTEXT_USER_PROMPT.format(
                    document=doc.page_content,
                    chunk=chunk.page_content,
                )),
            ]
            for chunk in chunks
        ]
        
        try:
            responses = await self.model.abatch(messages, config={"max_concurrency": 2})

            results = []
            for chunk, r in zip(chunks, responses):
                context = r.content.strip()
                results.append(ChunkRecord(**{
                    **{c.name: getattr(chunk, c.name) for c in ModelChunk.__table__.columns},
                    "page_content": f"{context}\n\n{chunk.page_content}",
                }))
            return results
        
        except Exception as e:
            raise
            
    async def inject(self, docs: list[DocRecord]) -> list[ChunkRecord]:
        chunks = []
        for doc in docs:
            stmt = (
                select(ModelChunk).where(
                    ModelChunk.doc_id == doc.doc_id
                )
            )
            results = await self.session.scalars(stmt)
            _chunks = results.all()
            chunks.extend(await self._inject(doc=doc, chunks=_chunks))
        return chunks
                
                
        