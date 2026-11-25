from __future__ import annotations

import logging
from typing import Literal

from qdrant_client import AsyncQdrantClient, models

from config import QdrantConfig
from db import DENSE, SPARSE, QdrantModel
from rag.types import QueryPoint


logger = logging.getLogger(__name__)


def _combine_filters(
    common: models.Filter | None,
    branch: models.Filter | None,
) -> models.Filter | None:
    if common is None:
        return branch
    if branch is None:
        return common
    return models.Filter(must=[common, branch])


def _format_response(
    response: models.QueryResponse,
    format: bool | None,
) -> models.QueryResponse | list[QueryPoint]:
    if not format:
        return response

    return [
        QueryPoint(
            **{
                **(point.payload or {}),
                "point_id": str(point.id),
                "version": point.version,
                "score": point.score,
            }
        )
        for point in response.points
    ]


class QdrantSearch(QdrantModel):
    def __init__(
        self,
        collection_name: str,
        client: AsyncQdrantClient | None = None,
        config: QdrantConfig | None = None,
    ):
        super().__init__(collection_name, client, config)
        if isinstance(client, AsyncQdrantClient):
            self.client = client

    async def search(
        self,
        *,
        query_vector: list[float] | None = None,
        sparse_vector: models.SparseVector | None = None,
        query_filter: models.Filter | None = None,
        limit: int = 15,
        with_payload: bool = True,
        mode: Literal["dense", "sparse"] = "dense",
        format: bool | None = False,
    ) -> models.QueryResponse | list[QueryPoint]:
        if format and not with_payload:
            raise ValueError("Formatted search results require with_payload=True.")

        if mode == "dense":
            if not query_vector:
                raise ValueError("Dense search requires query_vector.")
            vector, vector_name = query_vector, DENSE
        elif mode == "sparse":
            if sparse_vector is None:
                raise ValueError("Sparse search requires sparse_vector.")
            vector, vector_name = sparse_vector, SPARSE
        else:
            raise ValueError(f"Unsupported search mode: {mode}")

        if self.client is None:
            self.create_qdrant_client()

        logger.info("Starting %s search.", mode)
        response = await self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=with_payload,
            timeout=600,
            using=vector_name,
        )
        return _format_response(response, format)

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
        format: bool | None = False,
    ) -> models.QueryResponse | list[QueryPoint]:
        if self.client is None:
            self.create_qdrant_client()

        logger.info("Starting hybrid search.")
        response = await self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=query_vector,
                    limit=dense_limit,
                    using=DENSE,
                    filter=_combine_filters(filter, dense_filter),
                ),
                models.Prefetch(
                    query=sparse_vector,
                    limit=sparse_limit,
                    using=SPARSE,
                    filter=_combine_filters(filter, sparse_filter),
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
            timeout=600,
        )
        return _format_response(response, format)
