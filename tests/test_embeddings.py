from __future__ import annotations

import unittest
import math
from unittest.mock import patch

from config import EmbeddingsConfig
from rag.embeddings import ModelEmbeddings, SparseEmbedding
from rag.embeddings import helper
from rag.types import ChunkRecord


class FakeEmbeddings:
    """Small deterministic embedding substitute; it never contacts Ollama."""

    def __init__(self) -> None:
        self.query_calls: list[str] = []
        self.document_batches: list[list[str]] = []

    async def aembed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return [float(len(text)), 1.0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_batches.append(list(texts))
        return [[float(len(text)), 1.0] for text in texts]


def chunk(content: str, chunk_id: str = "chunk-1") -> ChunkRecord:
    return ChunkRecord(
        doc_id="doc-1",
        chunk_id=chunk_id,
        title="Fixture",
        page_content=content,
        url="https://example.com",
        category="test",
        section_path=[],
        publisher="Unit Test",
        authority="official",
        language="vi",
        region="VN",
        license="public",
        normalized_at="2026-01-01T00:00:00",
        pipeline_version="1.0.0",
    )


class ModelEmbeddingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_query_embedding_is_cached(self) -> None:
        fake = FakeEmbeddings()
        model = ModelEmbeddings(embedding_model=fake)

        first = await model.aembedding_query("xin chào")
        second = await model.aembedding_query("xin chào")

        self.assertEqual(first, [8.0, 1.0])
        self.assertEqual(second, first)
        self.assertEqual(fake.query_calls, ["xin chào"])

    async def test_query_cache_reuses_entries_and_stays_within_capacity(self) -> None:
        fake = FakeEmbeddings()
        model = ModelEmbeddings(embedding_model=fake, maxsize=2)

        await model.aembedding_query("a")
        await model.aembedding_query("b")
        await model.aembedding_query("a")
        await model.aembedding_query("c")

        self.assertEqual(fake.query_calls, ["a", "b", "c"])
        self.assertEqual(len(model._cache), 2)

    async def test_documents_are_embedded_in_requested_batch_sizes(self) -> None:
        fake = FakeEmbeddings()
        model = ModelEmbeddings(embedding_model=fake)

        vectors = await model.aembedding_documents(["a", "bb", "ccc", "dddd", "eeeee"], batch_size=2)

        self.assertEqual(fake.document_batches, [["a", "bb"], ["ccc", "dddd"], ["eeeee"]])
        self.assertEqual(vectors, [[1.0, 1.0], [2.0, 1.0], [3.0, 1.0], [4.0, 1.0], [5.0, 1.0]])

    async def test_empty_document_list_returns_empty_vectors(self) -> None:
        fake = FakeEmbeddings()
        model = ModelEmbeddings(embedding_model=fake)

        self.assertEqual(await model.aembedding_documents([]), [])
        self.assertEqual(fake.document_batches, [])

    async def test_empty_and_very_long_texts_are_forwarded_to_embedding_backend(self) -> None:
        fake = FakeEmbeddings()
        model = ModelEmbeddings(embedding_model=fake)
        long_text = "x" * 20_000

        empty_vector = await model.aembedding_query("")
        long_vectors = await model.aembedding_documents([long_text], batch_size=1)

        self.assertEqual(fake.query_calls, [""])
        self.assertEqual(fake.document_batches, [[long_text]])
        self.assertEqual(len(empty_vector), 2)
        self.assertEqual(len(long_vectors[0]), 2)

    async def test_embedding_vectors_have_consistent_dimension_float_values_and_are_finite(self) -> None:
        fake = FakeEmbeddings()
        model = ModelEmbeddings(embedding_model=fake)

        vectors = await model.aembedding_documents(["first", "second"])

        dimensions = {len(vector) for vector in vectors}
        self.assertEqual(dimensions, {2})
        self.assertTrue(all(isinstance(value, float) for vector in vectors for value in vector))
        self.assertTrue(all(math.isfinite(value) for vector in vectors for value in vector))

    async def test_batch_size_must_be_positive(self) -> None:
        model = ModelEmbeddings(embedding_model=FakeEmbeddings())

        for batch_size in (0, -1):
            with self.subTest(batch_size=batch_size):
                with self.assertRaisesRegex(ValueError, "greater than zero"):
                    await model.aembedding_documents(["text"], batch_size=batch_size)


class SparseEmbeddingTests(unittest.TestCase):
    def test_average_document_length_uses_token_counts(self) -> None:
        chunks = [chunk("ignored-1"), chunk("ignored-2", "chunk-2")]
        with patch.object(helper, "word_tokenize", side_effect=[["one", "two"], ["three", "four", "five", "six"]]):
            average = helper.search_avgdl(chunks)

        self.assertEqual(average, 3.0)

    def test_sparse_embedding_builds_one_vector_per_chunk(self) -> None:
        chunks = [chunk("first", "chunk-1"), chunk("second", "chunk-2")]
        tokens = {"first": ["a", "b"], "second": ["c", "d", "e", "f"]}
        with patch.object(helper, "word_tokenize", side_effect=lambda text: tokens[text]):
            sparse = SparseEmbedding(chunks=chunks, avg_search=True)
            vectors = sparse.build_sparses()

        self.assertEqual(len(vectors), len(chunks))
        self.assertEqual(vectors[0].indices, [helper._to_int("a"), helper._to_int("b")])
        self.assertEqual(vectors[1].indices, [helper._to_int("c"), helper._to_int("d"), helper._to_int("e"), helper._to_int("f")])

    def test_sparse_query_uses_same_tf_builder(self) -> None:
        with patch.object(helper, "word_tokenize", return_value=["học", "phí", "học"]):
            vector = SparseEmbedding.sparse_query("ignored", avgdl=100)

        self.assertEqual(vector.indices, [helper._to_int("học"), helper._to_int("phí")])
        self.assertEqual(len(vector.values), 2)

    def test_embedding_config_uses_repository_defaults(self) -> None:
        config = EmbeddingsConfig()

        self.assertEqual(config.model_provider, "ollama")
        self.assertEqual(config.model_name, "qwen3-embedding:4b")


if __name__ == "__main__":
    unittest.main()
