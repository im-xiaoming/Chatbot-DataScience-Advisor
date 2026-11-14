from __future__ import annotations

import logging
from qdrant_client import AsyncQdrantClient, models

from rag.embeddings import EMBEDDING_DIMENSIONS
from config import QDrantConfig
from .schemas import _PAYLOAD
from common import logs
from common import run_async

logger = logging.getLogger(__name__)


CLIENT = None

DENSE, SPARSE = 'dense', 'sparse'

def create_qdrant_client(config: QDrantConfig):
    global CLIENT
    try:
        CLIENT = AsyncQdrantClient(
            location=config.host
        )
    except Exception as e:
        logger.exception("Error when init Qdrant Client.")
    else:
        logger.info("Qdrant Client created.")
        
    return CLIENT


@run_async
async def create_collection(
    *,
    collection_name: str,
    size: int  = 1024
    ):
    assert not EMBEDDING_DIMENSIONS, '".rag.embeddings.load_embedding_model" function must be called first before call "create_collection".'
    
    if await CLIENT.collection_exists(collection_name=collection_name):
        logger.info(f'Collection "{collection_name}" already exists.')
        return
    
    try:
        await CLIENT.create_collection(
            collection_name=collection_name,
            vectors_config={
                DENSE: models.VectorParams(size=EMBEDDING_DIMENSIONS, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={
                SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)
            },
            timeout=600
        )
    except Exception as e:
        logger.exception(f"Failed to create collection: {collection_name}. Error: {e}.")
    else:
        logger.info(f"Create collection {collection_name} successful.")


@run_async
async def create_payload(
    *,
    collection_name: str
):
    try:
        for field_name, field_schema in _PAYLOAD:
            await CLIENT.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_schema,
                wait=True,
                timeout=600
            )
    except Exception as e:
        logger.exception("Failed to create Payload.")
    else:    
        logger.exception("Create Payload successfully.")


@run_async
async def delete_collection(
    *,
    collection_name: str
):
    try:
        await CLIENT.delete_collection(
            collection_name=collection_name,
            timeout=600
        )
    except Exception as e:
        logger.exception(f'Failed to delete collection "{collection_name}". Error {e}.')
    else:
        logger.info(f'Already delete collection "{collection_name}".')


async def upsert(
    *,
    collection_name: str,
    points: models.PointsList
):
    try:
        await CLIENT.upsert(
            collection_name=collection_name,
            points=points,
            timeout=600,
            wait=True
        )
    except Exception as e:
        logger.exception(f'Failed to upsert points. Collection name: "{collection_name}". Error: {e}.')
    else:
        logger.info("Upsert points successfully.")


class QuantModel:
    def __init__(
        self,
        collection_name: str,
        client: AsyncQdrantClient | None = None,
        config: QDrantConfig | None = None
    ):
        self.collection_name = collection_name
        self.client = client if client else create_qdrant_client(config=config)
        
    @run_async
    async def upsert(self, points):
        await upsert(
            collection_name=self.collection_name,
            points = points
        )