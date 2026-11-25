import json
import os

os.environ.update(RETRIEVER="fake", LLM="fake", AUTH_REQUIRED="0", APP_DB=":memory:")  # đặt trước khi import app

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402


def events(text):
    for block in text.strip().split("\n\n"):
        ev = next((l[7:] for l in block.splitlines() if l.startswith("event: ")), "token")
        data = json.loads(next(l[6:] for l in block.splitlines() if l.startswith("data: ")))
        yield ev, data


def test_chat_streams_sources_then_tokens_then_done():
    r = TestClient(app).post("/chat", json={"question": "buộc thôi học", "goal": "Data Analyst"})
    evs = list(events(r.text))
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    assert evs[0][0] == "sources" and 1 <= len(evs[0][1]["sources"]) <= 8
    assert evs[-1][0] == "done" and "first_token_ms" in evs[-1][1]
    assert sum(1 for e, _ in evs if e == "token") > 5


def test_category_filter_is_applied():
    r = TestClient(app).post("/chat", json={"question": "học phí", "category": "scholarship_tuition"})
    _, data = next(events(r.text))
    assert {s["category"] for s in data["sources"]} == {"scholarship_tuition"}


def test_health_reports_modes():
    assert TestClient(app).get("/health").json() == {"retriever": "fake", "llm": "fake", "rerank": False, "auth": False}


def test_done_event_reports_citations():
    r = TestClient(app).post("/chat", json={"question": "buộc thôi học"})
    done = [d for e, d in events(r.text) if e == "done"][0]
    assert done["cited"] and done["invalid_citations"] == []


def test_follow_up_emits_query_event_only_with_history():
    c = TestClient(app)
    first = [e for e, _ in events(c.post("/chat", json={"question": "học phí"}).text)]
    assert "query" not in first


def test_chat_with_reranker(monkeypatch):
    import api.main as m
    from api.rerank import Reranker
    monkeypatch.setattr(m, "reranker", Reranker(scorer=lambda pairs: [len(d) for _, d in pairs]))
    evs = list(events(TestClient(app).post("/chat", json={"question": "học bổng khuyến khích"}).text))
    assert evs[0][0] == "sources" and len(evs[0][1]["sources"]) <= m.TOP_K
    assert evs[-1][0] == "done"
