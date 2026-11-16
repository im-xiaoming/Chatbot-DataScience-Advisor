from __future__ import annotations

import logging
import uuid
from qdrant_client import models
from langchain_core.embeddings import Embeddings
from qdrant_client import AsyncQdrantClient
from config import QDrantConfig

import db
from common import logs

from rag.types import ChunkRecord
from common import _NAMESPACE
from db import QuantModel


logger = logging.getLogger(__name__)


def _point(
    *,
    id: uuid.UUID,
    vector: list[float],
    payload: models.Payload,
) -> models.PointStruct:
    try:
        return models.PointStruct(
            id=id,
            vector=vector,
            payload=payload
        )
    except Exception as e:
        logger.exception("Failed to create PointStruct.")
        
 
def _create_point_id(chunk_id: str, page_content: str) -> uuid.UUID:
    return uuid.uuid5(
        namespace=uuid.UUID(_NAMESPACE),
        name= (chunk_id + page_content).encode('utf-8')
    )
 
 
class QdrantIndexer(QuantModel):
    def __init__(
        self,
        collection_name: str,
        client: AsyncQdrantClient | None = None,
        config: QDrantConfig | None = None
    ):
        super().__init__(
            collection_name=collection_name,
            client=client,
            config=config
        )
    
    @staticmethod    
    def build_points(records: list[ChunkRecord], embeddings: list[Embeddings]) -> list[models.PointStruct]:
        points = []
        for record, embedding in zip(records, embeddings, strict=True):
            points.append(
                _point(
                    id=_create_point_id(record.chunk_id, record.page_content),
                    vector={'dense': embedding},
                    payload=record.model_dump()
                )
            )
        return points