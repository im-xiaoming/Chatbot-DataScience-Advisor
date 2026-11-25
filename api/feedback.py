"""Ghi phản hồi 👍/👎 của người dùng thật (thử nghiệm với sinh viên) vào eval/out/feedback.jsonl.

Gắn vào api/main.py (trước dòng app.mount(...)):
    from api.feedback import router as feedback_router
    app.include_router(feedback_router)
Biến môi trường: FEEDBACK_FILE (mặc định eval/out/feedback.jsonl). Không bắt đăng nhập, để người thử
không có tài khoản (?tester=SV01 trên giao diện) vẫn gửi được.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.auth import optional_user

FEEDBACK_FILE = Path(os.getenv("FEEDBACK_FILE", "eval/out/feedback.jsonl"))
_lock = Lock()  # nhiều request ghi cùng lúc không làm lẫn dòng
router = APIRouter()


class Feedback(BaseModel):
    """Body của POST /feedback, do frontend/app.js (sendFeedback) gửi."""

    rating: int = Field(ge=-1, le=1)            # 1 = hữu ích, -1 = chưa tốt
    question: str
    answer: str
    reason: str | None = None                   # lý do chọn nhanh: sai thông tin, thiếu ý, khó hiểu, ...
    comment: str | None = Field(default=None, max_length=1000)
    goal: str | None = None
    category: str | None = None
    tester: str | None = Field(default=None, max_length=50)   # mã người thử, không ghi họ tên
    sources: list[str] = Field(default_factory=list)
    timing: dict | None = None


# Không ghi kiểu trả về và giữ "dict | None" cho tham số Depends: FastAPI đọc các annotation này lúc chạy
# (kiểu trả về thành response_model), xem chú thích ở phần endpoint của api/auth.py.
@router.post("/feedback")
async def feedback(fb: Feedback, user: dict | None = Depends(optional_user)):
    """Nối một dòng JSON vào FEEDBACK_FILE; người đã đăng nhập mà không có mã người thử thì ghi tên đăng nhập.

    Returns:
        {"ok": True}.
    """
    rec = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), **fb.model_dump()}
    if user and not rec["tester"]:  # người đã đăng nhập: ghi tên đăng nhập làm mã người thử
        rec["tester"] = user["username"]
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _lock, open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"ok": True}
