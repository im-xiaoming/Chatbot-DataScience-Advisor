from __future__ import annotations

import unittest

from langchain_core.documents import Document
from pydantic import ValidationError

from config import RecursiveCharacterTextSplitterConfig
from rag.ingestion.loaders import Splitter
from rag.types import ChunkRecord, DocRecord


def record_fields() -> dict:
    return {
        "doc_id": "doc-1",
        "chunk_id": "doc-1+000000000000001",
        "title": "Kế hoạch học tập",
        "page_content": "Thông tin học tập",
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


class ChunkingBehaviorTests(unittest.TestCase):
    def test_chunk_length_never_exceeds_configured_limit(self) -> None:
        splitter = Splitter(
            recursive_config=RecursiveCharacterTextSplitterConfig(chunk_size=10, chunk_overlap=3)
        )
        source = Document(page_content="abcdefghijklmnopqrstuvwxyz", metadata={"source": "fixture"})

        chunks = splitter._recursive_character_splitter([source])

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk.page_content) <= 10 for chunk in chunks))

    def test_character_fallback_keeps_configured_overlap(self) -> None:
        splitter = Splitter(
            recursive_config=RecursiveCharacterTextSplitterConfig(chunk_size=10, chunk_overlap=3)
        )
        source = Document(page_content="abcdefghijklmnopqrstuvwxyz")

        chunks = splitter._recursive_character_splitter([source])

        for previous, current in zip(chunks, chunks[1:]):
            self.assertEqual(previous.page_content[-3:], current.page_content[:3])

    def test_split_chunks_retain_document_metadata(self) -> None:
        metadata = {
            "subject_code": "DS101",
            "semester": 1,
            "target_year": 1,
            "source": "curriculum.pdf",
        }
        splitter = Splitter(
            recursive_config=RecursiveCharacterTextSplitterConfig(chunk_size=12, chunk_overlap=2)
        )

        chunks = splitter._recursive_character_splitter(
            [Document(page_content="Nội dung môn học và điều kiện tiên quyết.", metadata=metadata)]
        )

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            with self.subTest(content=chunk.page_content):
                self.assertEqual(chunk.metadata, metadata)

    def test_recursive_splitter_prefers_sentence_boundary_when_possible(self) -> None:
        splitter = Splitter(
            recursive_config=RecursiveCharacterTextSplitterConfig(chunk_size=38, chunk_overlap=0)
        )
        source = Document(page_content="Môn A là cơ sở. Môn B yêu cầu học Môn A trước.")

        chunks = splitter._recursive_character_splitter([source])

        self.assertGreater(len(chunks), 1)
        self.assertIn("Môn A là cơ sở", chunks[0].page_content)
        self.assertIn("Môn B yêu cầu học Môn A trước.", chunks[-1].page_content)


class RecordSchemaTests(unittest.TestCase):
    def test_chunk_record_accepts_valid_record_and_parses_datetime(self) -> None:
        record = ChunkRecord(**record_fields())

        self.assertEqual(record.doc_id, "doc-1")
        self.assertEqual(record.normalized_at.isoformat(), "2026-01-01T00:00:00")
        self.assertEqual(record.section_path, ["Năm nhất", "Học kỳ 1"])

    def test_doc_record_ignores_chunk_only_fields(self) -> None:
        fields = record_fields()
        fields.pop("chunk_id")
        record = DocRecord(**fields)

        self.assertEqual(record.doc_id, "doc-1")
        self.assertFalse(hasattr(record, "chunk_id"))

    def test_required_fields_are_validated(self) -> None:
        fields = record_fields()
        fields.pop("title")

        with self.assertRaises(ValidationError):
            ChunkRecord(**fields)

    def test_wrong_metadata_types_are_rejected(self) -> None:
        cases = [
            ("section_path", "not-a-list"),
            ("normalized_at", "not-a-date"),
        ]
        for field, invalid_value in cases:
            with self.subTest(field=field):
                fields = record_fields()
                fields[field] = invalid_value
                with self.assertRaises(ValidationError):
                    ChunkRecord(**fields)

    def test_optional_dates_accept_none(self) -> None:
        fields = record_fields()
        fields.update(published_date=None, valid_until=None, fetched_at=None)

        record = ChunkRecord(**fields)

        self.assertIsNone(record.published_date)
        self.assertIsNone(record.valid_until)
        self.assertIsNone(record.fetched_at)


if __name__ == "__main__":
    unittest.main()
