from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from qdrant_client import models

from config import QdrantConfig
from db import DENSE, SPARSE
from rag.retrieval import QdrantSearch
from rag.types import QueryPoint


def sample_payload() -> dict:
    return {
        "doc_id": "doc-1",
        "chunk_id": "doc-1+000000000000001",
        "title": "Kế hoạch học tập",
        "page_content": "Học kỳ một có các môn cơ sở.",
        "url": "https://example.com/plan",
        "category": "curriculum",
        "section_path": ["Năm nhất", "Học kỳ 1"],
        "publisher": "IUH",
        "authority": "official",
        "language": "vi",
        "region": "VN",
        "license": "public",
        "normalized_at": "2026-01-01T00:00:00",
        "pipeline_version": "1.0.0",
    }


class QdrantSearchTests(unittest.IsolatedAsyncioTestCase):
    def make_searcher(self, response=None) -> tuple[QdrantSearch, AsyncMock]:
        searcher = QdrantSearch(collection_name="test_collection", config=QdrantConfig())
        client = AsyncMock()
        client.query_points.return_value = response or SimpleNamespace(points=[])
        searcher.client = client
        return searcher, client

    async def test_dense_search_passes_vector_filter_and_top_k(self) -> None:
        searcher, client = self.make_searcher()
        query_filter = models.Filter(
            must=[
                models.FieldCondition(key="category", match=models.MatchValue(value="curriculum")),
                models.FieldCondition(key="student_year", match=models.MatchValue(value=1)),
            ]
        )

        await searcher.search(
            query_vector=[0.1, 0.2],
            query_filter=query_filter,
            limit=7,
            mode="dense",
        )

        kwargs = client.query_points.await_args.kwargs
        self.assertEqual(kwargs["query"], [0.1, 0.2])
        self.assertEqual(kwargs["using"], DENSE)
        self.assertEqual(kwargs["query_filter"], query_filter)
        self.assertEqual(kwargs["limit"], 7)

    async def test_sparse_search_requires_sparse_vector(self) -> None:
        searcher, client = self.make_searcher()

        with self.assertRaisesRegex(ValueError, "Sparse vector must be not None"):
            await searcher.search(query_vector=[], mode="sparse")

        client.query_points.assert_not_awaited()

    async def test_formatted_search_maps_payload_to_query_points(self) -> None:
        point = SimpleNamespace(
            id="point-1",
            version=3,
            score=0.91,
            payload=sample_payload(),
        )
        searcher, _ = self.make_searcher(SimpleNamespace(points=[point]))

        results = await searcher.search(query_vector=[0.1], format=True)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], QueryPoint)
        self.assertEqual(results[0].point_id, "point-1")
        self.assertEqual(results[0].title, "Kế hoạch học tập")
        self.assertEqual(results[0].score, 0.91)

    async def test_formatted_search_returns_empty_list_when_no_hits(self) -> None:
        searcher, _ = self.make_searcher(SimpleNamespace(points=[]))

        results = await searcher.search(query_vector=[0.1], format=True)

        self.assertEqual(results, [])

    async def test_hybrid_search_builds_dense_sparse_prefetch_and_rrf(self) -> None:
        searcher, client = self.make_searcher()
        sparse = models.SparseVector(indices=[5], values=[1.0])
        dense_filter = models.Filter(must=[models.HasIdCondition(has_id=["dense-id"])])
        sparse_filter = models.Filter(must=[models.HasIdCondition(has_id=["sparse-id"])])

        await searcher.hybrid_search(
            query_vector=[0.1, 0.2],
            sparse_vector=sparse,
            dense_limit=4,
            sparse_limit=6,
            limit=5,
            dense_filter=dense_filter,
            sparse_filter=sparse_filter,
        )

        kwargs = client.query_points.await_args.kwargs
        self.assertEqual(kwargs["limit"], 5)
        self.assertEqual(kwargs["prefetch"][0].using, DENSE)
        self.assertEqual(kwargs["prefetch"][0].limit, 4)
        self.assertEqual(kwargs["prefetch"][0].filter, dense_filter)
        self.assertEqual(kwargs["prefetch"][1].using, SPARSE)
        self.assertEqual(kwargs["prefetch"][1].limit, 6)
        self.assertEqual(kwargs["prefetch"][1].query, sparse)
        self.assertEqual(kwargs["prefetch"][1].filter, sparse_filter)
        self.assertEqual(kwargs["query"].fusion, models.Fusion.RRF)


if __name__ == "__main__":
    unittest.main()
