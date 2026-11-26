"""Kiểu dữ liệu của API: người dùng, cuộc trò chuyện, tin nhắn đã lưu (api/auth.py) và payload SSE (api/main.py).

Chỉ để chú thích kiểu, không có logic. Kiểu chunk/nguồn (Point, Source) ở rag/generation/types.py.
"""
from __future__ import annotations

from typing import NotRequired, TypedDict

from rag.generation.types import CourseCheckDict, Source


DoctorRow = tuple[str, str, str, str]  # api/doctor.py: (trạng thái ✓/!/✗, tên mục, chi tiết, gợi ý sửa)


class User(TypedDict):
    """Người dùng đã đăng nhập (không bao giờ chứa mật khẩu hay hash)."""

    id: int
    username: str
    display_name: str


class Claims(TypedDict):
    """Nội dung token JWT: sub = id người dùng (chuỗi, theo chuẩn JWT), iat/exp = giây Unix."""

    sub: str
    name: str
    iat: int
    exp: int


class Conversation(TypedDict):
    """Một cuộc trò chuyện trong danh sách bên trái giao diện."""

    id: int
    title: str              # 80 ký tự đầu của câu hỏi đầu tiên
    goal: str | None        # mục tiêu nghề nghiệp lúc tạo
    updated_at: float       # giây Unix, để sắp xếp mới nhất trước


class DoneEvent(TypedDict):
    """Dữ liệu sự kiện SSE "done": kiểm tra trích dẫn, môn học và thời gian."""

    cited: list[int]
    invalid_citations: list[int]
    course_check: CourseCheckDict | None    # None nếu không đọc được niên giám
    first_token_ms: int
    total_ms: int


class MessageMeta(TypedDict, total=False):
    """Thông tin lưu kèm câu trả lời (cột meta, JSON) để mở lại hội thoại hiện đúng như lúc chat.

    Tên khoá theo camelCase ở courseCheck vì frontend/app.js đọc thẳng các khoá này.
    """

    route: str                  # "rag" (gọi search_documents), "clarify" (hỏi lại người dùng) hoặc "small_talk" (agent/agent.py)
    query: str                  # câu hỏi sau bước viết lại, nếu khác câu gốc
    sources: list[Source]
    cited: list[int]
    courseCheck: CourseCheckDict | None
    timing: DoneEvent
    error: str                  # câu trả lời lỗi: bị loại khỏi lịch sử gửi LLM
    stopped: bool               # người dùng bấm dừng giữa chừng


class StoredMessage(MessageMeta):
    """Một tin nhắn trả về từ GET /conversations/{id}: các cột cố định cộng các khoá của meta."""

    id: int
    role: str                   # "user" | "assistant"
    content: str
    created_at: float
