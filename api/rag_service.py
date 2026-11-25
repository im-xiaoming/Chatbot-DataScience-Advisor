"""Tìm kiếm thật trên Qdrant bằng code của nhóm 3 và 5 (bước "tìm kiếm" trong luồng RAG của api/main.py).

Dùng khi RETRIEVER=qdrant; cần Qdrant đang chạy và collection "QQ" đã nạp bằng pipline.py.
strategy: "hybrid" (mặc định, dense + sparse gộp RRF), "dense" hoặc "sparse" — dùng để so sánh trong eval.
Biến môi trường: EMBED_CPU (mặc định 1, xem chú thích bên dưới).
"""
from __future__ import annotations

import os

from langchain_ollama import OllamaEmbeddings
from qdrant_client import models

from config import EmbeddingsConfig
from db import create_qdrant_client
from rag.embeddings import ModelEmbeddings, SparseEmbedding
from rag.generation.types import Point
from rag.retrieval import QdrantSearch

COLLECTION = "QQ"  # trùng với --collection_name khi chạy pipline.py

# EMBED_CPU=1 (mặc định): model embedding câu hỏi chạy trên CPU với ngữ cảnh nhỏ để Ollama giữ được cả
# model embedding lẫn model chat trong bộ nhớ. Không có cờ này, GPU 4 GB không chứa nổi cả hai nên mỗi câu hỏi
# Ollama phải dỡ/nạp lại 2 model (~16 s). Vector gần như trùng bản GPU (cosine 0,998). Đặt EMBED_CPU=0 để tắt.
_cfg = EmbeddingsConfig()
if os.getenv("EMBED_CPU", "1") == "1" and _cfg.model_provider == "ollama":
    embedder = ModelEmbeddings(embedding_model=OllamaEmbeddings(model=_cfg.model_name, num_gpu=0, num_ctx=512))
else:
    embedder = ModelEmbeddings(config=_cfg)
# Truyền hàm tạo client (không phải client): lớp QdrantModel của nhóm tự gọi hàm này khi tìm kiếm lần đầu.
# mypy báo sai kiểu ở dòng này vì QdrantSearch khai báo collection_name: int và client chỉ nhận AsyncQdrantClient
# (lỗi khai báo kiểu trong rag/retrieval, đã ghi ở eval/BUGS_FOR_TEAM.md).
searcher = QdrantSearch(collection_name=COLLECTION, client=create_qdrant_client)


def _category_filter(category: str | None) -> models.Filter | None:
    """Bộ lọc Qdrant theo payload "category"; None = không lọc."""
    if not category:
        return None
    return models.Filter(must=[models.FieldCondition(key="category", match=models.MatchValue(value=category))])


async def retrieve(question: str, category: str | None = None, k: int = 5, strategy: str = "hybrid") -> list[Point]:
    """Tìm k chunk liên quan nhất tới câu hỏi.

    Args:
        question: câu tìm kiếm (đã qua Generator.search_query).
        category: chỉ tìm trong một loại tài liệu (curriculum, regulation, ...); None = tất cả.
        k: số chunk trả về. API dùng TOP_K=8 (xem api/main.py).
        strategy: "hybrid" | "dense" | "sparse".

    Returns:
        Payload của từng chunk kèm "score", theo thứ tự điểm giảm dần.

    Raises:
        ValueError: strategy không hợp lệ.
        RuntimeError: QdrantSearch trả None (nó nuốt lỗi kết nối và chỉ ghi log).
    """
    flt = _category_filter(category)
    sparse = SparseEmbedding.sparse_query(question)
    if strategy == "hybrid":
        res = await searcher.hybrid_search(
            query_vector=await embedder.aembedding_query(question), sparse_vector=sparse,
            limit=k, dense_filter=flt, sparse_filter=flt,
        )
    elif strategy == "dense":
        res = await searcher.search(query_vector=await embedder.aembedding_query(question),
                                    query_filter=flt, limit=k, mode="dense")
    elif strategy == "sparse":
        # QdrantSearch.search bắt buộc có query_vector; ở chế độ sparse nó chỉ dùng sparse_vector
        res = await searcher.search(query_vector=sparse, sparse_vector=sparse,
                                    query_filter=flt, limit=k, mode="sparse")
    else:
        raise ValueError(f"strategy không hợp lệ: {strategy}")
    if res is None:  # QdrantSearch nuốt lỗi và trả None
        raise RuntimeError("Qdrant search thất bại, xem log của rag.retrieval")
    return [{**p.payload, "score": p.score} for p in res.points]  # type: ignore[typeddict-item]  # payload Qdrant là dict tuỳ ý, đúng khoá của Point do pipline.py nạp
