from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from qdrant_client import models

from db.qdrant import _create_collection, _create_payload, _delete_collection, _upsert
from db.schemas import _PAYLOAD


class QdrantOperationTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_collection_defines_dense_and_sparse_vectors(self) -> None:
        client = AsyncMock()
        client.collection_exists.return_value = False

        with patch("db.qdrant.EMBEDDING_DIMENSIONS", 3):
            await _create_collection(client=client, collection_name="test_collection")

        client.collection_exists.assert_awaited_once_with(collection_name="test_collection")
        client.create_collection.assert_awaited_once()
        kwargs = client.create_collection.await_args.kwargs
        self.assertEqual(kwargs["collection_name"], "test_collection")
        self.assertEqual(kwargs["vectors_config"]["dense"].size, 3)
        self.assertEqual(kwargs["vectors_config"]["dense"].distance, models.Distance.COSINE)
        self.assertIn("sparse", kwargs["sparse_vectors_config"])

    async def test_create_collection_does_not_recreate_existing_collection(self) -> None:
        client = AsyncMock()
        client.collection_exists.return_value = True

        with patch("db.qdrant.EMBEDDING_DIMENSIONS", 3):
            await _create_collection(client=client, collection_name="already_exists")

        client.create_collection.assert_not_awaited()

    async def test_create_payload_adds_an_index_for_each_declared_field(self) -> None:
        client = AsyncMock()

        with (
            patch("db.qdrant.logger.exception"),
            patch("db.qdrant.logger.info"),
        ):
            await _create_payload(client=client, collection_name="test_collection")

        self.assertEqual(client.create_payload_index.await_count, len(_PAYLOAD))

    async def test_upsert_passes_collection_points_and_wait_flag(self) -> None:
        client = AsyncMock()
        points = [
            models.PointStruct(
                id="00000000-0000-0000-0000-000000000001",
                vector={"dense": [0.1]},
                payload={"doc_id": "doc-1"},
            )
        ]

        await _upsert(client=client, collection_name="test_collection", points=points)

        client.upsert.assert_awaited_once_with(
            collection_name="test_collection",
            points=points,
            timeout=600,
            wait=True,
        )

    async def test_delete_collection_targets_requested_collection(self) -> None:
        client = AsyncMock()

        await _delete_collection(client=client, collection_name="test_collection")

        client.delete_collection.assert_awaited_once_with(
            collection_name="test_collection",
            timeout=600,
        )

    async def test_upsert_connection_error_is_logged(self) -> None:
        client = AsyncMock()
        client.upsert.side_effect = ConnectionError("Qdrant is unavailable")

        with self.assertLogs("db.qdrant", level="ERROR") as captured:
            await _upsert(client=client, collection_name="test_collection", points=[])

        self.assertIn("Qdrant is unavailable", "\n".join(captured.output))


if __name__ == "__main__":
    unittest.main()
