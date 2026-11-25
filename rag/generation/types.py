"""Kiểu dữ liệu dùng chung giữa tìm kiếm, Generation và API (chỉ để chú thích kiểu, không có logic).

Point là một chunk đã tìm được: payload Qdrant (do pipline.py của nhóm nạp) cộng điểm tìm kiếm;
tìm kiếm giả (api/fake.py) trả về đúng các khoá này. Source là bản rút gọn của Point gửi về giao diện
qua sự kiện SSE "sources" và lưu kèm câu trả lời trong lịch sử hội thoại.
"""
from __future__ import annotations

from typing import NotRequired, TypedDict


class Point(TypedDict):
    """Một chunk tìm được, đưa vào NGỮ CẢNH của prompt."""

    title: str
    url: str
    category: str               # curriculum, regulation, career, market... (lọc được bằng tham số category)
    page_content: str
    section_path: NotRequired[list[str]]     # đường dẫn tiêu đề trong tài liệu gốc, ví dụ ["Quy chế", "Điều 23"]
    score: NotRequired[float | None]         # điểm tìm kiếm (RRF/cosine/BM25), hoặc điểm rerank nếu RERANK=1
    retrieval_score: NotRequired[float | None]  # điểm tìm kiếm gốc, chỉ có khi đã rerank
    published_date: NotRequired[str | None]
    valid_until: NotRequired[str | None]     # có thì ghi "hiệu lực đến ..." vào ngữ cảnh
    doc_id: NotRequired[str]
    chunk_id: NotRequired[str]


class Source(TypedDict):
    """Nguồn gửi về giao diện: đủ để hiện thẻ nguồn [n], không gửi toàn văn chunk."""

    title: str
    url: str
    category: str
    section_path: list[str]
    score: float | None
    snippet: str                # 280 ký tự đầu của page_content


class SemesterMismatch(TypedDict):
    """Câu trả lời ghi một môn ở học kỳ khác với niên giám."""

    code: str
    name: str
    said: int       # học kỳ câu trả lời ghi
    actual: int     # học kỳ trong niên giám


class NameMismatch(TypedDict):
    """Mã môn ghép với tên của một môn khác (lỗi hay gặp của LLM nhỏ khi chép bảng)."""

    code: str
    said_name: str
    actual_name: str
    said_name_code: str     # mã thật của môn mang tên mà câu trả lời đã ghi


class CourseCheckDict(TypedDict):
    """Kết quả CourseCheck.as_dict(), gửi trong sự kiện "done" (khoá course_check)."""

    codes: list[str]
    unknown: list[str]
    semester_mismatch: list[SemesterMismatch]
    name_mismatch: list[NameMismatch]
