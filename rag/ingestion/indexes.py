from __future__ import annotations

import logging
import uuid
from qdrant_client import models
from langchain_core.embeddings import Embeddings

import db
from common import logs

from rag.types import ChunkRecord
from common import _NAMESPACE


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
 
        
def build_points(records: list[ChunkRecord], embeddings: Embeddings) -> models.PointsList:
    points = []
    for record, embedding in zip(records, embeddings, strict=True):
        points.append(
            _point(
                id=_create_point_id(record.chunk_id, record.page_content),
                vector=embedding,
                payload=record.model_dump()
            )
        )
    return models.PointsList(points=points)
    
    
if __name__ == '__main__':
    id = _create_point_id('123213', page_content='hello')
    print(id)