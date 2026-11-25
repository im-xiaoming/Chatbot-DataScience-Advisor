from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock

from rag.types import ChunkRecord, DocRecord
from db.qdrant_db.models import ModelChunk, ModelDoc
from db.qdrant_db.queries import ChunkQuery, DocumentQuery


def make_doc() -> DocRecord:
    return DocRecord(
        doc_id="doc-1",
        title="Tài liệu mẫu",
        page_content="Nội dung tài liệu",
        url="https://example.com",
        category="curriculum",
        section_path=["Năm nhất"],
        publisher="IUH",
        authority="official",
        language="vi",
        region="VN",
        license="public",
        normalized_at="2026-01-01T00:00:00",
        pipeline_version="1.0.0",
    )


def make_chunk() -> ChunkRecord:
    return ChunkRecord(
        doc_id="doc-1",
        chunk_id="doc-1+000000000000001",
        title="Tài liệu mẫu",
        page_content="Nội dung đoạn",
        url="https://example.com",
        category="curriculum",
        section_path=["Năm nhất", "Học kỳ 1"],
        publisher="IUH",
        authority="official",
        language="vi",
        region="VN",
        license="public",
        normalized_at="2026-01-01T00:00:00",
        pipeline_version="1.0.0",
    )


def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = Mock()
    return session


class DocumentQueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_insert_new_document_adds_and_flushes_model(self) -> None:
        session = mock_session()
        session.get.return_value = None
        query = DocumentQuery(session)

        result = await query.insert(make_doc())

        self.assertIsInstance(result, ModelDoc)
        self.assertEqual(result.doc_id, "doc-1")
        session.add.assert_called_once()
        self.assertIsInstance(session.add.call_args.args[0], ModelDoc)
        session.flush.assert_awaited_once()

    async def test_insert_existing_document_updates_it(self) -> None:
        session = mock_session()
        session.get.return_value = ModelDoc(doc_id="doc-1")
        query = DocumentQuery(session)

        result = await query.insert(make_doc())

        self.assertIsNone(result)
        session.execute.assert_awaited_once()
        session.add.assert_not_called()

    async def test_get_by_id_returns_session_scalar_result(self) -> None:
        session = mock_session()
        expected = ModelDoc(doc_id="doc-1")
        session.scalar.return_value = expected
        query = DocumentQuery(session)

        result = await query.get_by_id("doc-1")

        self.assertIs(result, expected)
        session.scalar.assert_awaited_once()

    async def test_insert_rolls_back_and_raises_if_flush_fails(self) -> None:
        session = mock_session()
        session.get.return_value = None
        session.flush.side_effect = RuntimeError("flush failed")
        query = DocumentQuery(session)

        with self.assertRaisesRegex(RuntimeError, "flush failed"):
            await query.insert(make_doc())

        session.rollback.assert_awaited_once()


class ChunkQueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_insert_new_chunk_adds_and_flushes_model(self) -> None:
        session = mock_session()
        session.get.return_value = None
        query = ChunkQuery(session)

        result = await query.insert(make_chunk())

        self.assertIsInstance(result, ModelChunk)
        self.assertEqual(result.chunk_id, "doc-1+000000000000001")
        session.add.assert_called_once()
        self.assertIsInstance(session.add.call_args.args[0], ModelChunk)
        session.flush.assert_awaited_once()

    async def test_insert_existing_chunk_updates_it(self) -> None:
        session = mock_session()
        session.get.return_value = ModelChunk(chunk_id="doc-1+000000000000001")
        query = ChunkQuery(session)

        result = await query.insert(make_chunk())

        self.assertIsNone(result)
        session.execute.assert_awaited_once()
        session.add.assert_not_called()

    async def test_get_by_id_returns_session_scalar_result(self) -> None:
        session = mock_session()
        expected = ModelChunk(chunk_id="doc-1+000000000000001")
        session.scalar.return_value = expected
        query = ChunkQuery(session)

        result = await query.get_by_id("doc-1+000000000000001")

        self.assertIs(result, expected)
        session.scalar.assert_awaited_once()

    async def test_update_rolls_back_and_raises_if_database_fails(self) -> None:
        session = mock_session()
        session.execute.side_effect = RuntimeError("database unavailable")
        query = ChunkQuery(session)

        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            await query.update("doc-1+000000000000001", make_chunk())

        session.rollback.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
