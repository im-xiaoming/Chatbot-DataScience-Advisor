"""Hàm dùng chung cho các script đánh giá (run_answers, run_retrieval, rescore, report).

So khớp ý bắt buộc và nhận diện câu từ chối đều theo chuỗi con sau khi chuẩn hoá (không dùng LLM),
nên nhanh, lặp lại được, nhưng có thể khớp nhầm; xem phần lưu ý trong eval/results.md.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eval.types import QARow

OUT_DIR = Path("eval/out")


def load_qa(path: str = "eval/qa.jsonl") -> list[QARow]:
    """Đọc file JSONL câu hỏi mẫu (bỏ dòng trống)."""
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def norm(s: str) -> str:
    """Chuẩn hoá để so khớp: Unicode NFC, chữ thường, gộp khoảng trắng."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s).lower()).strip()


def key_fact_hits(answer: str, key_facts: list[str]) -> list[bool]:
    """Mỗi ý bắt buộc có xuất hiện trong câu trả lời không ("a|b" = chấp nhận một trong các cách viết)."""
    a = norm(answer)
    return [any(norm(alt) in a for alt in k.split("|")) for k in key_facts]


# Cụm chữ coi là "từ chối". Chưa có các cách viết "không có số liệu", "không cung cấp" (eval/results.md liệt kê
# các câu bị bỏ sót vì vậy); thêm/bớt cụm thì chạy lại eval.rescore để xem câu nào đổi kết luận.
REFUSAL_PATTERNS = [
    "chưa có dữ liệu", "chưa có thông tin", "không có thông tin", "không có dữ liệu",
    "không tìm thấy", "chưa tìm thấy", "không đủ thông tin", "không thể trả lời",
    "ngoài phạm vi", "không nằm trong", "không có trong", "chưa được cung cấp",
]


def _opening(answer: str, chars: int = 300) -> str:
    """Phần mở đầu câu trả lời, bỏ dòng tiêu đề Markdown (### ...)."""
    lines = [l for l in answer.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    return norm(" ".join(lines))[:chars]


def is_refusal(answer: str) -> bool:
    """Câu trả lời có phải là từ chối ("chưa có thông tin...") không.

    Chỉ xét phần mở đầu (hoặc cả câu nếu câu ngắn), vì LLM hay chèn ghi chú kiểu
    "tài liệu không có thông tin về lương" ở giữa một câu trả lời đúng; đếm cả những ghi chú đó
    làm chỉ số "trả lời câu trong phạm vi" thấp sai (lượt v148: c14, r16, k26, m09...).
    """
    text = norm(answer) if len(answer) < 400 else _opening(answer)
    return any(p in text for p in REFUSAL_PATTERNS)


def save_json(name: str, data: Any) -> Path:
    """Ghi data ra eval/out/<name> (UTF-8, giữ dấu tiếng Việt) và trả về đường dẫn."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUT_DIR / name
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p
