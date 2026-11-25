"""Đồ giả để làm và test giao diện khi chưa có Qdrant / chưa muốn gọi Ollama.

- fake_retrieve: tìm theo từ khoá trên các chunk tạo bằng chính Splitter của nhóm từ data/normalized/
  (giống hệt chunk sẽ nạp vào Qdrant). Không dùng data/chunks.jsonl vì file đó là bản cũ, chunk quá dài.
- FakeLLM: nhả một câu trả lời mẫu dạng Markdown, từng mẩu nhỏ như token thật.
Bật bằng RETRIEVER=fake (mặc định) và/hoặc LLM=fake khi chạy api/main.py; tests/ luôn dùng cả hai.
"""
from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from types import SimpleNamespace

from rag.generation.types import Point


def load_chunks(path: str = "data/chunks.jsonl") -> list[dict]:
    """Đọc file chunk cũ (nhiều object JSON viết liền nhau). Hiện không nơi nào gọi; fake_retrieve dùng build_chunks."""
    # File gồm nhiều object JSON viết liền (indent=4), không phải 1 dòng/1 object
    text, dec, i, out = Path(path).read_text(encoding="utf-8"), json.JSONDecoder(), 0, []
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        obj, i = dec.raw_decode(text, i)
        out.append(obj)
    return out


def build_chunks(glob_path: str = "./data/normalized/") -> list[Point]:
    """Chia chunk bằng code thật của nhóm 3 (rag/ingestion/loaders.py).

    Chạy một lần khi fake_retrieve được gọi lần đầu (vài giây, có import torch qua rag.ingestion).
    """
    from config import RecursiveCharacterTextSplitterConfig
    from rag.ingestion.loaders import Record, Splitter
    _, chunks = Splitter(recursive_config=RecursiveCharacterTextSplitterConfig()).split_documents(glob_path)
    # mypy báo 2 lỗi ở hai dòng dưới do khai báo kiểu trong rag/ingestion (nhận list[Document], data có thể None)
    records = Record.build_chunk_records(chunks)
    return [json.loads(r.data.model_dump_json()) for r in records]


_CHUNKS: list[Point] | None = None


async def fake_retrieve(question: str, category: str | None = None, k: int = 5) -> list[Point]:
    """Tìm kiếm giả theo từ khoá: điểm = tỉ lệ từ của câu hỏi có trong tiêu đề + nội dung chunk.

    Cùng cách gọi với api.rag_service.retrieve (trừ tham số strategy), để api/main.py đổi qua lại bằng
    RETRIEVER mà không sửa code. Làm mốc so sánh cho tìm kiếm thật trong eval/run_retrieval.py.
    """
    global _CHUNKS
    _CHUNKS = _CHUNKS or build_chunks()
    words = {w for w in re.findall(r"\w+", question.lower()) if len(w) > 1}
    pool = [c for c in _CHUNKS if not category or c["category"] == category]

    def score(c: Point) -> float:
        text = (c["title"] + " " + c["page_content"]).lower()
        return sum(w in text for w in words) / (len(words) or 1)

    ranked: list[Point]
    ranked, seen = [], set()
    for c in sorted(pool, key=score, reverse=True):
        if c["page_content"] in seen:  # data/chunks.jsonl có chunk trùng nội dung
            continue
        seen.add(c["page_content"])
        ranked.append({**c, "score": round(score(c), 3)})
        if len(ranked) == k:
            break
    return ranked


class FakeLLM:
    """Giả lập chat model của LangChain: .ainvoke() và .astream() trả về object có .content."""

    async def ainvoke(self, messages: Sequence[tuple[str, str]]) -> SimpleNamespace:
        """Bước viết lại câu hỏi: trả lại nguyên phần sau "CÂU HỎI MỚI:" của prompt."""
        # Dùng cho bước viết lại câu hỏi: trả lại nguyên câu hỏi mới
        return SimpleNamespace(content=messages[-1][1].split("CÂU HỎI MỚI:")[-1].strip())

    async def astream(self, messages: Sequence[tuple[str, str]]) -> AsyncIterator[SimpleNamespace]:
        """Stream một câu trả lời mẫu liệt kê các tài liệu [n] trong NGỮ CẢNH, mỗi mẩu 4 ký tự, cách nhau 12 ms."""
        ctx = messages[-1][1]
        titles = re.findall(r"^\[(\d+)\] ([^\n—(]+)", ctx, flags=re.M)
        rows = "\n".join(f"| [{n}] | {t} |" for n, t in titles) or "| - | Không tìm thấy tài liệu |"
        answer = (
            "> *Chế độ thử: đây là câu trả lời mẫu, chưa gọi LLM thật. "
            "Bật Ollama bằng LLM=ollama để có câu trả lời thật.*\n\n"
            "### Tài liệu tìm được\n\n"
            f"| Số | Tài liệu |\n|---|---|\n{rows}\n\n"
            "Khi chạy với LLM thật, câu trả lời sẽ dựa trên các tài liệu này và ghi nguồn "
            "ngay sau mỗi ý, ví dụ [1]."
        )
        for piece in re.findall(r".{1,4}", answer, flags=re.S):
            await asyncio.sleep(0.012)
            yield SimpleNamespace(content=piece)
