"""Chỉ số retrieval. gold = tập url đúng; got = danh sách url theo thứ tự trả về.

Tính theo tài liệu (url), không theo chunk: eval/run_retrieval.py gộp các chunk cùng url trước khi chấm.
"""


def recall_at_k(gold: set[str], got: list[str], k: int) -> float:
    """Tỉ lệ tài liệu đúng nằm trong top k (gold không được rỗng)."""
    return len(gold & set(got[:k])) / len(gold)


def hit_at_k(gold: set[str], got: list[str], k: int) -> float:
    """1.0 nếu có ít nhất một tài liệu đúng trong top k, ngược lại 0.0."""
    return float(bool(gold & set(got[:k])))


def mrr(gold: set[str], got: list[str]) -> float:
    """Nghịch đảo thứ hạng của tài liệu đúng đầu tiên (1 = đứng đầu); không có thì 0."""
    for rank, url in enumerate(got, 1):
        if url in gold:
            return 1 / rank
    return 0.0
