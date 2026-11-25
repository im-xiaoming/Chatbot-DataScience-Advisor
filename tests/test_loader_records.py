from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from langchain_core.documents import Document

from config import RecursiveCharacterTextSplitterConfig
from rag.ingestion.loaders import Record, Splitter
from rag.types import ChunkRecord, DocRecord


def metadata() -> dict:
    return {
        "doc_id": "doc-1",
        "chunk_id": "doc-1+000000000000001",
        "title": "Tài liệu mẫu",
        "url": "https://example.com",
        "category": "test",
        "section_path": ["Mục 1"],
        "publisher": "Unit Test",
        "authority": "official",
        "language": "vi",
        "region": "VN",
        "license": "public",
        "normalized_at": "2026-01-01T00:00:00",
        "pipeline_version": "1.0.0",
    }


class SplitterEdgeCaseTests(unittest.TestCase):
    def test_missing_file_returns_no_documents_or_chunks(self) -> None:
        splitter = Splitter(recursive_config=RecursiveCharacterTextSplitterConfig())

        with tempfile.TemporaryDirectory() as directory:
            with self.assertLogs("root", level="ERROR") as captured:
                documents, chunks = splitter.split_document(str(Path(directory) / "missing.md"))

        self.assertEqual(documents, [])
        self.assertEqual(chunks, [])
        self.assertIn("Failed to load file", captured.output[0])

    def test_empty_file_returns_no_documents_or_chunks(self) -> None:
        splitter = Splitter(recursive_config=RecursiveCharacterTextSplitterConfig())

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.md"
            path.write_text("  \n", encoding="utf-8")
            documents, chunks = splitter.split_document(str(path))

        self.assertEqual(documents, [])
        self.assertEqual(chunks, [])

    def test_split_documents_walks_nested_markdown_and_skips_other_extensions(self) -> None:
        markdown = """title: Nested sample
url: https://example.com
category: test
publisher: Unit Test
authority: official
language: vi
region: VN
license: public
normalized_at: 2026-01-01T00:00:00
pipeline_version: 1.0.0
---
# Body
Nội dung đủ dài để tạo một chunk trong bài kiểm thử này.
"""
        splitter = Splitter(recursive_config=RecursiveCharacterTextSplitterConfig())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()
            (nested / "sample.md").write_text(markdown, encoding="utf-8")
            (nested / "ignored.txt").write_text(markdown, encoding="utf-8")

            documents, chunks = splitter.split_documents(str(root))

        self.assertEqual(len(documents), 1)
        self.assertGreaterEqual(len(chunks), 1)
        self.assertEqual(documents[0].metadata["title"], "Nested sample")


class RecordConversionTests(unittest.TestCase):
    def test_build_doc_records_preserves_content_and_metadata(self) -> None:
        data = metadata()
        data.pop("chunk_id")
        document = Document(page_content="Nội dung của tài liệu", metadata=data)

        records = Record.build_doc_records([document])

        self.assertEqual(len(records), 1)
        self.assertIsInstance(records[0], DocRecord)
        self.assertEqual(records[0].doc_id, "doc-1")
        self.assertEqual(records[0].page_content, "Nội dung của tài liệu")
        self.assertEqual(records[0].section_path, ["Mục 1"])

    def test_build_chunk_records_preserves_content_and_chunk_metadata(self) -> None:
        document = Document(page_content="Nội dung đoạn", metadata=metadata())

        records = Record.build_chunk_records([document])

        self.assertEqual(len(records), 1)
        self.assertIsInstance(records[0].data, ChunkRecord)
        self.assertEqual(records[0].data.chunk_id, "doc-1+000000000000001")
        self.assertEqual(records.tolist(), ["Nội dung đoạn"])

    def test_record_list_empty_operations_return_empty_lists(self) -> None:
        from rag.ingestion.loaders import RecordList

        records = RecordList()

        self.assertEqual(records.tolist(), [])
        self.assertEqual(records.model_dump(), [])


if __name__ == "__main__":
    unittest.main()
