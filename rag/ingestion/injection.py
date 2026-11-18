from __future__ import annotations

import copy

from config import LLMConfig
from agent.models import load_llm_model
from rag.types import DocRecord, ChunkRecord

from langchain.messages import HumanMessage, SystemMessage

class Injection:
    def __init__(
        self,
        *,
        config: LLMConfig,
        temperature: float,
        prompt: str
    ):
        self.model = load_llm_model(
            model_name=config.model_name,
            model_provider=config.model_provider,
            temperature=temperature
        )
        self.prompt = prompt
        
    def inject(
        self,
        doc: str | DocRecord,
        chunks: list[ChunkRecord]
    ) -> list[ChunkRecord]:
        doc_content = doc if isinstance(doc, str) else doc.page_content
        model = copy.deepcopy(self.model).with_structured_output(ChunkRecord)
        
        new_chunks = []
        
        for chunk in chunks:
            msg = [
                SystemMessage(f'DOCUMENT:\n{doc_content}.\n\nCHUNK:\n{chunk}\n\nPROMPT:\n{self.prompt}.')
            ]
            try:
                response = model.invoke(msg)
                # new_chunks.append(ChunkRecord(**response))
                new_chunks.append(response)
                
                return new_chunks
            
            except Exception as e:
                pass
                
        