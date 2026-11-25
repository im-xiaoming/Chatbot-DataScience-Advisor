"""Gộp kết quả trong eval/out/ thành bảng Markdown eval/results.md để dán vào báo cáo.

Chạy: uv run python -m eval.report
Đọc eval/out/retrieval-*.json và eval/out/answers-*.summary.json (chỉ các file ngay trong eval/out/, không đọc
thư mục con như eval/out/final148/). GHI ĐÈ toàn bộ eval/results.md: phần viết tay (ví dụ mục so sánh
v148/final148) phải dán lại sau khi chạy.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

OUT = Path("eval/out")
# Tên tiếng Việt của từng chỉ số; thứ tự ở đây là thứ tự dòng trong bảng.
LABEL: dict[str, str] = {
    "key_fact_recall": "Ý bắt buộc có trong câu trả lời", "facts_in_context": "Ý bắt buộc có trong ngữ cảnh",
    "source_hit": "Tài liệu đúng có trong ngữ cảnh",
    "fail_retrieval": "Câu thiếu ý do tìm kiếm", "fail_generation": "Câu thiếu ý do LLM bỏ sót",
    "cited_rate": "Có ghi nguồn [n]", "invalid_citations": "Trích dẫn sai số",
    "invented_codes": "Mã môn bịa (không có trong niên giám)", "semester_mismatch": "Môn ghi sai học kỳ", "name_mismatch": "Mã môn ghép sai tên",
    "condense_ok": "Viết lại câu hỏi nối tiếp đúng", "answered_in_scope": "Trả lời câu trong phạm vi", "refused_out_of_scope": "Từ chối câu ngoài phạm vi",
    "faithfulness": "Bám ngữ cảnh (1-5)", "correctness": "Đúng so với đáp án (1-5)",
    "first_token_ms_avg": "Token đầu (ms)", "total_ms_avg": "Tổng thời gian (ms)",
}


# Chỉ số dạng tỉ lệ 0-1, in thành phần trăm; số đếm và điểm 1-5 in nguyên.
RATIOS: set[str] = {"condense_ok", "facts_in_context", "key_fact_recall", "source_hit", "cited_rate", "answered_in_scope", "refused_out_of_scope",
          "hit@1", "hit@3", "hit@5", "recall@5"}


def pct(v: float | int | None, key: str | None = None) -> str:
    """Định dạng một ô: "–" nếu thiếu, phần trăm nếu là tỉ lệ, còn lại in nguyên."""
    if v is None:
        return "–"
    if key in RATIOS or (key is None and isinstance(v, float) and v <= 1):
        return f"{float(v):.0%}"
    return str(v)


def retrieval_section(path: Path) -> list[str]:
    """Bảng chỉ số tìm kiếm của một file retrieval-*.json, kèm bảng theo chức năng của cách tìm có MRR cao nhất."""
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = [f"### Tìm kiếm — {path.stem.split('-', 1)[1]}", "",
             "| Cách tìm | Số câu | Hit@1 | Hit@3 | Hit@5 | Recall@5 | MRR |", "|---|---|---|---|---|---|---|"]
    for name, res in data["results"].items():
        o = res["overall"]
        lines.append(f"| {name} | {o['n']} | {pct(o['hit@1'])} | {pct(o['hit@3'])} | {pct(o['hit@5'])} | "
                     f"{pct(o['recall@5'])} | {o['mrr']:.2f} |")
    best = max(data["results"].items(), key=lambda kv: kv[1]["overall"]["mrr"])
    lines += ["", f"Theo chức năng (cách tìm {best[0]}):", "",
              "| Chức năng | Số câu | Hit@5 | MRR |", "|---|---|---|---|"]
    for fn, o in best[1]["by_function"].items():
        lines.append(f"| {fn} | {o['n']} | {pct(o['hit@5'])} | {o['mrr']:.2f} |")
    if best[1]["misses"]:
        lines += ["", "Câu trượt top 5: " + ", ".join(best[1]["misses"])]
    return lines + [""]


def answers_section(path: Path) -> list[str]:
    """Bảng chỉ số câu trả lời của một file answers-*.summary.json: cột Toàn bộ và một cột cho mỗi chức năng."""
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    s, cfg = data["summary"], data["config"]
    qa = "" if cfg.get("qa", "eval/qa.jsonl") == "eval/qa.jsonl" else f", bộ {cfg['qa']}"
    lines = [f"### Câu trả lời — tìm kiếm {cfg['retriever']}, LLM {cfg['llm']}{qa}" + (", có giám khảo LLM" if cfg.get("judge") else ""), ""]
    keys = [k for k in LABEL if k in s["overall"]]
    lines += ["| Chỉ số | Toàn bộ | " + " | ".join(s["by_function"]) + " |",
              "|---|---|" + "---|" * len(s["by_function"])]
    for k in keys:
        lines.append(f"| {LABEL[k]} | {pct(s['overall'][k], k)} | " +
                     " | ".join(pct(v.get(k), k) for v in s["by_function"].values()) + " |")
    if data.get("errors"):
        lines += ["", f"Câu lỗi LLM, không tính vào chỉ số: {', '.join(data['errors'])}"]
    return lines + [""]


def main() -> None:
    """Gộp mọi file kết quả thành eval/results.md và in ra màn hình."""
    lines = ["# Kết quả đánh giá chatbot tư vấn lộ trình KHDL", "",
             f"Cập nhật: {datetime.now():%d/%m/%Y %H:%M}. Bộ câu hỏi: `eval/qa.jsonl`.", ""]
    for p in sorted(OUT.glob("retrieval-*.json")):
        lines += retrieval_section(p)
    for p in sorted(OUT.glob("answers-*.summary.json")):
        lines += answers_section(p)
    Path("eval/results.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
