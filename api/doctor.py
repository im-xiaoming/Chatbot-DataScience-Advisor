"""Kiểm tra máy đã đủ để chạy chatbot chưa, và gợi ý lệnh chạy phù hợp.

Chạy:  uv run python -m api.doctor
Chỉ dùng thư viện chuẩn để kiểm tra Ollama / Qdrant / Postgres, nên chạy được cả khi cài thiếu gói.
Chạy trước khi bật API: mỗi dòng in ra (✓ / ! / ✗) kèm gợi ý sửa; thoát mã 1 nếu có dòng ✗.
"""
from __future__ import annotations

import importlib.util
import json
import socket
import sys
import time
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.types import DoctorRow as Row  # (trạng thái, tên mục, chi tiết, gợi ý sửa)

OK, WARN, FAIL = "✓", "!", "✗"
OLLAMA = "http://localhost:11434"
QDRANT = "http://localhost:6333"
COLLECTION = "QQ"


def http_json(url: str, payload: dict | None = None, timeout: float = 3) -> dict:
    """GET (hoặc POST nếu có payload) và đọc JSON; lỗi mạng/HTTP để nguyên cho hàm gọi bắt."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def configured_models() -> tuple[str, str]:
    """(model chat, model embedding) theo config của nhóm; đọc lỗi (thiếu gói, thiếu .env) thì dùng tên mặc định."""
    try:
        from config import EmbeddingsConfig, LLMConfig
        return LLMConfig().model_name, EmbeddingsConfig().model_name
    except Exception:
        return "qwen3.5:4b", "qwen3-embedding:4b"


def check_python() -> Row:
    v = sys.version_info
    status = OK if v >= (3, 13) else WARN
    return status, "Python", f"{v.major}.{v.minor}", "" if status == OK else "repo yêu cầu Python 3.13 (.python-version)"


def check_packages() -> Row:
    need = ["fastapi", "uvicorn", "langchain_ollama", "qdrant_client", "underthesea", "pytest"]
    missing = [p for p in need if importlib.util.find_spec(p) is None]
    if missing:
        return FAIL, "Thư viện", "thiếu " + ", ".join(missing), "uv sync && uv add fastapi uvicorn pytest pytest-asyncio httpx"
    return OK, "Thư viện", "đủ", ""


def check_data() -> Row:
    n = len(list(Path("data/normalized").glob("*/*.md")))
    plan = Path("data/normalized/curriculum/iuh-khdl-ke-hoach-dao-tao-2023.md").exists()
    if n == 0:
        return FAIL, "Dữ liệu", "không thấy data/normalized", "chạy lệnh từ thư mục gốc của repo"
    return (OK if plan else WARN), "Dữ liệu", f"{n} tài liệu" + ("" if plan else ", thiếu niên giám 2023"), ""


def check_ollama() -> list[Row]:
    """Ollama có chạy không, đã tải đủ 2 model chưa, và thử sinh một câu ngắn để đo tốc độ (> 20 s thì cảnh báo)."""
    llm, emb = configured_models()
    try:
        tags = http_json(f"{OLLAMA}/api/tags")
    except Exception:
        return [(FAIL, "Ollama", "không kết nối được localhost:11434", "mở ứng dụng Ollama hoặc chạy `ollama serve`")]
    have = {m["name"] for m in tags.get("models", [])} | {m["name"].split(":")[0] for m in tags.get("models", [])}
    rows = [(OK, "Ollama", "đang chạy", "")]
    for name in (llm, emb):
        rows.append((OK, f"Model {name}", "đã tải", "") if name in have
                    else (FAIL, f"Model {name}", "chưa tải", f"ollama pull {name}"))
    if llm in have:
        t0 = time.perf_counter()
        try:
            out = http_json(f"{OLLAMA}/api/generate", {"model": llm, "prompt": "Trả lời một từ: xin chào",
                                                         "stream": False, "think": False,
                                                         "options": {"num_predict": 8}}, timeout=180)
            dt = time.perf_counter() - t0
            status = OK if dt < 20 else WARN
            hint = "" if status == OK else "chậm (có thể chạy CPU); làm giao diện thì dùng LLM=fake"
            rows.append((status, "Thử sinh câu", f"{dt:.1f} s: {out.get('response', '').strip()[:30]!r}", hint))
        except Exception as e:
            rows.append((FAIL, "Thử sinh câu", type(e).__name__, "xem log của Ollama"))
    return rows


def check_qdrant() -> list[Row]:
    """Qdrant có chạy và có collection QQ với dữ liệu không (chỉ cảnh báo: tìm kiếm giả không cần Qdrant)."""
    try:
        cols = [c["name"] for c in http_json(f"{QDRANT}/collections")["result"]["collections"]]
    except Exception:
        return [(WARN, "Qdrant", "chưa chạy (chỉ cần cho RETRIEVER=qdrant)",
                 "docker run -d -p 6333:6333 qdrant/qdrant")]
    if COLLECTION not in cols:
        return [(WARN, "Qdrant", f"đang chạy, chưa có collection {COLLECTION}",
                 f"uv run python pipline.py --collection_name {COLLECTION}")]
    n = http_json(f"{QDRANT}/collections/{COLLECTION}")["result"].get("points_count", 0)
    return [(OK if n else WARN, "Qdrant", f"collection {COLLECTION}: {n} điểm", "" if n else "nạp lại bằng pipline.py")]


def check_postgres() -> Row:
    """Postgres và file .env chỉ cần cho pipline.py (nạp dữ liệu), không cần để chạy API."""
    env = Path(".env").exists()
    up = port_open("localhost", 5432)
    if env and up:
        return OK, "Postgres", "đang chạy, có .env", ""
    hint = "docker compose up -d" if not up else "tạo file .env (xem hướng dẫn cài đặt)"
    return WARN, "Postgres", ("chưa chạy" if not up else "thiếu .env") + " (chỉ cần khi chạy pipline.py)", hint


def run() -> list[Row]:
    """Chạy mọi bước kiểm tra theo thứ tự in ra."""
    rows = [check_python(), check_packages(), check_data()]
    rows += check_ollama()
    rows += check_qdrant()
    rows.append(check_postgres())
    return rows


def suggest(rows: list[Row]) -> str:
    """Lệnh uvicorn hợp với máy: Qdrant chạy thì RETRIEVER=qdrant, Ollama hoặc model thiếu thì LLM=fake."""
    st = {name: s for s, name, _, _ in rows}
    llm_ok = all(s == OK for n, s in st.items() if n.startswith("Model") or n == "Ollama")
    qdrant_ok = st.get("Qdrant") == OK
    env = []
    if qdrant_ok:
        env.append("RETRIEVER=qdrant")
    if not llm_ok:
        env.append("LLM=fake")
    prefix = (" ".join(env) + " ") if env else ""
    return f"{prefix}uv run uvicorn api.main:app --reload   (Windows PowerShell: đặt biến bằng $env:TÊN=\"giá trị\";)"


def main() -> None:
    rows = run()
    w = max(len(r[1]) for r in rows)
    for s, name, detail, hint in rows:
        print(f" {s}  {name:<{w}}  {detail}" + (f"\n    → {hint}" if hint else ""))
    print("\nLệnh chạy gợi ý:\n  " + suggest(rows))
    sys.exit(1 if any(r[0] == FAIL for r in rows) else 0)


if __name__ == "__main__":
    main()
