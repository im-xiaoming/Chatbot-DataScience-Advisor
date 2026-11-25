from __future__ import annotations

import logging
from typing import Literal
from rag.types import QueryPoint

from db import QdrantModel, DENSE, SPARSE
from qdrant_client import AsyncQdrantClient, models
from config import QdrantConfig

from common import logs
from common.wrappers import run_async


logger = logging.getLogger(__name__)

class QdrantSearch(QdrantModel):
    def __init__(
        self,
        collection_name: int,
        client: AsyncQdrantClient | None = None,
        config: QdrantConfig | None = None
    ):
        super().__init__(collection_name, client, config)
        

    async def search(
        self,
        *,
        query_vector: list[float],
        sparse_vector: models.SparseVector | None = None,
        query_filter: models.Filter | None = None,
        limit: int = 15,
        with_payload: bool = True,
        mode: Literal['dense', 'sparse'] = 'dense',
        format: bool | None = False
    ):
        if not self.client:
            self.create_qdrant_client()
        
        if mode == 'sparse' and not sparse_vector:
            raise ValueError("Sparse vector must be not None if mode is \"sparse\".")
        
        logger.info("Starting query point.")
        try:
            response = await self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=with_payload,
                timeout=600,
                using=DENSE if mode == 'dense' else SPARSE
            )
            
            if not format:
                return response
            
            points = []
            for point in response.points:
                points.append(
                    QueryPoint(
                        point_id=point.id,
                        version=point.version,
                        score=point.score,
                        **point.payload
                    )
                )
            return points
        
        except Exception as e:
            logger.exception("Search error" + str(e))
            
    
    async def hybrid_search(
        self,
        *,
        query_vector: list[float],
        sparse_vector: models.SparseVector,
        limit: int = 25,
        dense_limit: int = 10,
        sparse_limit: int = 10,
        filter: models.Filter | None = None,
        dense_filter: models.Filter | None = None,
        sparse_filter: models.Filter | None = None,
        format: bool | None = False
    ) -> models.QueryResponse:
        if not self.client:
            self.create_qdrant_client()
        
        logger.info("Starting hybrid search.")
        
        try:    
            response = await self.client.query_points(
                collection_name=self.collection_name,
                prefetch=[
                    models.Prefetch(
                        query=query_vector,
                        limit=dense_limit,
                        using=DENSE,
                        filter=dense_filter
                    ),
                    models.Prefetch(
                        query=sparse_vector,
                        limit=sparse_limit,
                        using=SPARSE,
                        filter=sparse_filter
                    )
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit,
                with_payload=True,
                timeout=600
            )
            return response
        
        except Exception as e:
            logger.exception("Error in hybrid search: " + str(e))