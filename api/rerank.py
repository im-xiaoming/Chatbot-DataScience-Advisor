"""Sắp xếp lại kết quả tìm kiếm bằng cross-encoder của nhóm 3 (rag/rerank/CrossEncoder, BAAI/bge-reranker-v2-m3).

Bật bằng RERANK=1: API lấy 2 x TOP_K chunk, rerank rồi giữ TOP_K. Lần đầu sẽ tải model (~2 GB) từ Hugging Face.
Nằm giữa bước tìm kiếm và Generator.select_points trong api/main.py; eval/run_retrieval.py --rerank cũng dùng.

Lưu ý: import thẳng CrossEncoderConfig từ config.config vì config/__init__.py của nhóm chưa export lớp này
(đã báo trong eval/BUGS_FOR_TEAM.md); khi nhóm export rồi có thể đổi lại thành `from config import ...`.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

from rag.generation.types import Point

Scorer = Callable[[list[tuple[str, str]]], Sequence[float]]  # (câu hỏi, nội dung chunk) -> điểm liên quan


def _team_cross_encoder() -> Scorer:
    """Tải cross-encoder của nhóm (import trễ vì kéo theo torch, ~1,5 GB bộ nhớ)."""
    from config.config import CrossEncoderConfig
    from rag.rerank import CrossEncoder
    model = CrossEncoder(CrossEncoderConfig())
    return lambda pairs: model(pairs).tolist()


class Reranker:
    """Chấm lại điểm (câu hỏi, chunk) bằng cross-encoder và giữ top_k.

    Args:
        scorer: hàm chấm điểm; None = dùng cross-encoder của nhóm, tải ở lần rerank đầu tiên.
            Test truyền hàm giả để không phải tải model.
        batch_size: số cặp (câu hỏi, chunk) chấm trong một lần gọi model.
    """

    def __init__(self, scorer: Scorer | None = None, batch_size: int = 8) -> None:
        self._scorer = scorer
        self.batch_size = batch_size

    @property
    def scorer(self) -> Scorer:
        """Hàm chấm điểm; tải model khi dùng lần đầu."""
        if self._scorer is None:  # tải model khi dùng lần đầu
            self._scorer = _team_cross_encoder()
        return self._scorer

    def rerank(self, query: str, points: list[Point], top_k: int) -> list[Point]:
        """Sắp xếp points theo điểm cross-encoder giảm dần, giữ top_k.

        Returns:
            Bản sao các chunk với "score" = điểm rerank (4 chữ số) và "retrieval_score" = điểm tìm kiếm gốc.
        """
        if not points:
            return []
        pairs = [(query, p.get("page_content", "")) for p in points]
        scores: list[float] = []
        for i in range(0, len(pairs), self.batch_size):
            scores.extend(float(s) for s in self.scorer(pairs[i:i + self.batch_size]))
        ranked = sorted(zip(points, scores), key=lambda x: x[1], reverse=True)[:top_k]
        return [{**p, "retrieval_score": p.get("score"), "score": round(s, 4)} for p, s in ranked]
