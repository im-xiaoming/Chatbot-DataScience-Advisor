"""Kiểu dữ liệu của bộ đánh giá: một dòng câu hỏi (eval/qa*.jsonl) và một dòng kết quả (eval/out/answers-*.jsonl).

Chỉ để chú thích kiểu, không có logic. Ý nghĩa từng chỉ số xem docstring đầu eval/run_answers.py.
"""
from __future__ import annotations

from typing import NotRequired, TypedDict

from rag.generation.types import NameMismatch, SemesterMismatch


class QARow(TypedDict):
    """Một câu hỏi mẫu. Câu ngoài phạm vi (in_scope=False) có gold_urls và key_facts rỗng."""

    id: str                     # c01, k02, ... chữ cái đầu là nhóm chức năng
    function: str               # tên chức năng của đề bài, dùng để chia bảng kết quả
    question: str
    answer: str                 # đáp án mẫu, chỉ giám khảo LLM đọc
    goal: str | None            # mục tiêu nghề nghiệp gửi kèm câu hỏi
    in_scope: bool
    gold_urls: list[str]        # url tài liệu chứa đáp án
    key_facts: list[str]        # ý bắt buộc; "a|b" = chấp nhận một trong các cách viết
    history: NotRequired[list[list[str]]]       # chỉ bộ nối tiếp: [[vai, nội dung], ...]
    expected_query: NotRequired[list[str]]      # chỉ bộ nối tiếp: câu viết lại phải chứa các ý này


class Judge(TypedDict):
    """Điểm của giám khảo LLM (thang 1-5)."""

    faithfulness: int
    correctness: int
    reason: str


class AnswerResult(TypedDict):
    """Một dòng eval/out/answers-*.jsonl: câu trả lời của chatbot và các chỉ số tự động."""

    id: str
    function: str
    in_scope: bool
    question: str
    query: str                          # câu hỏi sau bước viết lại (bằng question nếu không có lịch sử)
    condense_ok: bool | None            # None nếu không phải câu nối tiếp
    answer: str
    sources: list[str]                  # url các chunk đưa vào ngữ cảnh, theo thứ tự [1], [2], ...
    context: str                        # tin nhắn cuối gửi LLM (NGỮ CẢNH + câu hỏi)
    source_hit: bool | None
    key_fact_recall: float | None
    missing_facts: list[str]
    facts_in_context: float | None
    failure: str | None                 # "retrieval" | "generation" | None
    cited: list[int]
    invalid_citations: list[int]
    invented_codes: list[str]
    semester_mismatch: list[SemesterMismatch]
    name_mismatch: list[NameMismatch]
    refusal: bool
    refusal_ok: bool
    first_token_ms: int
    total_ms: int
    judge: NotRequired[Judge | None]    # chỉ có khi chạy --judge và câu trong phạm vi
