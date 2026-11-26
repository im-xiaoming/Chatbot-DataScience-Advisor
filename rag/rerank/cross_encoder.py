"""Cross-encoder chấm điểm liên quan của cặp (câu hỏi, đoạn văn); model mặc định BAAI/bge-reranker-v2-m3
(config.CrossEncoderConfig). Sắp xếp và giữ top_k nằm ở rag/rerank/reranker.py.
"""
from __future__ import annotations

import torch
from qdrant_client import models
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from rag.types import QueryPoint


def load_cross_encoder_model(model_name: str, device: torch.device):
    """Tải tokenizer và model từ Hugging Face (lần đầu ~2 GB), chuyển model sang device, để ở chế độ eval."""
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name).to(device)
    model.eval()
    return tokenizer, model


class CrossEncoder:
    """Chấm điểm cặp (câu hỏi, đoạn văn) bằng cross-encoder.

    Args:
        config: có thuộc tính model_name (config.CrossEncoderConfig).
        device: "cuda" hoặc "cpu"; không có GPU thì tự dùng CPU.
    """

    def __init__(self, config, device: str = 'cuda') -> None:
        self.device = torch.device(device if torch.cuda.is_available() else 'cpu')
        self.tokenizer, self.model = load_cross_encoder_model(config.model_name, self.device)

    def __call__(self, pairs: list[tuple[str, str]]) -> torch.Tensor:
        """Điểm sigmoid trong (0, 1) cho từng cặp, đúng thứ tự đầu vào; danh sách rỗng -> tensor rỗng.

        Chạy đồng bộ (nặng CPU/GPU): code async nên gọi qua asyncio.to_thread.
        """
        if not pairs:
            return torch.empty(0)
        inputs = self.tokenizer(pairs, padding=True, truncation=True, return_tensors='pt',
                                max_length=512).to(self.device)
        with torch.no_grad():
            scores = self.model(**inputs, return_dict=True).logits.view(-1).float().sigmoid()
        return scores.cpu()


def format_query(points: list[models.ScoredPoint]) -> list[QueryPoint]:
    """Đổi kết quả tìm kiếm của Qdrant thành QueryPoint (id, version, score + payload)."""
    return [QueryPoint(point_id=str(p.id), version=p.version, score=p.score, **(p.payload or {})) for p in points]
