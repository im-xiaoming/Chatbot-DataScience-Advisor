from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document
from qdrant_client import models

from common import _encode_string
from common.common import _NAMESPACE
from config import RecursiveCharacterTextSplitterConfig
from rag.embeddings import helper
from rag.ingestion.indexer import QdrantIndexer, _create_point_id
from rag.ingestion.loaders import (
    Record,
    RecordList,
    Splitter,
    _build_section_path,
    _content_standardized,
    _to_json,
)
from rag.types import ChunkRecord


class MetadataHelpersTests(unittest.TestCase):
    def test_to_json_reads_metadata_and_removes_single_quotes(self) -> None:
        result = _to_json("title: 'Tài liệu mẫu'\nurl: https://example.com\npriority: 1")

        self.assertEqual(result["title"], "Tài liệu mẫu")
        self.assertEqual(result["url"], "https://example.com")
        self.assertEqual(result["priority"], "1")

    def test_content_standardized_removes_html_comment_markers(self) -> None:
        result = _content_standardized("  Nội dung <!-- page 12 --> cần giữ.  ")

        self.assertEqual(result, "Nội dung  cần giữ.")

    def test_build_section_path_carries_parent_heading(self) -> None:
        docs = [
            Document(page_content="A", metadata={"Header 1": "Chương A"}),
            Document(page_content="B", metadata={"Header 2": "Mục B"}),
        ]

        result = _build_section_path(docs)

        self.assertEqual(result[0].metadata["section_path"], ["Chương A"])
        self.assertEqual(result[1].metadata["section_path"], ["Chương A", "Mục B"])


class SplitterTests(unittest.TestCase):
    def test_split_document_builds_document_and_stable_chunk_ids(self) -> None:
        markdown = """title: Tài liệu thử
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
# Chương một
Đây là đoạn nội dung đầu tiên, có đủ chữ để kiểm tra cách chia tài liệu thành các đoạn nhỏ.
## Mục con
Đây là nội dung thứ hai và cũng đủ dài để bộ chia xử lý ổn định trong bài kiểm thử.
"""
        splitter = Splitter(
            recursive_config=RecursiveCharacterTextSplitterConfig(
                chunk_size=40,
                chunk_overlap=5,
            )
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.md"
            path.write_text(markdown, encoding="utf-8")
            documents, chunks = splitter.split_document(str(path))

        self.assertEqual(len(documents), 1)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(documents[0].metadata["title"], "Tài liệu thử")
        self.assertTrue(all(chunk.metadata["doc_id"] for chunk in chunks))
        self.assertEqual(
            [chunk.metadata["chunk_id"] for chunk in chunks],
            sorted(chunk.metadata["chunk_id"] for chunk in chunks),
        )


class StableIdTests(unittest.TestCase):
    def test_encode_string_is_deterministic_and_input_sensitive(self) -> None:
        self.assertEqual(_encode_string("tiêu đề"), _encode_string("tiêu đề"))
        self.assertNotEqual(_encode_string("tiêu đề"), _encode_string("tiêu đề khác"))

    def test_point_id_is_deterministic_and_uses_project_namespace(self) -> None:
        chunk_id = "doc+000000000000001"
        content = "Nội dung đoạn"

        point_id = _create_point_id(chunk_id, content)

        self.assertEqual(point_id, _create_point_id(chunk_id, content))
        self.assertEqual(
            point_id,
            uuid.uuid5(uuid.UUID(_NAMESPACE), (chunk_id + content).encode("utf-8")),
        )


class SparseVectorTests(unittest.TestCase):
    def test_tf_aggregates_repeated_tokens(self) -> None:
        with patch.object(helper, "word_tokenize", return_value=["xin", "xin", "chao"]):
            vector = helper._TF("ignored", avgdl=3)

        expected_indices = [helper._to_int("xin"), helper._to_int("chao")]
        expected_values = [
            (2 * 2.25) / (2 + 1.25 * (1 - 0.75 + 0.75 * 3 / 3)),
            (1 * 2.25) / (1 + 1.25 * (1 - 0.75 + 0.75 * 3 / 3)),
        ]
        self.assertEqual(vector.indices, expected_indices)
        for actual, expected in zip(vector.values, expected_values, strict=True):
            self.assertAlmostEqual(actual, expected)


def make_chunk_record() -> ChunkRecord:
    return ChunkRecord(
        doc_id="doc-1",
        chunk_id="doc-1+000000000000001",
        title="Tài liệu thử",
        page_content="Nội dung đoạn",
        url="https://example.com",
        category="test",
        section_path=["Mục 1"],
        publisher="Unit Test",
        authority="official",
        language="vi",
        region="VN",
        license="public",
        normalized_at="2026-01-01T00:00:00",
        pipeline_version="1.0.0",
    )


class IndexerTests(unittest.TestCase):
    def test_build_points_keeps_vectors_and_payload(self) -> None:
        record = make_chunk_record()
        sparse = models.SparseVector(indices=[1], values=[0.5])

        points = QdrantIndexer.build_points(
            records=[record],
            embeddings=[[0.1, 0.2, 0.3]],
            sparse_vector=[sparse],
        )

        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].id, _create_point_id(record.chunk_id, record.page_content))
        self.assertEqual(points[0].vector["dense"], [0.1, 0.2, 0.3])
        self.assertEqual(points[0].vector["sparse"], sparse)
        self.assertEqual(points[0].payload["chunk_id"], record.chunk_id)

    def test_build_points_rejects_mismatched_input_lengths(self) -> None:
        record = make_chunk_record()
        sparse = models.SparseVector(indices=[1], values=[0.5])

        with self.assertRaises(ValueError):
            QdrantIndexer.build_points(
                records=[record],
                embeddings=[],
                sparse_vector=[sparse],
            )


class RecordListTests(unittest.TestCase):
    def test_build_chunk_records_exposes_dumped_records(self) -> None:
        documents = [Document(page_content="Nội dung", metadata=make_chunk_record().model_dump())]

        records = Record.build_chunk_records(documents)

        self.assertEqual(records.tolist(), ["Nội dung"])
        dumped = records.model_dump()
        self.assertIsInstance(dumped[0], ChunkRecord)
        self.assertEqual(dumped[0].chunk_id, "doc-1+000000000000001")


if __name__ == "__main__":
    unittest.main()
