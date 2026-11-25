from api.rerank import Reranker


def overlap_scorer(pairs):
    """Điểm = số từ chung giữa câu hỏi và đoạn văn (thay cho cross-encoder thật)."""
    return [len(set(q.split()) & set(d.split())) for q, d in pairs]


def test_rerank_orders_by_score_and_keeps_top_k():
    pts = [{"page_content": "học bổng", "score": 0.9}, {"page_content": "buộc thôi học", "score": 0.1},
           {"page_content": "thôi học khi bỏ học", "score": 0.5}]
    out = Reranker(scorer=overlap_scorer, batch_size=2).rerank("bị buộc thôi học", pts, top_k=2)
    assert [p["page_content"] for p in out] == ["buộc thôi học", "thôi học khi bỏ học"]
    assert out[0]["retrieval_score"] == 0.1 and out[0]["score"] == 3


def test_rerank_empty():
    assert Reranker(scorer=overlap_scorer).rerank("q", [], 5) == []


def test_scorer_loaded_lazily():
    r = Reranker()
    assert r._scorer is None  # không tải model khi chỉ khởi tạo
