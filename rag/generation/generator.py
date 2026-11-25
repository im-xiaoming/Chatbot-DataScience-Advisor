"""Khâu Generation của RAG: từ câu hỏi + các chunk tìm được -> câu trả lời stream từng token.

Vị trí trong luồng (api/main.py, eval/run_answers.py):
  condense (viết lại câu hỏi nối tiếp) -> search_query -> [tìm kiếm, nhóm 3/5] -> select_points
  -> build_messages -> stream.
Dùng với bất kỳ chat model nào của LangChain (có .astream và .ainvoke), ví dụ ChatOllama
từ agent.models.load_llm_model; test dùng LLM giả có cùng hai phương thức này.
"""
from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator, Sequence
from typing import Any

from .prompts import (
    CONDENSE_PROMPT, INTENT_KEYWORDS, INTENT_RULES, NO_CONTEXT_ANSWER, SYSTEM_PROMPT,
)
from .types import Point

logger = logging.getLogger(__name__)

Message = tuple[str, str]  # ("system" | "human" | "ai", nội dung)


def detect_intent(question: str) -> str:
    """Đoán loại câu hỏi theo từ khoá; trả về 'general' nếu không khớp loại nào.

    Dùng từ khoá thay vì hỏi LLM để không tốn thêm một lượt gọi model (mỗi lượt ~3-10 s trên máy 4 GB VRAM).
    Hoà điểm thì lấy loại khai báo trước trong INTENT_KEYWORDS.

    Returns:
        Một khoá của INTENT_RULES: course_plan, career, graduation, market hoặc general.
    """
    q = question.lower()
    hits = {name: sum(k in q for k in kws) for name, kws in INTENT_KEYWORDS.items()}
    best = max(hits, key=hits.get)  # type: ignore[arg-type]  # dict.get dùng làm key là hợp lệ, mypy không suy ra được overload
    return best if hits[best] else "general"


def format_point(i: int, p: Point) -> str:
    """Một tài liệu trong NGỮ CẢNH: số thứ tự, tiêu đề, mục, hiệu lực, nội dung.

    Chỉ giữ 2 cấp cuối của section_path cho gọn; ghi ngày ban hành / hiệu lực để LLM
    không lấy quy định đã hết hạn.

    Args:
        i: số thứ tự bắt đầu từ 1, chính là số LLM dùng để trích dẫn [i].
        p: chunk đã chọn.
    """
    head = f"[{i}] {p.get('title', '')}"
    section = p.get("section_path") or []
    if section:
        head += " — " + " › ".join(section[-2:])
    meta = []
    if p.get("published_date"):
        meta.append(f"ban hành {str(p['published_date'])[:10]}")
    if p.get("valid_until"):
        meta.append(f"hiệu lực đến {str(p['valid_until'])[:10]}")
    if meta:
        head += f" ({', '.join(meta)})"
    return f"{head}\n{p.get('page_content', '').strip()}"


def extract_citations(text: str, n_sources: int) -> tuple[list[int], list[int]]:
    """Tách các số trích dẫn [n] trong câu trả lời.

    Returns:
        (các số hợp lệ 1..n_sources, các số trỏ tới nguồn không tồn tại), mỗi danh sách đã sắp xếp, không trùng.
    """
    nums = sorted({int(m) for m in re.findall(r"\[(\d{1,2})\]", text)})
    return [n for n in nums if 1 <= n <= n_sources], [n for n in nums if not 1 <= n <= n_sources]


class ThinkFilter:
    """Bỏ phần <think>...</think> của model suy luận (Qwen) khỏi luồng token,
    kể cả khi thẻ bị cắt ngang giữa hai token.

    Cách dùng: gọi feed() cho từng token, cuối luồng gọi flush() để lấy phần còn giữ lại.
    """

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self) -> None:
        self.buf, self.inside = "", False

    def feed(self, text: str) -> str:
        """Nhận một token, trả về phần chắc chắn nằm ngoài thẻ think (có thể rỗng)."""
        self.buf += text
        out = []
        while True:
            tag = self.CLOSE if self.inside else self.OPEN
            i = self.buf.find(tag)
            if i >= 0:
                if not self.inside:
                    out.append(self.buf[:i])
                self.buf, self.inside = self.buf[i + len(tag):], not self.inside
                continue
            # giữ lại đuôi có thể là phần đầu của thẻ
            keep = next((k for k in range(len(tag) - 1, 0, -1) if self.buf.endswith(tag[:k])), 0)
            if not self.inside:
                out.append(self.buf[: len(self.buf) - keep])
            self.buf = self.buf[len(self.buf) - keep:]
            return "".join(out)

    def flush(self) -> str:
        """Trả phần đuôi còn giữ lại khi hết luồng (bỏ đi nếu đang ở trong thẻ think chưa đóng)."""
        rest, self.buf = ("" if self.inside else self.buf), ""
        return rest


class Generator:
    """Gom các bước của khâu Generation quanh một chat model.

    Args:
        llm: chat model của LangChain (hoặc đồ giả) có ainvoke(messages) và astream(messages).
            Để Any vì LangChain không có kiểu chung gọn cho cả ChatOllama lẫn đồ giả trong test.
        max_context_chars: ngân sách ký tự của NGỮ CẢNH. Với 12.000 ký tự, prompt dài nhất của bộ eval
            khoảng 3.800 token, vừa NUM_CTX=8192 của api/main.py và còn chỗ cho câu trả lời.
        max_history_turns: số tin nhắn lịch sử gần nhất đưa vào prompt và bước viết lại câu hỏi.
    """

    def __init__(
        self,
        llm: Any,
        *,
        max_context_chars: int = 12_000,
        max_history_turns: int = 6,
    ) -> None:
        self.llm = llm
        self.max_context_chars = max_context_chars
        self.max_history_turns = max_history_turns

    # ---------- trước khi tìm kiếm ----------
    async def condense(self, question: str, history: Sequence[Message]) -> str:
        """Viết lại câu hỏi nối tiếp ('còn học phí thì sao?') thành câu hỏi đầy đủ để tìm kiếm.

        Không có lịch sử thì trả nguyên câu hỏi, không gọi LLM. LLM lỗi, trả rỗng hoặc trả quá dài
        (> 400 ký tự, thường là nó trả lời luôn thay vì viết lại) thì cũng dùng câu hỏi gốc, để một lỗi
        ở bước phụ này không làm hỏng cả lượt chat.
        """
        if not history:
            return question
        convo = "\n".join(f"{'Sinh viên' if r == 'human' else 'Cố vấn'}: {c[:500]}"
                          for r, c in history[-self.max_history_turns:])
        try:
            res = await self.llm.ainvoke([("human", CONDENSE_PROMPT.format(history=convo, question=question))])
            text = re.sub(r"<think>.*?</think>", "", str(res.content), flags=re.S).strip().strip('"“”')
        except Exception:
            logger.exception("Condense question failed; dùng câu hỏi gốc.")
            return question
        return text if 0 < len(text) <= 400 else question

    @staticmethod
    def search_query(question: str, goal: str | None) -> str:
        """Thêm mục tiêu nghề nghiệp vào câu tìm kiếm khi câu hỏi liên quan tới nghề/môn học
        mà chưa nhắc tới mục tiêu. Câu hỏi chung (quy chế, học phí...) giữ nguyên, vì thêm tên nghề
        vào đó chỉ kéo về tài liệu nghề nghiệp không liên quan."""
        if goal and detect_intent(question) != "general" and goal.lower() not in question.lower():
            return f"{question} ({goal})"
        return question

    # ---------- dựng prompt ----------
    def select_points(self, points: Sequence[Point]) -> list[Point]:
        """Bỏ chunk trùng nội dung, cắt cho vừa ngân sách ký tự của ngữ cảnh.

        Giữ thứ tự tìm kiếm (chunk tốt nhất trước). Chunk cuối bị cắt bớt kèm " …" nếu vượt ngân sách;
        còn dưới 300 ký tự thì dừng hẳn, vì một mẩu quá ngắn chỉ làm nhiễu.
        """
        chosen, seen, used = [], set(), 0
        for p in points:
            content = (p.get("page_content") or "").strip()
            if not content or content in seen:
                continue
            room = self.max_context_chars - used
            if room < 300:
                break
            if len(content) > room:
                p = {**p, "page_content": content[:room] + " …"}
            seen.add(content)
            chosen.append(p)
            used += len(p["page_content"])
        return chosen

    def build_messages(
        self,
        question: str,
        points: Sequence[Point],
        *,
        goal: str | None = None,
        history: Sequence[Message] = (),
    ) -> list[Message]:
        """Dựng danh sách tin nhắn gửi LLM: system (nguyên tắc chung + hướng dẫn theo loại câu hỏi),
        lịch sử gần nhất, rồi tin nhắn cuối chứa mục tiêu nghề nghiệp, NGỮ CẢNH đánh số [1..n] và câu hỏi.

        Args:
            question: câu hỏi đã viết lại (sau condense).
            points: các chunk đã qua select_points; thứ tự quyết định số trích dẫn.
            goal: mục tiêu nghề nghiệp sinh viên chọn trên giao diện.
            history: lịch sử hội thoại dạng (vai, nội dung).
        """
        intent = detect_intent(question)
        system = SYSTEM_PROMPT + "\n\nHƯỚNG DẪN CHO CÂU HỎI NÀY:\n" + INTENT_RULES[intent]
        context = "\n\n".join(format_point(i, p) for i, p in enumerate(points, 1))
        profile = f"Mục tiêu nghề nghiệp của sinh viên: {goal}.\n\n" if goal else ""
        msgs: list[Message] = [("system", system)]
        msgs += list(history[-self.max_history_turns:])
        msgs.append(("human", f"{profile}NGỮ CẢNH:\n{context}\n\nCÂU HỎI: {question}"))
        return msgs

    # ---------- sinh câu trả lời ----------
    async def stream(self, messages: list[Message], n_sources: int) -> AsyncIterator[str]:
        """Stream câu trả lời đã lọc phần suy nghĩ. Không có nguồn thì trả lời cố định, không gọi LLM.

        Trả lời cố định khi không có nguồn là để chặn LLM tự trả lời bằng kiến thức ngoài tài liệu
        (đề bài cấm bịa môn học, quy định).

        Yields:
            Từng mẩu văn bản theo thứ tự, ghép lại là câu trả lời đầy đủ.
        """
        if n_sources == 0:
            yield NO_CONTEXT_ANSWER
            return
        flt = ThinkFilter()
        async for chunk in self.llm.astream(messages):
            text = flt.feed(str(getattr(chunk, "content", "") or ""))
            if text:
                yield text
        tail = flt.flush()
        if tail:
            yield tail
