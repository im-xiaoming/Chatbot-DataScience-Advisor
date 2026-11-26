"""Đăng ký, đăng nhập, bảo vệ /chat và lưu lịch sử hội thoại theo người dùng (api/auth.py)."""
import pytest

from api import auth
from tests.test_api import events


@pytest.fixture
def client(app_client, monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DB", str(tmp_path / "app.db"))
    monkeypatch.setenv("AUTH_REQUIRED", "1")
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    auth._fails.clear()
    return app_client


def signup(c, username="sv01", password="matkhau-an-toan"):
    r = c.post("/auth/register", json={"username": username, "password": password, "display_name": "Sinh viên 01"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_password_is_hashed_and_verified():
    h = auth.hash_password("abc12345")
    assert "abc12345" not in h and h.startswith("scrypt$")
    assert auth.verify_password("abc12345", h) and not auth.verify_password("abc12346", h)


def test_token_rejects_tampering_and_expiry():
    secret = b"k" * 32
    tok = auth.make_token({"id": 1, "username": "a"}, secret)
    assert auth.read_token(tok, secret)["sub"] == "1"
    head, body, sig = tok.split(".")
    assert auth.read_token(f"{head}.{body}x.{sig}", secret) is None
    assert auth.read_token(tok, b"other") is None
    assert auth.read_token(auth.make_token({"id": 1, "username": "a"}, secret, days=-1), secret) is None


def test_register_login_me(client):
    signup(client)
    assert client.post("/auth/register", json={"username": "SV01", "password": "khac-hoan-toan"}).status_code == 409
    assert client.post("/auth/login", json={"username": "sv01", "password": "sai-mat-khau"}).status_code == 401
    r = client.post("/auth/login", json={"username": "sv01", "password": "matkhau-an-toan"})
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).json()
    assert me["username"] == "sv01" and me["display_name"] == "Sinh viên 01"


@pytest.mark.parametrize("username,password", [("ab", "matkhau-an-toan"), ("có dấu", "matkhau-an-toan"),
                                               ("sv02", "")])
def test_register_validates_input(client, username, password):
    assert client.post("/auth/register", json={"username": username, "password": password}).status_code == 422


@pytest.mark.parametrize("password", ["1", "12345678", "sv03"])
def test_register_accepts_any_password(client, password):
    assert client.post("/auth/register", json={"username": "sv03", "password": password}).status_code == 201


def test_login_is_locked_after_repeated_failures(client):
    signup(client)
    for _ in range(auth.MAX_FAILS):
        client.post("/auth/login", json={"username": "sv01", "password": "sai-mat-khau"})
    r = client.post("/auth/login", json={"username": "sv01", "password": "matkhau-an-toan"})
    assert r.status_code == 429


def test_chat_requires_login(client):
    assert client.post("/chat", json={"question": "học phí"}).status_code == 401
    assert client.get("/conversations").status_code == 401
    bad = {"Authorization": "Bearer abc.def.ghi"}
    assert client.post("/chat", json={"question": "học phí"}, headers=bad).status_code == 401


def test_chat_saves_conversation_and_uses_server_history(client):
    h = signup(client)
    evs = list(events(client.post("/chat", json={"question": "buộc thôi học", "goal": "Data Analyst"}, headers=h).text))
    assert evs[0][0] == "conversation" and evs[-1][0] == "done"
    cid = evs[0][1]["id"]

    evs2 = list(events(client.post("/chat", json={"question": "Còn học phí thì sao?", "conversation_id": cid},
                                   headers=h).text))
    assert evs2[0] == ("conversation", {"id": cid, "title": "buộc thôi học"})

    conv = client.get(f"/conversations/{cid}", headers=h).json()
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant", "user", "assistant"]
    bot = conv["messages"][1]
    assert bot["content"] and bot["sources"] and "timing" in bot and "cited" in bot
    assert [c["id"] for c in client.get("/conversations", headers=h).json()] == [cid]


def test_users_cannot_see_each_others_conversations(client):
    a, b = signup(client, "sv_a"), signup(client, "sv_b")
    cid = next(events(client.post("/chat", json={"question": "học phí"}, headers=a).text))[1]["id"]
    assert client.get(f"/conversations/{cid}", headers=b).status_code == 404
    assert client.post("/chat", json={"question": "x", "conversation_id": cid}, headers=b).status_code == 404
    assert client.delete(f"/conversations/{cid}", headers=b).status_code == 404
    assert client.delete(f"/conversations/{cid}", headers=a).json() == {"ok": True}
    assert client.get("/conversations", headers=a).json() == []


def test_feedback_records_username_as_tester(client, monkeypatch, tmp_path):
    from api import feedback
    monkeypatch.setattr(feedback, "FEEDBACK_FILE", tmp_path / "fb.jsonl")
    h = signup(client)
    client.post("/feedback", json={"rating": 1, "question": "q", "answer": "a"}, headers=h)
    assert '"tester": "sv01"' in (tmp_path / "fb.jsonl").read_text(encoding="utf-8")
