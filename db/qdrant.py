from __future__ import annotations

import logging
import types
from typing import Callable, Literal
from qdrant_client import AsyncQdrantClient, models

from rag.embeddings import EMBEDDING_DIMENSIONS
from config import QdrantConfig
from .schemas import _PAYLOAD
from common import logs
from common import run_async
from config import QdrantConfig

logger = logging.getLogger(__name__)


DENSE, SPARSE = 'dense', 'sparse'

def create_qdrant_client(config: QdrantConfig) -> AsyncQdrantClient:
    try:
        client = AsyncQdrantClient(
            location=config.host
        )
        return client
    except Exception as e:
        logger.exception("Error when init Qdrant Client." + str(e))


async def _create_collection(
    *,
    client: AsyncQdrantClient,
    collection_name: str,
    ):
    global EMBEDDING_DIMENSIONS
    if not EMBEDDING_DIMENSIONS:
        from agent.models import load_embedding_model
        from config import EmbeddingsConfig
        
        config = EmbeddingsConfig()
        model = load_embedding_model(
            model_name=config.model_name,
            model_provider=config.model_provider
        )
        EMBEDDING_DIMENSIONS = len(model.embed_query("Hello!"))
    
    assert EMBEDDING_DIMENSIONS, '"load_embedding_model" function must be called first before call "create_collection".'
    
    if await client.collection_exists(collection_name=collection_name):
        logger.info(f'Collection "{collection_name}" already exists.')
        return
    
    try:
        await client.create_collection(
            collection_name=collection_name,
            vectors_config={
                DENSE: models.VectorParams(size=EMBEDDING_DIMENSIONS, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={
                SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)
            },
            timeout=600,
        )
    except Exception as e:
        logger.exception(f"Failed to create collection: {collection_name}. Error: {e}.")
    else:
        logger.info(f"Create collection {collection_name} successful.")


async def _create_payload(
    *,
    client: AsyncQdrantClient,
    collection_name: str
):
    try:
        for field_name, field_schema in _PAYLOAD:
            await client.create_payload_index(
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


async def _delete_collection(
    *,
    client: AsyncQdrantClient,
    collection_name: str
):
    try:
        await client.delete_collection(
            collection_name=collection_name,
            timeout=600,
        )
    except Exception as e:
        logger.exception(f'Failed to delete collection "{collection_name}". Error {e}.')
    else:
        logger.info(f'Already delete collection "{collection_name}".')


async def _upsert(
    *,
    client: AsyncQdrantClient,
    collection_name: str,
    points: list[models.PointStruct]
):
    try:
        await client.upsert(
            collection_name=collection_name,
            points=points,
            timeout=600,
            wait=True
        )
    except Exception as e:
        logger.exception(f'Failed to upsert points. Collection name: "{collection_name}". Error: {e}.')
    else:
        logger.info("Upsert points successfully.")


class QdrantModel:
    def __init__(
        self,
        collection_name: str,
        client: AsyncQdrantClient | Callable[[QdrantConfig], None] | None = None,
        config: QdrantConfig | None = None
    ):
        assert (client or config), "Client or Config must be not None."
        
        self.collection_name = collection_name
        self.config = config
        self.client_instance = client
        self.client = None
        
        if not self.config:
            self.config = QdrantConfig()
            
    
    def create_qdrant_client(self):
        if isinstance(self.client, AsyncQdrantClient):
            self.client = self.client_instance
        elif isinstance(self.client_instance, types.FunctionType):
            self.client = self.client_instance(self.config)
        elif self.client_instance is None:
            self.client = create_qdrant_client(config=self.config)
            
        assert self.client, "Client haven't created yet."
        
        
    async def upsert(self, points: list[models.PointStruct]):
        if not self.client:
            self.create_qdrant_client()
           
        await _upsert(
            client=self.client,
            collection_name=self.collection_name,
            points = points
        )
        

    async def delete_collection(self):
        if not self.client:
            self.create_qdrant_client()
        await _delete_collection(client=self.client, collection_name=self.collection_name)
        

    async def create_collection(self, create_payload=True):
        if not self.client:
            self.create_qdrant_client()
        try:
            await _create_collection(client=self.client,collection_name=self.collection_name)
            if create_payload:
                await _create_payload(client=self.client, collection_name=self.collection_name)
        except Exception as e:
            print("error: " + str(e))
        

    async def create_payload(self):
        if not self.client:
            self.create_qdrant_client()
        await _create_payload(client=self.client, collection_name=self.collection_name)
