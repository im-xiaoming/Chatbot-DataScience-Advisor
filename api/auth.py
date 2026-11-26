"""Đăng ký / đăng nhập và lưu lịch sử trò chuyện theo từng người dùng.

Chỉ dùng thư viện chuẩn của Python, không cần cài thêm gói:
  - Mật khẩu băm bằng scrypt (hashlib), mỗi người một salt ngẫu nhiên; không lưu mật khẩu gốc.
  - Token đăng nhập là JWT HS256 tự ký bằng hmac (hạn mặc định 7 ngày), gửi qua header
    "Authorization: Bearer <token>".
  - Dữ liệu ở SQLite, file data/app.db (đổi bằng biến APP_DB). File này không đưa lên git.

Biến môi trường:
  APP_DB=data/app.db        nơi lưu người dùng và hội thoại
  AUTH_SECRET=...            khoá ký token; bỏ trống thì tự sinh một lần và lưu trong APP_DB
  AUTH_REQUIRED=1            0 = cho phép chat không cần đăng nhập (dùng khi chạy eval, demo nhanh)
  TOKEN_DAYS=7

Endpoint: POST /auth/register · POST /auth/login · GET /auth/me
          GET /conversations · GET /conversations/{id} · DELETE /conversations/{id}
api/main.py dùng chat_user (bảo vệ /chat) và Store (lấy lịch sử, lưu câu hỏi/câu trả lời).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from api.types import Claims, Conversation, MessageMeta, StoredMessage, User

router = APIRouter()

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    goal TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_conv_user ON conversations(user_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    meta TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_msg_conv ON messages(conversation_id, id);
"""


def auth_required() -> bool:
    """/chat có bắt đăng nhập không (đọc AUTH_REQUIRED mỗi lần gọi để test đổi được bằng monkeypatch)."""
    return os.getenv("AUTH_REQUIRED", "1") != "0"


# ---------------------------------------------------------------- lưu trữ
class Store:
    """Lớp mỏng trên SQLite: người dùng, cuộc trò chuyện, tin nhắn.

    Mỗi thao tác mở một kết nối riêng (SQLite chịu được, và an toàn khi FastAPI chạy nhiều luồng);
    riêng ":memory:" giữ một kết nối dùng chung vì mỗi kết nối mới sẽ là một CSDL rỗng khác.
    Mọi hàm đọc/ghi hội thoại đều lọc theo user_id để người này không xem được hội thoại của người khác.

    Args:
        path: đường dẫn file SQLite (tự tạo thư mục) hoặc ":memory:" (test).
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._mem = sqlite3.connect(":memory:", check_same_thread=False) if str(path) == ":memory:" else None
        self._lock = Lock()
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        """Kết nối có bật khoá ngoại; tự commit khi khối with kết thúc không lỗi.

        Khoá _lock tuần tự hoá các thao tác trong cùng tiến trình, tránh lỗi "database is locked".
        """
        c = self._mem or sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        try:
            with self._lock:
                yield c
                c.commit()
        finally:
            if not self._mem:
                c.close()

    # -- khoá ký token
    def secret(self) -> bytes:
        """Khoá ký token: AUTH_SECRET nếu có, không thì sinh một lần và lưu trong bảng meta.

        Lưu trong CSDL để khởi động lại server không làm mất hiệu lực token đang dùng.
        """
        if os.getenv("AUTH_SECRET"):
            return os.environ["AUTH_SECRET"].encode()
        if not getattr(self, "_secret", None):
            with self.conn() as c:
                row = c.execute("SELECT value FROM meta WHERE key='auth_secret'").fetchone()
                if not row:
                    c.execute("INSERT INTO meta(key, value) VALUES ('auth_secret', ?)", (secrets.token_hex(32),))
                    row = c.execute("SELECT value FROM meta WHERE key='auth_secret'").fetchone()
                self._secret = row["value"].encode()
        return self._secret

    # -- người dùng
    def create_user(self, username: str, display_name: str, password: str) -> User:
        """Tạo người dùng mới (mật khẩu được băm trước khi lưu).

        Raises:
            HTTPException: 409 nếu tên đăng nhập đã có (không phân biệt hoa thường).
        """
        try:
            with self.conn() as c:
                cur = c.execute("INSERT INTO users(username, display_name, password_hash, created_at) VALUES (?,?,?,?)",
                                (username, display_name, hash_password(password), time.time()))
                return {"id": cur.lastrowid, "username": username, "display_name": display_name}  # type: ignore[typeddict-item]  # lastrowid luôn có sau INSERT
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Tên đăng nhập đã có người dùng")

    def check_login(self, username: str, password: str) -> User | None:
        """Kiểm tra tên/mật khẩu; None nếu sai. Tên không tồn tại vẫn băm thử một lần để thời gian phản hồi như nhau."""
        with self.conn() as c:
            row = c.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row and verify_password(password, row["password_hash"]):
            return {"id": row["id"], "username": row["username"], "display_name": row["display_name"]}
        if not row:
            verify_password(password, _DUMMY_HASH)  # tốn thời gian như nhau, không lộ tên nào đã tồn tại
        return None

    def get_user(self, uid: int) -> User | None:
        with self.conn() as c:
            row = c.execute("SELECT id, username, display_name FROM users WHERE id = ?", (uid,)).fetchone()
        return dict(row) if row else None  # type: ignore[return-value]  # dict từ sqlite3.Row đúng các cột của User

    # -- hội thoại
    def create_conversation(self, uid: int, title: str, goal: str | None) -> Conversation:
        """Tạo cuộc trò chuyện mới; tiêu đề lấy từ câu hỏi đầu, gộp khoảng trắng, tối đa 80 ký tự."""
        now = time.time()
        title = re.sub(r"\s+", " ", title).strip()[:80] or "Cuộc trò chuyện"
        with self.conn() as c:
            cur = c.execute("INSERT INTO conversations(user_id, title, goal, created_at, updated_at) VALUES (?,?,?,?,?)",
                            (uid, title, goal, now, now))
        return {"id": cur.lastrowid, "title": title, "goal": goal, "updated_at": now}  # type: ignore[typeddict-item]  # lastrowid luôn có sau INSERT

    def get_conversation(self, uid: int, cid: int) -> Conversation | None:
        """Cuộc trò chuyện cid nếu thuộc về người dùng uid, ngược lại None."""
        with self.conn() as c:
            row = c.execute("SELECT id, title, goal, updated_at FROM conversations WHERE id = ? AND user_id = ?",
                            (cid, uid)).fetchone()
        return dict(row) if row else None  # type: ignore[return-value]  # dict từ sqlite3.Row đúng các cột của Conversation

    def list_conversations(self, uid: int, limit: int = 50) -> list[Conversation]:
        """Các cuộc trò chuyện của uid, mới cập nhật trước."""
        with self.conn() as c:
            rows = c.execute("SELECT id, title, goal, updated_at FROM conversations WHERE user_id = ? "
                             "ORDER BY updated_at DESC LIMIT ?", (uid, limit)).fetchall()
        return [dict(r) for r in rows]  # type: ignore[misc]  # dict từ sqlite3.Row đúng các cột của Conversation

    def delete_conversation(self, uid: int, cid: int) -> bool:
        """Xoá cuộc trò chuyện (tin nhắn xoá theo nhờ ON DELETE CASCADE); False nếu không có hoặc không thuộc uid."""
        with self.conn() as c:
            return c.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?", (cid, uid)).rowcount > 0

    def add_message(self, cid: int, role: str, content: str, meta: MessageMeta | None = None) -> int:
        """Lưu một tin nhắn và đẩy cuộc trò chuyện lên đầu danh sách.

        Args:
            cid: id cuộc trò chuyện (người gọi đã kiểm tra quyền sở hữu).
            role: "user" | "assistant".
            content: nội dung; câu trả lời bị dừng giữa chừng vẫn lưu phần đã có.
            meta: thông tin kèm câu trả lời (nguồn, thời gian, lỗi...), lưu dạng JSON.

        Returns:
            id của tin nhắn.
        """
        now = time.time()
        with self.conn() as c:
            cur = c.execute("INSERT INTO messages(conversation_id, role, content, meta, created_at) VALUES (?,?,?,?,?)",
                            (cid, role, content, json.dumps(meta, ensure_ascii=False) if meta else None, now))
            c.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, cid))
            return cur.lastrowid  # type: ignore[return-value]  # lastrowid luôn có sau INSERT

    def messages(self, cid: int) -> list[StoredMessage]:
        """Mọi tin nhắn của cuộc trò chuyện theo thứ tự gửi, đã trải các khoá của meta ra ngoài."""
        with self.conn() as c:
            rows = c.execute("SELECT id, role, content, meta, created_at FROM messages WHERE conversation_id = ? "
                             "ORDER BY id", (cid,)).fetchall()
        return [{"id": r["id"], "role": r["role"], "content": r["content"], "created_at": r["created_at"],
                 **(json.loads(r["meta"]) if r["meta"] else {})} for r in rows]  # type: ignore[typeddict-item]  # meta là JSON do add_message ghi (MessageMeta)

    def history(self, cid: int, max_turns: int = 10) -> list[tuple[str, str]]:
        """Lịch sử dạng (human|ai, nội dung) cho bước viết lại câu hỏi nối tiếp; bỏ câu trả lời lỗi/rỗng."""
        msgs = [m for m in self.messages(cid) if m["content"] and not m.get("error")]
        return [("human" if m["role"] == "user" else "ai", m["content"]) for m in msgs[-max_turns:]]


_stores: dict[str, Store] = {}


def get_store() -> Store:
    """Store của APP_DB hiện tại (mỗi đường dẫn một Store; test đổi APP_DB sang file tạm là có CSDL mới)."""
    path = os.getenv("APP_DB", "data/app.db")
    if path not in _stores:
        _stores[path] = Store(path)
    return _stores[path]


# ---------------------------------------------------------------- mật khẩu
def hash_password(password: str, *, n: int = 2 ** 14, r: int = 8, p: int = 1) -> str:
    """Băm mật khẩu bằng scrypt với salt ngẫu nhiên 16 byte.

    Returns:
        "scrypt$n$r$p$salt_hex$hash_hex" — lưu kèm tham số để sau này tăng n vẫn kiểm tra được hash cũ.
    """
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${salt.hex()}${h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """So mật khẩu với hash đã lưu (so sánh thời gian hằng số); hash sai định dạng thì trả False."""
    try:
        _, n, r, p, salt, h = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(got.hex(), h)
    except ValueError:
        return False


_DUMMY_HASH = hash_password(secrets.token_hex(8))


# ---------------------------------------------------------------- token (JWT HS256)
def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(user: User, secret: bytes, days: float | None = None) -> str:
    """Tạo JWT HS256 cho người dùng.

    Args:
        user: cần "id" và "username".
        secret: khoá ký (Store.secret()).
        days: hạn dùng; None = TOKEN_DAYS (mặc định 7). Số âm dùng trong test để tạo token đã hết hạn.
    """
    days = days if days is not None else float(os.getenv("TOKEN_DAYS", "7"))
    now = int(time.time())
    head = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64(json.dumps({"sub": str(user["id"]), "name": user["username"], "iat": now,
                            "exp": now + int(days * 86400)}).encode())
    sig = _b64(hmac.new(secret, f"{head}.{body}".encode(), hashlib.sha256).digest())
    return f"{head}.{body}.{sig}"


def read_token(token: str, secret: bytes) -> Claims | None:
    """Kiểm tra chữ ký, thuật toán (chỉ nhận HS256, chặn kiểu tấn công "alg: none") và hạn của token.

    Returns:
        Claims nếu hợp lệ, None nếu sai chữ ký, sai định dạng hoặc đã hết hạn.
    """
    try:
        head, body, sig = token.split(".")
        want = _b64(hmac.new(secret, f"{head}.{body}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, want) or json.loads(_unb64(head)).get("alg") != "HS256":
            return None
        claims = json.loads(_unb64(body))
        return claims if claims.get("exp", 0) > time.time() else None
    except (ValueError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------- phụ thuộc FastAPI
def optional_user(request: Request) -> User | None:
    """Người dùng từ header Authorization; None nếu không có token hoặc token không hợp lệ."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    store = get_store()
    claims = read_token(auth[7:].strip(), store.secret())
    return store.get_user(int(claims["sub"])) if claims else None


def current_user(user: dict | None = Depends(optional_user)) -> User:
    """Bắt buộc đăng nhập.

    Raises:
        HTTPException: 401 kèm header WWW-Authenticate nếu chưa đăng nhập.
    """
    if not user:
        raise HTTPException(401, "Bạn cần đăng nhập", headers={"WWW-Authenticate": "Bearer"})
    return user  # type: ignore[return-value]  # là User từ optional_user; tham số ghi dict vì FastAPI đọc annotation


def chat_user(user: dict | None = Depends(optional_user)) -> User | None:
    """Dùng cho /chat: bắt buộc đăng nhập, trừ khi AUTH_REQUIRED=0."""
    if user is None and auth_required():
        raise HTTPException(401, "Bạn cần đăng nhập", headers={"WWW-Authenticate": "Bearer"})
    return user  # type: ignore[return-value]  # như current_user


# ---------------------------------------------------------------- chống dò mật khẩu (đơn giản, trong bộ nhớ)
# Mỗi (tên đăng nhập, IP) sai quá MAX_FAILS lần trong WINDOW giây thì khoá tạm. Lưu trong bộ nhớ nên
# khởi động lại server là mất; đủ cho một máy chủ demo, chạy nhiều tiến trình thì cần Redis hoặc tương tự.
_fails: dict[str, list[float]] = {}
MAX_FAILS, WINDOW = 5, 300


def _too_many(key: str) -> bool:
    now = time.time()
    _fails[key] = [t for t in _fails.get(key, []) if now - t < WINDOW]
    return len(_fails[key]) >= MAX_FAILS


# ---------------------------------------------------------------- endpoint
# Endpoint cố ý không ghi kiểu trả về: FastAPI dùng kiểu trả về làm response_model (lọc và kiểm tra dữ liệu),
# thêm vào sẽ đổi hành vi. Tham số Depends(...) giữ kiểu dict vì FastAPI đọc annotation này lúc chạy, còn
# User chỉ import khi kiểm tra kiểu. Kiểu dữ liệu thật ghi trong docstring (xem api/types.py).
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,32}$")


class RegisterIn(BaseModel):
    """Body của POST /auth/register."""

    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=128)  # đặt tùy ý, chỉ cần không rỗng
    display_name: str | None = Field(default=None, max_length=60)


class LoginIn(BaseModel):
    """Body của POST /auth/login."""

    username: str = Field(max_length=32)
    password: str = Field(max_length=128)


def _session(user: User) -> dict[str, Any]:
    return {"token": make_token(user, get_store().secret()), "user": user}


@router.post("/auth/register", status_code=201)
async def register(body: RegisterIn):
    """Đăng ký và đăng nhập luôn.

    Returns:
        {"token": ..., "user": User}.

    Raises:
        HTTPException: 422 tên đăng nhập/mật khẩu không hợp lệ, 409 tên đã có người dùng.
    """
    username = body.username.strip()
    if not USERNAME_RE.match(username):
        raise HTTPException(422, "Tên đăng nhập 3–32 ký tự, chỉ gồm chữ không dấu, số, dấu _ hoặc .")
    name = (body.display_name or "").strip() or username
    return _session(get_store().create_user(username, name, body.password))


@router.post("/auth/login")
async def login(body: LoginIn, request: Request):
    """Đăng nhập.

    Returns:
        {"token": ..., "user": User}.

    Raises:
        HTTPException: 401 sai tên hoặc mật khẩu (cùng một thông báo, không lộ tên nào tồn tại),
            429 sai quá 5 lần trong 5 phút.
    """
    key = f"{body.username.lower()}|{request.client.host if request.client else ''}"
    if _too_many(key):
        raise HTTPException(429, "Sai mật khẩu quá nhiều lần, thử lại sau 5 phút")
    user = get_store().check_login(body.username.strip(), body.password)
    if not user:
        _fails.setdefault(key, []).append(time.time())
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    _fails.pop(key, None)
    return _session(user)


@router.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    """Người dùng của token hiện tại; giao diện gọi khi tải lại trang để biết token còn dùng được không."""
    return user


@router.get("/conversations")
async def conversations(user: dict = Depends(current_user)):
    """Danh sách cuộc trò chuyện của người dùng (tối đa 50, mới nhất trước)."""
    return get_store().list_conversations(user["id"])


@router.get("/conversations/{cid}")
async def conversation(cid: int, user: dict = Depends(current_user)):
    """Một cuộc trò chuyện kèm toàn bộ tin nhắn.

    Raises:
        HTTPException: 404 nếu không có hoặc thuộc người khác (không phân biệt hai trường hợp).
    """
    store = get_store()
    conv = store.get_conversation(user["id"], cid)
    if not conv:
        raise HTTPException(404, "Không tìm thấy cuộc trò chuyện")
    return {**conv, "messages": store.messages(cid)}


@router.delete("/conversations/{cid}")
async def delete_conversation(cid: int, user: dict = Depends(current_user)):
    """Xoá một cuộc trò chuyện của người dùng.

    Raises:
        HTTPException: 404 nếu không có hoặc thuộc người khác.
    """
    if not get_store().delete_conversation(user["id"], cid):
        raise HTTPException(404, "Không tìm thấy cuộc trò chuyện")
    return {"ok": True}
