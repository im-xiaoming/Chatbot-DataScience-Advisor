from __future__ import annotations

import torch
import logging
import asyncio

from collections import OrderedDict
from typing import Optional, Callable, Literal

import config
from common import run_async
from rag.rerank import CrossEncoder
from agent.models import load_embedding_model

from langchain_core.embeddings import Embeddings

from common import logs


logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = None


class ModelEmbeddings:
    
    def __init__(
        self,
        embedding_model: Optional[Embeddings] = None,
        cross_encoder_model: Optional[CrossEncoder] = None,
        config: Optional[config.EmbeddingsConfig] = None,
        # device: Literal['cuda', 'cpu'] = 'cuda',
        maxsize: int = 128,
        semaphore: int = 2,
    ):
        if not (embedding_model or config):
            raise 'one of "model" or "config" must be not None.'

        if embedding_model:
            self.embedding_model = embedding_model
        elif config:
            self.embedding_model = load_embedding_model(
                model_name= config.model_name,
                model_provider = config.model_provider
            )
        self.cross_encoder = cross_encoder_model    
        self._cache = OrderedDict()
        # self.device = torch.device(device if torch.cuda.is_available() else 'cpu')
        self.maxsize = maxsize
        
        self.semaphore = asyncio.Semaphore(semaphore)
        
            
    # async def _query(self, query: str, func: Callable[[str], list[float]]):
    #     if query in self._cache:
    #         logging.info("Query already cached. No embedding called.")
    #         self._cache.move_to_end(query, last=True)
    #         return self._cache[query]
    #     else:
    #         query_embed = torch.tensor(await func(query), dtype=torch.float32).to(self.device) # (N, 1)
            
    #         if len(self._cache) > 0:
    #             embeds = torch.tensor(list(self._cache.values()), dtype=torch.float32).to(self.device) # (M, N)
    #             cosine = embeds @ query_embed.t() # (M, 1)
    #             value, index = cosine.cpu().max(dim=-1)
    #             if value > self.threshold:
    #                 logging.info("Query already cached. No embedding called.")
    #                 return self._cache[self._cache.keys()[index]]
    #         else:
    #             logging.info("Caching new query.")
    #             self._cache[query] = query_embed.cpu().tolist()
    #             if len(self._cache) > self.maxsize:
    #                 self._cache.popitem(last=False)
    #             return self._cache[query]
    
    
    async def _query(self, query: str, func: Callable[[str], list[float]]):
        if query in self._cache:
            logger.info("Fetch from cached query.")
            return self._cache[query]
        r = await func(query)
        self._cache[query] = r
        self._cache.move_to_end(query, last=True)
        if len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)
        return r
        
            
    @run_async
    async def aembedding_query(self, query: str) -> list[float]:
        logger.info("Embedding query.")
        async with self.semaphore:
            return await self._query(query, self.embedding_model.aembed_query)


    @run_async
    async def aembedding_documents(
        self, documents: list[str], batch_size: int = 16
    ) -> list[list[float]]:
        """Embedding documents

        Args:
            model (Embeddings): Model
            documents (list[str]): List of string

        Returns:
            list[list[float]]: List of list of float
        """
        if batch_size < 1:
            raise ValueError("batch_size must be greater than zero")
        logger.info("Embedding %d documents in batches of %d.", len(documents), batch_size)
        embeddings: list[list[float]] = []
        async with self.semaphore:
            for start in range(0, len(documents), batch_size):
                batch = documents[start:start + batch_size]
                embeddings.extend(await self.embedding_model.aembed_documents(batch))
                logger.info("Embedded %d/%d documents.", start + len(batch), len(documents))
        return embeddings

