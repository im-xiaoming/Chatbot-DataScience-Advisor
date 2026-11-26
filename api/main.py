"""API chat stream từng token (SSE).

Tìm kiếm hybrid trên Qdrant, sinh câu trả lời bằng Ollama. Cấu hình bằng biến môi trường:
  RERANK=1                  sắp xếp lại bằng cross-encoder bge-reranker-v2-m3 của nhóm (tải model lần đầu)
  NUM_CTX=8192              cửa sổ ngữ cảnh gửi cho Ollama (tăng nếu máy đủ RAM/VRAM)
  TOP_K=8                   số chunk lấy về cho mỗi câu hỏi (lý do chọn 8: xem chú thích ở dòng TOP_K)
  AUTH_REQUIRED, APP_DB, AUTH_SECRET, TOKEN_DAYS: xem api/auth.py
Chạy:  uv run uvicorn api.main:app --reload   rồi mở http://localhost:8000

Luồng một câu hỏi (agent/agent.py):
  LLM agent có tool search_documents -> không gọi tool: trả lời thẳng (chào hỏi, chat vu vơ)
                                    -> gọi tool (RAG): tìm kiếm query -> chọn chunk -> dựng prompt -> stream token
                                    -> gọi ask_user: câu hỏi chưa rõ, dừng (interrupt) chờ người dùng trả lời
Sự kiện SSE: conversation (id hội thoại đã lưu) · route (small_talk | rag | clarify) · query (câu hỏi đã viết lại)
             · sources · token · clarify (câu hỏi lại + thread_id) · done · error

Đăng nhập: /chat cần header "Authorization: Bearer <token>" (lấy từ /auth/login), trừ khi AUTH_REQUIRED=0.
Người đã đăng nhập: câu hỏi và câu trả lời được lưu theo conversation_id (api/auth.py), lịch sử lấy từ máy chủ.
eval/run_answers.py import generator, llm, retrieve từ file này để chấm đúng cấu hình như API thật.
"""
import json
import re
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent.agent import Agent
from agent.models import load_llm_model
from api.auth import auth_required, chat_user, get_store
from api.auth import router as auth_router
from api.rag_service import retrieve
from api.types import MessageMeta
from config import APIConfig, LLMConfig
from rag.generation import Generator
from rag.retrieval import MetadataFilter

if TYPE_CHECKING:
    from api.auth import Store
    from api.types import Conversation

_api = APIConfig()
RERANK, NUM_CTX, TOP_K = _api.rerank, _api.num_ctx, _api.top_k
# Đo lại trên Qdrant (10 câu đầu, 23/11): k=6 recall ý 0,80 / tổng 39 s; k=8 recall 0,89 / tổng 51 s -> giữ 8.

_cfg = LLMConfig()
# Prompt dài nhất của bộ eval ~3.800 token; mặc định 32.768 của loader làm Ollama hết RAM trên máy 16 GB
llm = load_llm_model(model_name=_cfg.model_name, model_provider=_cfg.model_provider, num_ctx=NUM_CTX)

generator = Generator(llm)
reranker = None
if RERANK:
    from rag.rerank import Reranker
    reranker = Reranker()
agent = Agent(generator, retrieve, top_k=TOP_K, reranker=reranker)

ANON_THREAD = re.compile(r"anon-[0-9a-f]{32}")  # thread_id hợp lệ của người chưa đăng nhập


class Turn(BaseModel):
    """Một lượt hội thoại do trình duyệt gửi kèm (chỉ khi chưa đăng nhập)."""

    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    """Body của POST /chat."""

    question: str
    filters: MetadataFilter | None = None  # lọc metadata khi tìm kiếm, ví dụ {"category": "regulation"}
    goal: str | None = None            # Data Analyst, Data Scientist, ...
    history: list[Turn] = Field(default_factory=list)  # chỉ dùng khi không đăng nhập (AUTH_REQUIRED=0)
    conversation_id: int | None = None                  # bỏ trống = tạo cuộc trò chuyện mới
    # thread_id của sự kiện "clarify" lượt trước, để câu này được hiểu là câu trả lời cho câu hỏi lại.
    # Chỉ dùng khi chưa đăng nhập và đúng dạng "anon-<32 hex>"; người đã đăng nhập luôn dùng "conv-<conversation_id>".
    # Không chặn bằng pattern ở đây: giao diện gửi lại cả thread "conv-..." và request bị 422 oan.
    thread_id: str | None = Field(default=None, max_length=64)


def sse(data: Any, event: str | None = None) -> str:
    """Một sự kiện Server-Sent Events: dòng "event:" (bỏ qua với token cho gọn), dòng "data:" JSON, dòng trống.

    Args:
        data: payload JSON (dict, hoặc TypedDict như DoneEvent).
        event: tên sự kiện; None = sự kiện mặc định "message", giao diện hiểu là token.
    """
    head = f"event: {event}\n" if event else ""
    return head + "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"


app = FastAPI(title="Cố vấn lộ trình KHDL")


# Endpoint không ghi kiểu trả về và tham số Depends giữ "dict | None": FastAPI đọc các annotation này lúc chạy
# (kiểu trả về thành response_model), xem chú thích ở phần endpoint của api/auth.py.
@app.get("/health")
async def health():
    """Cấu hình đang chạy; giao diện đọc khi tải trang để hiện chế độ và biết có cần đăng nhập không."""
    return {"retriever": "qdrant", "llm": "ollama", "rerank": RERANK, "auth": auth_required()}


@app.post("/chat")
async def chat(req: ChatRequest, user: dict | None = Depends(chat_user)):
    """Trả lời một câu hỏi, stream bằng SSE.

    Lịch sử: người đã đăng nhập lấy từ CSDL theo conversation_id (bỏ trống thì tạo cuộc trò chuyện mới);
    chưa đăng nhập (AUTH_REQUIRED=0) thì dùng req.history do trình duyệt gửi. Câu hỏi được lưu ngay,
    câu trả lời được lưu trong finally nên vẫn còn khi người dùng bấm dừng hoặc có lỗi.

    Raises:
        HTTPException: 401 chưa đăng nhập (từ chat_user), 404 conversation_id không có hoặc của người khác.
    """
    store: Store  # chỉ None khi user None, và mọi chỗ dùng store đều nằm sau kiểm tra user/conv
    conv: Conversation | None
    store, conv = (get_store(), None) if user else (None, None)  # type: ignore[assignment]
    if user and req.conversation_id:
        conv = store.get_conversation(user["id"], req.conversation_id)
        if not conv:
            raise HTTPException(404, "Không tìm thấy cuộc trò chuyện")
        history = store.history(conv["id"])
    else:
        history = [("human" if t.role == "user" else "ai", t.content) for t in req.history]
    if user and not conv:
        conv = store.create_conversation(user["id"], req.question, req.goal)
    if conv:
        store.add_message(conv["id"], "user", req.question)
    # Luồng của agent: còn đang chờ trả lời câu hỏi lại thì agent chạy tiếp từ đó (agent/agent.py, node clarify)
    # Chưa đăng nhập chỉ nhận thread "anon-..." để không resume được thread "conv-..." của người khác.
    anon = req.thread_id if req.thread_id and ANON_THREAD.fullmatch(req.thread_id) else None
    thread_id = f"conv-{conv['id']}" if conv else anon or f"anon-{uuid.uuid4().hex}"

    async def gen() -> AsyncIterator[str]:
        """Các sự kiện theo thứ tự: conversation? · route · query? · sources? · token* · clarify? · done (hoặc error)."""
        answer = ""
        meta: MessageMeta = {}
        if conv:
            yield sse({"id": conv["id"], "title": conv["title"]}, "conversation")
        try:
            async for event, data in agent.run(req.question, history, filters=req.filters, goal=req.goal,
                                               thread_id=thread_id):
                if event == "token":  # token gửi không kèm dòng "event:" cho gọn
                    answer += data["token"]
                    yield sse(data)
                    continue
                if event == "route":
                    meta["route"] = data["route"]
                elif event == "query":
                    meta["query"] = data["query"]
                elif event == "sources":
                    meta["sources"] = data["sources"]
                elif event == "clarify":
                    meta["route"] = "clarify"
                elif event == "done":
                    meta.update(cited=data["cited"], courseCheck=data["course_check"], timing=data)  # type: ignore[call-arg, typeddict-item]  # mypy chưa hỗ trợ update(**kw) cho TypedDict
                yield sse(data, event)
        except Exception as e:  # báo lỗi lên giao diện thay vì cắt kết nối
            meta["error"] = f"Có lỗi ở máy chủ: {type(e).__name__}: {e}"
            yield sse({"message": f"{type(e).__name__}: {e}"}, "error")
        finally:  # lưu cả khi người dùng bấm dừng giữa chừng (kết nối bị đóng)
            if conv:
                if "timing" not in meta and "error" not in meta:
                    meta["stopped"] = True
                store.add_message(conv["id"], "assistant", answer, meta)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


from api.feedback import router as feedback_router  # noqa: E402

app.include_router(feedback_router)
app.include_router(auth_router)

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
