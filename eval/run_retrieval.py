"""So sánh các cách tìm kiếm trên bộ câu hỏi (chỉ câu trong phạm vi dữ liệu).

Chạy:
  uv run python -m eval.run_retrieval                                   # tìm kiếm giả (từ khoá), làm mốc
  uv run python -m eval.run_retrieval --mode qdrant --strategies dense,sparse,hybrid --rerank
Chỉ số: Hit@k (có ít nhất 1 tài liệu đúng trong top k), Recall@k, MRR, tính theo url tài liệu.
Kết quả lưu ở eval/out/retrieval-<mode>.json; chạy eval.report để gộp thành bảng.
Câu hỏi được ghép mục tiêu nghề nghiệp "(goal)" như Generator.search_query làm, nhưng không qua bước viết lại.
--mode qdrant cần Qdrant đang chạy; embedding câu hỏi theo EMBED_CPU như API (xem api/rag_service.py).
"""
from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from statistics import mean
from typing import TYPE_CHECKING, Any

from eval.common import load_qa, save_json
from eval.metrics import hit_at_k, mrr, recall_at_k

if TYPE_CHECKING:
    from eval.types import QARow
    from rag.generation.types import Point

    Strategy = Callable[[str, int], Coroutine[Any, Any, list[Point]]]  # (câu hỏi, k) -> chunk theo thứ tự

KS = (1, 3, 5)


def score(rows: list[QARow], ranked: dict[str, list[str]]) -> dict[str, Any]:
    """Tính Hit@1/3/5, Recall@5, MRR cho toàn bộ và theo chức năng, kèm danh sách câu trượt top 5.

    Args:
        rows: các câu trong phạm vi.
        ranked: id câu -> url tài liệu theo thứ hạng (đã gộp trùng bằng dedupe).
    """
    def agg(rs: list[QARow]) -> dict[str, Any]:
        out: dict[str, Any] = {"n": len(rs)}
        for k in KS:
            out[f"hit@{k}"] = round(mean(hit_at_k(set(r["gold_urls"]), ranked[r["id"]], k) for r in rs), 3)
        out["recall@5"] = round(mean(recall_at_k(set(r["gold_urls"]), ranked[r["id"]], 5) for r in rs), 3)
        out["mrr"] = round(mean(mrr(set(r["gold_urls"]), ranked[r["id"]]) for r in rs), 3)
        return out

    by_fn = defaultdict(list)
    for r in rows:
        by_fn[r["function"]].append(r)
    return {"overall": agg(rows), "by_function": {f: agg(rs) for f, rs in sorted(by_fn.items())},
            "misses": [r["id"] for r in rows if not hit_at_k(set(r["gold_urls"]), ranked[r["id"]], 5)]}


def dedupe(urls: list[str]) -> list[str]:
    """Nhiều chunk cùng một tài liệu -> giữ thứ hạng đầu tiên của tài liệu đó."""
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


async def main() -> None:
    """Đọc tham số, chạy từng cách tìm trên mọi câu trong phạm vi, in bảng và lưu JSON."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["fake", "qdrant"], default="fake")
    ap.add_argument("--strategies", default="hybrid", help="qdrant: dense,sparse,hybrid")
    ap.add_argument("--qa", default="eval/qa.jsonl")
    ap.add_argument("--k", type=int, default=10, help="số chunk lấy về trước khi gộp theo tài liệu")
    ap.add_argument("--rerank", action="store_true", help="thêm phiên bản +rerank cho mỗi cách tìm (lấy 2k rồi rerank)")
    a = ap.parse_args()

    rows = [r for r in load_qa(a.qa) if r["in_scope"]]
    if a.mode == "fake":
        from api.fake import fake_retrieve
        strategies: dict[str, Strategy] = {"keyword (giả)": lambda q, k: fake_retrieve(q, k=k)}
    else:
        from api.rag_service import retrieve
        strategies = {s: (lambda q, k, s=s: retrieve(q, k=k, strategy=s)) for s in a.strategies.split(",")}  # type: ignore[misc]  # s=s giữ giá trị s của từng vòng; mypy không suy được kiểu lambda có tham số mặc định

    if a.rerank:
        from rag.rerank import Reranker
        rr = Reranker()
        for name, fn in list(strategies.items()):
            async def reranked(q: str, k: int, fn: Strategy = fn) -> list[Point]:
                return rr.rerank(q, await fn(q, 2 * k), k)
            strategies[f"{name} + rerank"] = reranked

    results: dict[str, dict[str, Any]] = {}
    for name, fn in strategies.items():
        ranked = {}
        for r in rows:
            q = r["question"] + (f" ({r['goal']})" if r.get("goal") else "")
            ranked[r["id"]] = dedupe([p["url"] for p in await fn(q, a.k)])
        results[name] = score(rows, ranked)
        o = results[name]["overall"]
        print(f"{name:16s} n={o['n']}  Hit@1={o['hit@1']:.2f}  Hit@3={o['hit@3']:.2f}  Hit@5={o['hit@5']:.2f}  "
              f"Recall@5={o['recall@5']:.2f}  MRR={o['mrr']:.2f}")
        if results[name]["misses"]:
            print("   trượt top 5:", ", ".join(results[name]["misses"]))
    path = save_json(f"retrieval-{a.mode}.json", {"config": vars(a), "results": results})
    print("Đã lưu", path)


if __name__ == "__main__":
    asyncio.run(main())
