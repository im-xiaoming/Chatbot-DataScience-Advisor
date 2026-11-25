"""Chấm lại kết quả đã lưu (eval/out/**/answers-*.jsonl) bằng code chấm hiện tại, không cần chạy lại LLM.

Dùng khi sửa cách chấm (ví dụ is_refusal) mà không muốn chạy lại 2 tiếng.
Chạy: uv run python -m eval.rescore eval/out/v148/answers-qdrant-ollama.jsonl [file khác ...]
Ghi <tên file>.rescored.summary.json cạnh file gốc và in bảng so sánh trước/sau.
Chỉ chấm lại refusal/refusal_ok; các chỉ số khác (recall, giám khảo...) giữ nguyên như lúc chạy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from eval.common import is_refusal
from eval.run_answers import summarize

if TYPE_CHECKING:
    from eval.types import AnswerResult

KEYS = ["answered_in_scope", "refused_out_of_scope", "key_fact_recall", "correctness", "faithfulness"]


def rescore(rows: list[AnswerResult]) -> list[AnswerResult]:
    """Bản sao các dòng với refusal và refusal_ok tính lại bằng is_refusal hiện tại."""
    out: list[AnswerResult] = []
    for r in rows:
        ref = is_refusal(r["answer"])
        out.append({**r, "refusal": ref, "refusal_ok": ref if not r["in_scope"] else not ref})
    return out


def main(paths: list[str]) -> None:
    """Chấm lại từng file, ghi summary mới cạnh file gốc, in chỉ số trước -> sau và các câu đổi kết luận."""
    for p in map(Path, paths):
        rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
        old, new = summarize(rows)["overall"], summarize(rescore(rows))
        out = p.with_name(p.name.replace(".jsonl", ".rescored.summary.json"))
        out.write_text(json.dumps({"source": str(p), "summary": new}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"== {p} ({len(rows)} câu) -> {out.name}")
        for k in KEYS:
            if k in old:
                print(f"  {k:22s} {old[k]} -> {new['overall'][k]}")
        flips = [r["id"] for r, n in zip(rows, rescore(rows)) if r["refusal_ok"] != n["refusal_ok"]]
        if flips:
            print("  đổi kết luận từ chối:", ", ".join(flips))


if __name__ == "__main__":
    main(sys.argv[1:] or ["eval/out/answers-qdrant-ollama.jsonl"])
