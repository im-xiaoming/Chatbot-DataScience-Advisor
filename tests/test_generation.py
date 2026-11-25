from types import SimpleNamespace

import pytest

from rag.generation import NO_CONTEXT_ANSWER, Generator, ThinkFilter, detect_intent, extract_citations


class ScriptedLLM:
    """LLM giả: stream đúng các mẩu cho trước, ghi lại messages nhận được."""
    def __init__(self, pieces=(), reply="", fail=False):
        self.pieces, self.reply, self.fail, self.seen = pieces, reply, fail, []

    async def astream(self, messages):
        self.seen.append(messages)
        for p in self.pieces:
            yield SimpleNamespace(content=p)

    async def ainvoke(self, messages):
        if self.fail:
            raise RuntimeError("ollama down")
        self.seen.append(messages)
        return SimpleNamespace(content=self.reply)


def pt(n, content="nội dung", **kw):
    return {"title": f"Tài liệu {n}", "url": f"https://x/{n}", "category": "regulation",
            "section_path": ["A", "B"], "page_content": content, **kw}


@pytest.mark.parametrize("q, intent", [
    ("Gợi ý chọn môn cho từng học kỳ", "course_plan"),
    ("Data Analyst cần kỹ năng gì, lương bao nhiêu?", "career"),
    ("Điều kiện tốt nghiệp và chuẩn ngoại ngữ?", "graduation"),
    ("Xu hướng tuyển dụng ngành dữ liệu", "market"),
    ("Trường có mấy cơ sở?", "general"),
])
def test_detect_intent(q, intent):
    assert detect_intent(q) == intent


def test_think_filter_handles_tags_split_across_tokens():
    f = ThinkFilter()
    out = "".join(f.feed(x) for x in ["Xin <th", "ink>nháp nháp</th", "ink>chào [1]"]) + f.flush()
    assert out == "Xin chào [1]"


def test_think_filter_keeps_normal_angle_brackets():
    f = ThinkFilter()
    assert f.feed("a < b và <b>đậm</b>") + f.flush() == "a < b và <b>đậm</b>"


def test_extract_citations_flags_unknown_numbers():
    assert extract_citations("Ý A [1][3], ý B [7].", n_sources=3) == ([1, 3], [7])


def test_select_points_dedupes_and_respects_budget():
    g = Generator(ScriptedLLM(), max_context_chars=1000)
    pts = [pt(1, "x" * 600), pt(2, "x" * 600), pt(3, "y" * 600), pt(4, "z" * 600)]
    chosen = g.select_points(pts)
    assert [p["title"] for p in chosen] == ["Tài liệu 1", "Tài liệu 3"]  # bỏ bản trùng, cắt bớt cái thứ hai
    assert sum(len(p["page_content"]) for p in chosen) <= 1000 + 2


def test_build_messages_numbers_context_and_adds_rules():
    g = Generator(ScriptedLLM())
    msgs = g.build_messages("Gợi ý chọn môn học kỳ 1", [pt(1, valid_until="2027-06-30"), pt(2)],
                            goal="Data Engineer", history=[("human", "hi"), ("ai", "chào")])
    system, *hist, last = msgs
    assert "CHỌN MÔN THEO HỌC KỲ" in system[1]
    assert hist == [("human", "hi"), ("ai", "chào")]
    assert "[1] Tài liệu 1 — A › B (hiệu lực đến 2027-06-30)" in last[1]
    assert "[2] Tài liệu 2" in last[1] and "Data Engineer" in last[1]


def test_system_prompt_has_anti_hallucination_rules():
    # lỗi thật từ eval 23/11: ghép mã 2101685 với tên môn khác, làm tròn 17,8 -> ~18 triệu,
    # và thêm cả mục "không có dữ liệu" khiến câu trả lời đúng bị coi là từ chối
    system = Generator(ScriptedLLM()).build_messages("Data Engineer lương bao nhiêu?", [pt(1)])[0][1]
    assert "CÙNG MỘT DÒNG" in system
    assert "không làm tròn" in system
    assert "Bỏ hẳn những mục NGỮ CẢNH không có" in system
    assert "chỉ hỏi lương thì chỉ trả lời mục lương" in system  # hướng dẫn riêng cho intent career
    # lỗi eval 24/11 (bộ 148 câu): đọc nhầm cột bảng TOEIC, trả lời ngược câu có/không, thay báo cáo được hỏi bằng báo cáo khác
    assert "đúng tiêu đề cột" in system
    assert "câu đầu tiên là một câu kết luận đầy đủ" in system
    assert "không thay bằng số liệu của nguồn" in system


async def test_condense_prompt_keeps_new_question_focus():
    llm = ScriptedLLM(reply="Khi nào sinh viên bị cảnh báo kết quả học tập?")
    await Generator(llm).condense("Thế khi nào thì bị cảnh báo?", [("human", "Khi nào bị buộc thôi học?"), ("ai", "...")])
    prompt = llm.seen[0][0][1]
    assert "Giữ đúng điều sinh viên đang hỏi" in prompt and "Không hỏi lại câu hỏi cũ" in prompt
    assert "Thế khi nào thì bị cảnh báo?" in prompt
    assert "giữ nguyên điều đã hỏi ở lượt trước" in prompt  # "Thế còn Data Engineer?" phải giữ ý "kỹ năng" của lượt trước


def test_search_query_adds_goal_once():
    assert Generator.search_query("kỹ năng cần có", "Data Analyst") == "kỹ năng cần có (Data Analyst)"
    assert Generator.search_query("Data Analyst làm gì", "Data Analyst") == "Data Analyst làm gì"
    assert Generator.search_query("Điều kiện bị buộc thôi học?", "Data Analyst") == "Điều kiện bị buộc thôi học?"


async def test_condense_skips_llm_without_history():
    llm = ScriptedLLM(reply="không dùng")
    assert await Generator(llm).condense("học phí bao nhiêu?", []) == "học phí bao nhiêu?"
    assert llm.seen == []


async def test_condense_rewrites_follow_up():
    llm = ScriptedLLM(reply='"Học phí ngành Khoa học Dữ liệu học kỳ 1 năm 2026-2027 là bao nhiêu?"')
    out = await Generator(llm).condense("còn học phí thì sao?", [("human", "ngành KHDL học gì"), ("ai", "...")])
    assert out.startswith("Học phí ngành Khoa học Dữ liệu")


async def test_condense_falls_back_when_llm_fails():
    out = await Generator(ScriptedLLM(fail=True)).condense("còn học phí?", [("human", "a")])
    assert out == "còn học phí?"


async def test_stream_without_sources_does_not_call_llm():
    llm = ScriptedLLM(pieces=["không được gọi"])
    out = [t async for t in Generator(llm).stream([("human", "q")], n_sources=0)]
    assert out == [NO_CONTEXT_ANSWER] and llm.seen == []


async def test_stream_removes_thinking():
    llm = ScriptedLLM(pieces=["<think>", "suy nghĩ", "</think>", "Trả lời [1]"])
    out = "".join([t async for t in Generator(llm).stream([("human", "q")], n_sources=1)])
    assert out == "Trả lời [1]"
