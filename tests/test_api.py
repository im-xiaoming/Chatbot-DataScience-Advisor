import json
import os

os.environ.update(AUTH_REQUIRED="0", APP_DB=":memory:")  # đặt trước khi app_client (tests/conftest.py) import app


def events(text):
    for block in text.strip().split("\n\n"):
        ev = next((l[7:] for l in block.splitlines() if l.startswith("event: ")), "token")
        data = json.loads(next(l[6:] for l in block.splitlines() if l.startswith("data: ")))
        yield ev, data


def test_chat_streams_sources_then_tokens_then_done(app_client):
    r = app_client.post("/chat", json={"question": "buộc thôi học", "goal": "Data Analyst"})
    evs = list(events(r.text))
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    names = [e for e, _ in evs]
    assert evs[0] == ("route", {"route": "rag"})  # agent gọi tool search_documents
    assert names.index("sources") < names.index("token")
    assert 1 <= len(dict(evs)["sources"]["sources"]) <= 8
    assert evs[-1][0] == "done" and "first_token_ms" in evs[-1][1]
    assert sum(1 for e, _ in evs if e == "token") > 5


def test_category_filter_is_applied(app_client):
    r = app_client.post("/chat", json={"question": "học phí", "filters": {"category": "scholarship_tuition"}})
    data = next(d for e, d in events(r.text) if e == "sources")
    assert {s["category"] for s in data["sources"]} == {"scholarship_tuition"}


def test_unknown_filter_field_is_rejected(app_client):
    r = app_client.post("/chat", json={"question": "học phí", "filters": {"catgory": "regulation"}})  # gõ sai tên
    assert r.status_code == 422


def test_health_reports_modes(app_client):
    assert app_client.get("/health").json() == {"retriever": "qdrant", "llm": "ollama", "rerank": False, "auth": False}


def test_done_event_reports_citations(app_client):
    r = app_client.post("/chat", json={"question": "buộc thôi học"})
    done = [d for e, d in events(r.text) if e == "done"][0]
    assert done["cited"] and done["invalid_citations"] == []


def test_small_talk_answers_without_search(app_client):
    evs = list(events(app_client.post("/chat", json={"question": "xin chào"}).text))
    assert evs[0] == ("route", {"route": "small_talk"})  # agent không gọi tool
    assert [e for e, _ in evs[1:]] == ["token", "done"] and evs[-1][1]["cited"] == []


def test_chat_with_reranker(app_client, monkeypatch):
    import api.main as m
    from rag.rerank import Reranker
    monkeypatch.setattr(m.agent, "reranker", Reranker(scorer=lambda pairs: [len(d) for _, d in pairs]))
    evs = list(events(app_client.post("/chat", json={"question": "học bổng khuyến khích"}).text))
    assert len(dict(evs)["sources"]["sources"]) <= m.TOP_K
    assert evs[-1][0] == "done"


def test_thread_id_from_clarify_never_causes_422(app_client):
    """Giao diện gửi lại thread_id của sự kiện clarify, kể cả "conv-..." của người đã đăng nhập: không được 422."""
    for tid in ["conv-1", "anon-" + "0" * 32, "rác"]:
        r = app_client.post("/chat", json={"question": "xin chào", "thread_id": tid})
        assert r.status_code == 200
