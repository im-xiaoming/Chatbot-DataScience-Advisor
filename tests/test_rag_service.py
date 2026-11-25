"""Kiểm tra api/rag_service.py (RETRIEVER=qdrant) với Qdrant trong bộ nhớ và embedding giả, không cần Ollama."""
import importlib
import sys

import pytest
from qdrant_client import AsyncQdrantClient

import db.qdrant
import rag.embeddings
from rag.embeddings import helper
from rag.ingestion.indexer import QdrantIndexer


class FakeEmbedder:
    def __init__(self, *a, **kw):
        pass

    async def aembedding_query(self, q):
        return [1.0, 0.0] if "thôi học" in q else [0.0, 1.0]


@pytest.fixture
async def service(monkeypatch, make_chunk):
    monkeypatch.setattr(db.qdrant, "EMBEDDING_DIMENSIONS", 2)
    monkeypatch.setattr(rag.embeddings, "ModelEmbeddings", FakeEmbedder)
    client = AsyncQdrantClient(":memory:")
    monkeypatch.setattr(db, "create_qdrant_client", lambda cfg: client)
    sys.modules.pop("api.rag_service", None)
    svc = importlib.import_module("api.rag_service")

    chunks = [make_chunk(chunk_id="c1", page_content="buộc thôi học cảnh báo", url="u1"),
              make_chunk(chunk_id="c2", page_content="học bổng khuyến khích", url="u2", category="scholarship_tuition")]
    idx = QdrantIndexer(collection_name=svc.COLLECTION, client=lambda cfg: client)
    await idx.create_collection(create_payload=False)
    await idx.upsert(QdrantIndexer.build_points(records=chunks, embeddings=[[1.0, 0.0], [0.0, 1.0]],
                                                sparse_vector=[helper._TF(c, avgdl=3) for c in chunks]))
    yield svc
    sys.modules.pop("api.rag_service", None)
    await client.close()


@pytest.mark.parametrize("strategy", ["dense", "sparse", "hybrid"])
async def test_each_strategy_ranks_matching_chunk_first(service, strategy):
    res = await service.retrieve("buộc thôi học", k=2, strategy=strategy)
    assert res[0]["url"] == "u1" and "score" in res[0]


async def test_category_filter(service):
    res = await service.retrieve("buộc thôi học", category="scholarship_tuition", k=5)
    assert [r["url"] for r in res] == ["u2"]


async def test_unknown_strategy(service):
    with pytest.raises(ValueError):
        await service.retrieve("x", strategy="bm25")
