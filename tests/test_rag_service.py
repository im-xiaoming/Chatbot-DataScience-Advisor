"""Kiểm tra api/rag_service.py (RETRIEVER=qdrant) với Qdrant trong bộ nhớ và embedding giả, không cần Ollama."""
import importlib
import sys
from datetime import datetime, timezone

import pytest
from qdrant_client import AsyncQdrantClient

import db.qdrant
import rag.embeddings
from rag.embeddings import helper
from rag.ingestion.indexer import QdrantIndexer
from rag.retrieval import MetadataFilter


def d(y, m, day):
    return datetime(y, m, day, tzinfo=timezone.utc)


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

    chunks = [make_chunk(chunk_id="c1", page_content="buộc thôi học cảnh báo", url="u1",
                         published_date=d(2024, 1, 1), valid_until=d(2025, 1, 1)),
              make_chunk(chunk_id="c2", page_content="học bổng khuyến khích", url="u2", category="scholarship_tuition",
                         published_date=d(2026, 3, 1)),
              make_chunk(chunk_id="c3", page_content="kỹ năng Data Analyst", url="u3", category="career_role",
                         publisher="ITviec", authority="third_party", language="en", section_path=["Kỹ năng"])]
    idx = QdrantIndexer(collection_name=svc.COLLECTION, client=lambda cfg: client)
    await idx.create_collection(create_payload=False)
    await idx.upsert(QdrantIndexer.build_points(records=chunks, embeddings=[[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]],
                                                sparse_vector=[helper._TF(c, avgdl=3) for c in chunks]))
    yield svc
    sys.modules.pop("api.rag_service", None)
    await client.close()


@pytest.mark.parametrize("strategy", ["dense", "sparse", "hybrid"])
async def test_each_strategy_ranks_matching_chunk_first(service, strategy):
    res = await service.retrieve("buộc thôi học", k=2, strategy=strategy)
    assert res[0]["url"] == "u1" and "score" in res[0]


@pytest.mark.parametrize("filters,urls", [
    (MetadataFilter(category="scholarship_tuition"), {"u2"}),
    (MetadataFilter(category=["regulation", "career_role"]), {"u1", "u3"}),
    (MetadataFilter(exclude_category="regulation"), {"u2", "u3"}),
    (MetadataFilter(authority="third_party", language="en"), {"u3"}),
    (MetadataFilter(publisher=["ITviec", "CareerLink"]), {"u3"}),
    (MetadataFilter(section="Kỹ năng"), {"u3"}),
    (MetadataFilter(published_from=d(2025, 1, 1)), {"u2"}),  # c3 không có ngày ban hành nên bị loại
    (MetadataFilter(published_to=d(2025, 1, 1)), {"u1"}),
    (MetadataFilter(valid_at=d(2026, 1, 1)), {"u2", "u3"}),  # c1 hết hiệu lực 2025-01-01; c2, c3 không ghi hạn
    (MetadataFilter(valid_at=d(2024, 6, 1)), {"u1", "u2", "u3"}),
    (MetadataFilter(), {"u1", "u2", "u3"}),
    (None, {"u1", "u2", "u3"}),
])
async def test_metadata_filter(service, filters, urls):
    res = await service.retrieve("buộc thôi học", filters, k=5)
    assert {r["url"] for r in res} == urls


async def test_unknown_strategy(service):
    with pytest.raises(ValueError):
        await service.retrieve("x", strategy="bm25")
