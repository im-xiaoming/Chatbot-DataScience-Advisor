from __future__ import annotations

import torch
import logging
import asyncio

from collections import OrderedDict
from typing import Optional, Callable, Literal

from qdrant_client import models

import config
from common import run_async
from rag.rerank import CrossEncoder
from agent.models import load_embedding_model

from langchain_core.embeddings import Embeddings
from dataclasses import dataclass

from .import helper
from rag.types import ChunkRecord
from common import logs


logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = None


class SparseEmbedding:
    def __init__(self, chunks: list[ChunkRecord], avg_search: bool = False):
        self.chunks = chunks
        self.avgdl = 256
        if avg_search:
            self.avgdl = helper.search_avgdl(chunks)
    
    def build_sparses(self) -> list[models.SparseVector]:
        sparses = []
        for chunk in self.chunks:
            if not self.avgdl:
                sparse = helper._TF(chunk)
            else:
                sparse = helper._TF(chunk, avgdl=self.avgdl)
            sparses.append(sparse)
        return sparses
    
    @staticmethod
    def sparse_query(query: str, avgdl: int = 256) -> models.SparseVector:
        return helper._TF(d=query, avgdl=avgdl)

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
        
            

    async def aembedding_query(self, query: str) -> list[float]:
        logger.info("Embedding query.")
        async with self.semaphore:
            return await self._query(query, self.embedding_model.aembed_query)



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
        embeddings = []
        async with self.semaphore:
            for start in range(0, len(documents), batch_size):
                batch = documents[start:start + batch_size]
                embeddings.extend(await self.embedding_model.aembed_documents(batch))
                logger.info("Embedded %d/%d documents.", start + len(batch), len(documents))
        return embeddings



