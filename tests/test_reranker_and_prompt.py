from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import torch

from agent.prompt import CONTEXT_SYSTEM_PROMPT, CONTEXT_USER_PROMPT
from rag.rerank import CrossEncoder


class FakeBatch(dict):
    def to(self, device):
        self.device = device
        return self


class FakeTokenizer:
    def __init__(self) -> None:
        self.received_pairs = None
        self.options = None

    def __call__(self, pairs, **kwargs):
        self.received_pairs = pairs
        self.options = kwargs
        return FakeBatch(input_ids=torch.tensor([[1], [2], [3]]))


class FakeSequenceModel:
    def __call__(self, **kwargs):
        return SimpleNamespace(logits=torch.tensor([[0.0], [1.0], [-1.0]]))


class FakeEmptySequenceModel:
    def __call__(self, **kwargs):
        return SimpleNamespace(logits=torch.empty((0, 1)))


class CrossEncoderTests(unittest.TestCase):
    def test_reranker_returns_one_finite_score_per_pair_in_input_order(self) -> None:
        tokenizer = FakeTokenizer()
        model = FakeSequenceModel()
        pairs = [
            ("điều kiện môn A", "môn A cần học trước"),
            ("học kỳ một", "kế hoạch năm nhất"),
            ("học phí", "quy định học bổng"),
        ]
        with (
            patch("rag.rerank.cross_encoder.load_cross_encoder_model", return_value=(tokenizer, model)),
            patch("rag.rerank.cross_encoder.torch.cuda.is_available", return_value=False),
        ):
            reranker = CrossEncoder(SimpleNamespace(model_name="test-reranker"), device="cpu")
            scores = reranker(pairs)

        self.assertEqual(scores.shape, (3,))
        self.assertTrue(torch.isfinite(scores).all().item())
        self.assertAlmostEqual(scores[0].item(), 0.5)
        self.assertGreater(scores[1].item(), scores[0].item())
        self.assertLess(scores[2].item(), scores[0].item())
        self.assertEqual(tokenizer.received_pairs, pairs)
        self.assertTrue(tokenizer.options["truncation"])
        self.assertEqual(tokenizer.options["max_length"], 512)

    def test_reranker_handles_empty_pair_list(self) -> None:
        tokenizer = FakeTokenizer()
        with (
            patch(
                "rag.rerank.cross_encoder.load_cross_encoder_model",
                return_value=(tokenizer, FakeEmptySequenceModel()),
            ),
            patch("rag.rerank.cross_encoder.torch.cuda.is_available", return_value=False),
        ):
            reranker = CrossEncoder(SimpleNamespace(model_name="test-reranker"), device="cpu")
            scores = reranker([])

        self.assertEqual(scores.numel(), 0)


class PromptTemplateTests(unittest.TestCase):
    def test_user_prompt_inserts_document_and_chunk_without_losing_text(self) -> None:
        document = "Tài liệu gốc về chương trình đào tạo"
        chunk = "Điều kiện tiên quyết là môn Cơ sở dữ liệu."

        prompt = CONTEXT_USER_PROMPT.format(document=document, chunk=chunk)

        self.assertIn(f"<document>\n{document}\n</document>", prompt)
        self.assertIn(f"<chunk>\n{chunk}\n</chunk>", prompt)

    def test_prompt_template_reports_missing_required_placeholder(self) -> None:
        with self.assertRaises(KeyError):
            CONTEXT_USER_PROMPT.format(document="Tài liệu")

    def test_system_prompt_has_word_limit_and_no_fabrication_instruction(self) -> None:
        self.assertIn("512", CONTEXT_SYSTEM_PROMPT)
        self.assertIn("DOCUMENT", CONTEXT_SYSTEM_PROMPT)
        self.assertIn("CHUNK", CONTEXT_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
