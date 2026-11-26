"""Agent LangGraph (agent/agent.py): LLM tự quyết gọi RAG, hỏi lại người dùng (interrupt) hay trả lời thẳng."""
import asyncio
from types import SimpleNamespace

import pytest

from agent.agent import MAX_CLARIFY, Agent
from rag.generation import Generator


class FakeLLM:
    """Chat model giả.

    bind_tools().ainvoke -> lần lượt theo `script`, mỗi phần tử là ("search", query) | ("ask", câu hỏi lại) |
    ("reply", câu trả lời qua tool reply) | ("text", câu trả lời bằng chữ thường, không gọi tool);
    hết kịch bản thì lặp lại phần tử cuối. Mỗi lần gọi ghi lại tên các tool đã bind.
    ainvoke (bước condense) -> câu cố định; astream (bước RAG) -> câu trả lời có thẻ think và trích dẫn [1].
    """

    def __init__(self, *script, fail=False):
        self.script = list(script) or [("text", "<think>x</think>Chào bạn!")]
        self.fail, self.calls, self.bound = fail, [], []

    def bind_tools(self, tools):
        self.bound.append(tools)
        names = [t.name for t in tools]
        return SimpleNamespace(ainvoke=lambda messages: self._decide(messages, names))

    async def _decide(self, messages, tools):
        self.calls.append(("decide", messages, tools))
        if self.fail:
            raise RuntimeError("Ollama tắt")
        kind, text = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if kind == "text":
            return SimpleNamespace(content=text, tool_calls=[])
        name, arg = {"search": ("search_documents", "query"), "ask": ("ask_user", "question"),
                     "reply": ("reply", "answer")}[kind]
        return SimpleNamespace(content="", tool_calls=[{"name": name, "args": {arg: text}, "id": "1"}])

    async def ainvoke(self, messages):
        self.calls.append(("condense", messages, None))
        return SimpleNamespace(content="câu hỏi viết lại")

    async def astream(self, messages):
        self.calls.append(("answer", messages, None))
        for t in ["<think>nghĩ</think>", "Theo quy chế ", "[1]"]:
            yield SimpleNamespace(content=t)


async def fake_retrieve(q, filters, k=8):
    fake_retrieve.calls.append((q, filters, k))
    return [{"title": "Quy chế", "url": "https://x", "category": "regulation", "page_content": "Nội dung quy chế."}]


def collect(agent, question, history=(), thread_id=None):
    async def go():
        return [e async for e in agent.run(question, list(history), thread_id=thread_id)]
    return asyncio.run(go())


def decisions(llm):
    return [c for c in llm.calls if c[0] == "decide"]


@pytest.fixture(autouse=True)
def _reset():
    fake_retrieve.calls = []


def test_agent_exposes_tools():
    llm = FakeLLM()
    Agent(Generator(llm), fake_retrieve)
    assert [[t.name for t in tools] for tools in llm.bound] == [["search_documents", "ask_user", "reply"],
                                                                 ["search_documents", "reply"]]
    assert ("query", "question", "answer") == tuple(next(iter(t.args)) for t in llm.bound[0])


def test_graph_nodes_and_edges():
    g = Agent(Generator(FakeLLM()), fake_retrieve).graph.get_graph()
    assert set(g.nodes) == {"__start__", "agent", "respond", "search_documents", "generate", "clarify", "__end__"}
    edges = {(e.source, e.target) for e in g.edges}
    assert edges == {("__start__", "agent"), ("agent", "respond"), ("agent", "search_documents"), ("agent", "clarify"),
                     ("clarify", "agent"), ("respond", "__end__"), ("search_documents", "generate"),
                     ("generate", "__end__")}


@pytest.mark.parametrize("kind", ["reply", "text"])  # tool reply, hoặc model quên gọi tool mà viết chữ thường
def test_reply_answers_directly_without_search(kind):
    llm = FakeLLM((kind, "<think>x</think>Bạn tên là Minh nhé!"))
    history = [("human", "mình là Minh"), ("ai", "Chào Minh!")]
    evs = collect(Agent(Generator(llm), fake_retrieve), "tên mình là gì", history)
    assert [n for n, _ in evs] == ["route", "token", "done"] and evs[0][1] == {"route": "small_talk"}
    assert evs[1][1] == {"token": "Bạn tên là Minh nhé!"}  # đã bỏ thẻ think
    assert evs[-1][1]["cited"] == [] and "total_ms" in evs[-1][1]
    assert fake_retrieve.calls == []
    sent = decisions(llm)[0][1]
    assert sent[0][0] == "system" and sent[1:3] == history and sent[-1] == ("human", "tên mình là gì")


def test_tool_call_runs_rag_with_tool_query():
    llm = FakeLLM(("search", "Điều kiện buộc thôi học là gì?"))
    evs = collect(Agent(Generator(llm), fake_retrieve, top_k=5), "khi nào bị đuổi học?")
    names = [n for n, _ in evs]
    assert names[:3] == ["route", "query", "sources"] and evs[0][1] == {"route": "rag"}
    assert evs[1][1] == {"query": "Điều kiện buộc thôi học là gì?"}
    assert fake_retrieve.calls == [("Điều kiện buộc thôi học là gì?", None, 5)]
    assert "condense" not in [c[0] for c in llm.calls]  # query của tool thay bước viết lại câu hỏi
    done = evs[-1][1]
    assert names[-1] == "done" and done["cited"] == [1] and "first_token_ms" in done


@pytest.mark.parametrize("llm", [FakeLLM(fail=True), FakeLLM(("text", "<think>x</think>"))])
def test_falls_back_to_rag_with_condense(llm):
    evs = collect(Agent(Generator(llm), fake_retrieve), "học phí?", [("human", "hi"), ("ai", "chào")])
    assert evs[0][1] == {"route": "rag"} and evs[-1][0] == "done"
    assert fake_retrieve.calls == [("câu hỏi viết lại", None, 8)]


ASK = "Bạn hỏi điều kiện của việc gì: nhận học bổng hay xét tốt nghiệp?"


def test_unclear_question_interrupts_and_asks_back():
    llm = FakeLLM(("ask", ASK))
    agent = Agent(Generator(llm), fake_retrieve)
    evs = collect(agent, "điều kiện là gì?", thread_id="conv-1")
    assert [n for n, _ in evs] == ["route", "token", "clarify", "done"] and evs[0][1] == {"route": "clarify"}
    assert evs[1][1] == {"token": ASK} and evs[2][1] == {"question": ASK, "thread_id": "conv-1"}
    assert fake_retrieve.calls == []
    state = asyncio.run(agent.graph.aget_state({"configurable": {"thread_id": "conv-1"}}))
    assert state.next == ("clarify",) and state.interrupts  # graph đang dừng, chờ trả lời


def test_answer_resumes_graph_with_clarified_history():
    llm = FakeLLM(("ask", ASK), ("search", "Điều kiện nhận học bổng khuyến khích là gì?"))
    agent = Agent(Generator(llm), fake_retrieve)
    collect(agent, "điều kiện là gì?", [("human", "chào"), ("ai", "chào bạn")], thread_id="conv-1")
    evs = collect(agent, "học bổng", [("human", "bị bỏ qua khi resume")], thread_id="conv-1")

    assert evs[0][1] == {"route": "rag"} and evs[-1][0] == "done" and evs[-1][1]["cited"] == [1]
    assert fake_retrieve.calls == [("Điều kiện nhận học bổng khuyến khích là gì?", None, 8)]
    sent = decisions(llm)[1][1]  # lượt agent sau khi resume: hội thoại đã có câu hỏi gốc và câu hỏi lại
    assert sent[1:] == [("human", "chào"), ("ai", "chào bạn"), ("human", "điều kiện là gì?"), ("ai", ASK),
                        ("human", "học bổng")]
    state = asyncio.run(agent.graph.aget_state({"configurable": {"thread_id": "conv-1"}}))
    assert not state.values and not state.interrupts  # xong lượt thì thread bị xoá


def test_stops_asking_after_max_clarify():
    llm = FakeLLM(("ask", ASK))  # LLM lúc nào cũng muốn hỏi lại
    agent = Agent(Generator(llm), fake_retrieve)
    for answer in ["điều kiện là gì?", "cái đó", "ừ cái đó"][:MAX_CLARIFY + 1]:
        evs = collect(agent, answer, thread_id="conv-1")
    assert evs[0][1] == {"route": "rag"}  # lần thứ MAX_CLARIFY + 1 không còn tool ask_user
    assert [c[2] for c in decisions(llm)][-1] == ["search_documents", "reply"]
    assert len(fake_retrieve.calls) == 1


def test_new_thread_per_run_leaves_no_checkpoint():
    agent = Agent(Generator(FakeLLM(("search", "q"))), fake_retrieve)
    collect(agent, "học phí?")
    assert not agent.checkpointer.storage
