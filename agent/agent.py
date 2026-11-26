"""Agent LangGraph có ba tool: RAG (search_documents), hỏi lại người dùng (ask_user) và trả lời thẳng (reply).

Graph (xem Agent._build_graph):

    START -> agent --(gọi reply)----------------> respond ----------> END
              ^    |-(gọi search_documents)-> search_documents -> generate -> END
              |    \\-(gọi ask_user)---------> clarify: interrupt() -- tạm dừng, chờ người dùng trả lời
              \\_______________________________________/  (resume bằng Command(resume=câu trả lời))

  agent             LLM + AGENT_PROMPT, đã bind 3 tool và luôn phải gọi đúng một tool. Có tool reply là để model
                    nhỏ (qwen 4B) chịu gọi ask_user: chỉ có 2 tool thì nó tự viết câu hỏi lại thành chữ thường
                    (đo 26/11: 2 tool hỏi lại đúng 0/5 câu mơ hồ, 3 tool 4/5).
  respond           gửi câu trả lời thẳng (chào hỏi, chat vu vơ, hỏi lại điều đã nói), không trích dẫn.
  search_documents  tool RAG: tìm kiếm query (+ rerank) -> chọn chunk vừa ngữ cảnh.
  generate          dựng prompt RAG, stream câu trả lời có trích dẫn [n], kiểm tra môn học.
  clarify           câu hỏi chưa rõ: interrupt() dừng graph (trạng thái lưu trong checkpointer theo thread_id),
                    run() gửi câu hỏi lại cho người dùng. Tin nhắn kế tiếp cùng thread_id resume graph: câu trả lời
                    được ghép vào hội thoại rồi quay lại node agent. Hỏi lại tối đa MAX_CLARIFY lần, sau đó
                    agent không còn tool ask_user để không hỏi vòng vòng.

query của tool là câu hỏi đầy đủ, độc lập do LLM viết (thay bước condense). LLM lỗi, hoặc không gọi tool mà cũng
không trả lời gì, thì vào search_documents với câu hỏi viết lại bằng generator.condense như cũ.

Các node gửi sự kiện (tên, dữ liệu) qua get_stream_writer(); run() đọc bằng graph.astream(stream_mode="custom")
nên token vẫn stream được. api/main.py đổi sự kiện thành SSE và lưu tin nhắn.
Sự kiện: route · query? · sources? · token* · clarify? · done.
Thread chạy xong (không bị interrupt) thì xoá khỏi checkpointer, nên lượt sau không dính trạng thái cũ.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator, Callable, Coroutine, Sequence
from typing import Any, Literal, TypedDict

from langchain_core.tools import tool
from langgraph.config import get_stream_writer
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agent.prompt import AGENT_PROMPT
from rag.generation import Generator, default_catalog, detect_intent, extract_citations
from rag.generation.generator import Message
from rag.generation.types import Point
from rag.retrieval import MetadataFilter

logger = logging.getLogger(__name__)

Event = tuple[str, dict[str, Any]]
Route = Literal["small_talk", "rag", "clarify"]
MAX_CLARIFY = 2  # số lần hỏi lại tối đa trong một câu hỏi
Retrieve = Callable[..., Coroutine[Any, Any, list[Point]]]  # retrieve(câu, filters, k=...)


@tool
def search_documents(query: str) -> str:
    """Tra tài liệu chính thức của IUH và ngành Khoa học Dữ liệu: môn học, học kỳ, quy chế, học phí, học bổng,
    tốt nghiệp, chứng chỉ, nghề nghiệp, kỹ năng, lương, thị trường việc làm.

    Args:
        query: câu hỏi đầy đủ, độc lập bằng tiếng Việt.
    """
    raise NotImplementedError("node search_documents của graph chạy tool này")  # chỉ dùng làm schema cho LLM


@tool
def ask_user(question: str) -> str:
    """Hỏi lại sinh viên khi câu hỏi về học tập thiếu đối tượng chính nên không tra được, và hội thoại
    cũng không cho biết đối tượng đó.

    Args:
        question: một câu hỏi lại ngắn bằng tiếng Việt, gợi ý 2-3 lựa chọn cụ thể nếu được.
    """
    raise NotImplementedError("node clarify của graph chạy tool này")  # chỉ dùng làm schema cho LLM


@tool
def reply(answer: str) -> str:
    """Trả lời thẳng sinh viên, không tra tài liệu: chào hỏi, cảm ơn, tâm sự, chuyện vu vơ, hỏi lại điều đã nói
    trong hội thoại.

    Args:
        answer: câu trả lời 1-3 câu bằng tiếng Việt.
    """
    raise NotImplementedError("node respond của graph gửi câu trả lời này")  # chỉ dùng làm schema cho LLM


class State(TypedDict, total=False):
    """Trạng thái truyền giữa các node."""

    question: str                 # câu sinh viên gửi
    history: list[Message]        # lịch sử (vai, nội dung)
    filters: MetadataFilter | None  # lọc metadata khi tìm kiếm (rag/retrieval/metadata.py)
    goal: str | None              # mục tiêu nghề nghiệp
    route: Route                  # do node agent chọn
    reply: str                    # câu trả lời thẳng (route small_talk)
    query: str                    # câu hỏi độc lập dùng để tìm kiếm (route rag)
    points: list[Point]           # chunk đã chọn cho prompt RAG
    clarify_question: str         # câu hỏi lại (route clarify)
    clarify_rounds: int           # đã hỏi lại bao nhiêu lần


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


class Agent:
    """Agent một lượt chat, chạy bằng LangGraph.

    Args:
        generator: Generator dùng chung; generator.llm phải có bind_tools (chat model LangChain).
        retrieve: hàm tìm kiếm async, gọi dạng retrieve(câu, filters, k=k).
        top_k: số chunk lấy về cho mỗi câu hỏi.
        reranker: có thì lấy 2 x top_k rồi để cross-encoder chọn lại top_k.
    """

    def __init__(self, generator: Generator, retrieve: Retrieve, *, top_k: int = 8, reranker: Any = None) -> None:
        self.generator = generator
        self.retrieve = retrieve
        self.top_k = top_k
        self.reranker = reranker
        self.tool_llm = generator.llm.bind_tools([search_documents, ask_user, reply])
        self.no_ask_llm = generator.llm.bind_tools([search_documents, reply])  # khi đã hỏi lại đủ MAX_CLARIFY lần
        self.checkpointer = InMemorySaver()  # lưu graph đang chờ người dùng trả lời; mất khi khởi động lại API
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        g = StateGraph(State)
        g.add_node("agent", self._agent)
        g.add_node("respond", self._respond)
        g.add_node("search_documents", self._search_documents)
        g.add_node("generate", self._generate)
        g.add_node("clarify", self._clarify)
        g.add_edge(START, "agent")
        next_node = {"small_talk": "respond", "rag": "search_documents", "clarify": "clarify"}
        g.add_conditional_edges("agent", lambda state: next_node[state["route"]], list(next_node.values()))
        g.add_edge("respond", END)
        g.add_edge("search_documents", "generate")
        g.add_edge("generate", END)
        g.add_edge("clarify", "agent")
        return g.compile(checkpointer=self.checkpointer)

    async def run(self, question: str, history: Sequence[Message], *, filters: MetadataFilter | None = None,
                  goal: str | None = None, thread_id: str | None = None) -> AsyncIterator[Event]:
        """Chạy graph, trả lần lượt các sự kiện của node; tự thêm thời gian (first_token_ms, total_ms) vào done.

        Args:
            thread_id: id luồng hội thoại (api/main.py dùng "conv-<id>"). Nếu luồng này đang chờ trả lời câu hỏi
                lại thì question là câu trả lời và graph chạy tiếp từ node clarify (history, filters, goal bỏ qua,
                dùng trạng thái đã lưu). None = tạo luồng mới chỉ cho lượt này.
        """
        t0, first = time.perf_counter(), None
        config: Any = {"configurable": {"thread_id": thread_id or uuid.uuid4().hex}}
        if (await self.graph.aget_state(config)).interrupts:
            inp: Any = Command(resume=question)
        else:
            inp = State(question=question, history=list(history), filters=filters, goal=goal, clarify_rounds=0)
        async for name, data in self.graph.astream(inp, config, stream_mode="custom"):
            if name == "token":
                first = first or time.perf_counter()
            elif name == "done":
                data = {**data, "first_token_ms": round(((first or time.perf_counter()) - t0) * 1000),
                        "total_ms": round((time.perf_counter() - t0) * 1000)}
            yield name, data

        pending = (await self.graph.aget_state(config)).interrupts
        if not pending:  # xong lượt: xoá để lượt sau bắt đầu từ trạng thái sạch
            await self.checkpointer.adelete_thread(config["configurable"]["thread_id"])
            return
        ask = pending[0].value["question"]  # graph dừng ở node clarify: gửi câu hỏi lại như một câu trả lời
        ms = round((time.perf_counter() - t0) * 1000)
        yield "token", {"token": ask}
        yield "clarify", {"question": ask, "thread_id": config["configurable"]["thread_id"]}
        yield "done", {"cited": [], "invalid_citations": [], "course_check": None,
                       "first_token_ms": ms, "total_ms": ms}

    # ---------- các node ----------
    async def decide(self, question: str, history: Sequence[Message], *,
                     allow_clarify: bool = True) -> tuple[Route, str]:
        """Một lượt LLM có tool. Trả về ("small_talk", câu trả lời), ("rag", query của tool; rỗng nếu LLM lỗi)
        hoặc ("clarify", câu hỏi lại)."""
        msgs: list[Message] = [("system", AGENT_PROMPT)]
        msgs += list(history[-self.generator.max_history_turns:])
        msgs.append(("human", question))
        try:
            res = await (self.tool_llm if allow_clarify else self.no_ask_llm).ainvoke(msgs)
        except Exception:
            logger.exception("Agent LLM failed; vào RAG.")
            return "rag", ""
        calls = {c["name"]: c["args"] for c in res.tool_calls}
        if search_documents.name in calls:
            return "rag", str(calls[search_documents.name].get("query") or "").strip()
        if allow_clarify and (ask := str(calls.get(ask_user.name, {}).get("question") or "").strip()):
            return "clarify", ask
        answer = _strip_think(str(calls.get(reply.name, {}).get("answer") or res.content))  # model đôi khi viết chữ thường
        return ("small_talk", answer) if answer else ("rag", "")

    async def _agent(self, state: State) -> State:
        """Node agent: LLM chọn tra tài liệu, hỏi lại hay trả lời thẳng."""
        route, text = await self.decide(state["question"], state["history"],
                                        allow_clarify=state.get("clarify_rounds", 0) < MAX_CLARIFY)
        get_stream_writer()(("route", {"route": route}))
        if route == "small_talk":
            return {"route": route, "reply": text}
        if route == "clarify":
            return {"route": route, "clarify_question": text}
        return {"route": route, "query": text}

    async def _clarify(self, state: State) -> State:
        """Node clarify: dừng graph chờ người dùng trả lời câu hỏi lại, rồi ghép vào hội thoại cho node agent.

        interrupt() lần đầu dừng graph; khi resume, node chạy lại từ đầu và interrupt() trả về câu trả lời.
        """
        answer = interrupt({"question": state["clarify_question"]})
        # trạng thái đọc lại từ checkpointer biến tuple thành list: đổi về (vai, nội dung) cho đúng kiểu Message
        history = [(r, c) for r, c in state["history"]]
        history += [("human", state["question"]), ("ai", state["clarify_question"])]
        return {"question": str(answer), "history": history, "clarify_rounds": state.get("clarify_rounds", 0) + 1}

    async def _respond(self, state: State) -> State:
        """Node respond: gửi câu trả lời thẳng của LLM (không tra tài liệu, không trích dẫn)."""
        write = get_stream_writer()
        write(("token", {"token": state["reply"]}))
        write(("done", {"cited": [], "invalid_citations": [], "course_check": None}))
        return {}

    async def _search_documents(self, state: State) -> State:
        """Node tool search_documents: tìm kiếm (+ rerank), chọn chunk vừa ngữ cảnh, gửi danh sách nguồn."""
        write, gen = get_stream_writer(), self.generator
        query = state.get("query") or await gen.condense(state["question"], state["history"])
        if query != state["question"]:
            write(("query", {"query": query}))

        search_q = gen.search_query(query, state.get("goal"))
        if self.reranker:  # lấy nhiều hơn rồi để cross-encoder chọn lại (chạy trong thread vì nặng CPU/GPU)
            found = await self.retrieve(search_q, state.get("filters"), k=self.top_k * 2)
            found = await asyncio.to_thread(self.reranker.rerank, query, found, self.top_k)
        else:
            found = await self.retrieve(search_q, state.get("filters"), k=self.top_k)
        points = gen.select_points(found)
        write(("sources", {"intent": detect_intent(query), "sources": [{
            "title": p["title"], "url": p["url"], "category": p["category"],
            "section_path": p.get("section_path") or [], "score": p.get("score"),
            "snippet": p["page_content"][:280],
        } for p in points]}))
        return {"query": query, "points": points}

    async def _generate(self, state: State) -> State:
        """Node generate: stream câu trả lời dựa trên tài liệu, có trích dẫn [n] và kiểm tra môn học."""
        write, gen, points = get_stream_writer(), self.generator, state["points"]
        answer = ""
        messages = gen.build_messages(state["query"], points, goal=state.get("goal"), history=state["history"])
        async for text in gen.stream(messages, n_sources=len(points)):
            answer += text
            write(("token", {"token": text}))
        cited, invalid = extract_citations(answer, len(points))
        catalog = default_catalog()
        write(("done", {"cited": cited, "invalid_citations": invalid,
                        "course_check": catalog.check(answer).as_dict() if catalog else None}))
        return {}
