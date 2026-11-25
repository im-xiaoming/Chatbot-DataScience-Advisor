from eval.common import is_refusal, key_fact_hits, load_qa
from eval.run_answers import parse_judge, summarize


def test_key_fact_hits_accepts_alternatives_and_case():
    assert key_fact_hits("Lương khoảng 40.65 triệu, học SQL", ["40,65|40.65", "sql", "Python"]) == [True, True, False]


def test_is_refusal():
    assert is_refusal("Mình chưa có thông tin về giá vé xem phim.")
    assert not is_refusal("Học kỳ 1 gồm 17 tín chỉ [1].")


def test_parse_judge():
    assert parse_judge('<think>...</think> {"faithfulness": 5, "correctness": 3, "reason": "thiếu ý"}')["correctness"] == 3
    assert parse_judge("không phải JSON") is None
    assert parse_judge('{"faithfulness": 9, "correctness": 3}') is None


def test_qa_file_is_well_formed():
    rows = load_qa()
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)) >= 50
    for r in rows:
        assert r["question"] and r["function"]
        assert bool(r["gold_urls"]) == r["in_scope"]
        assert bool(r["key_facts"]) == r["in_scope"]


def test_summarize_splits_in_and_out_of_scope():
    base = dict(function="A", cited=[1], invalid_citations=[], first_token_ms=1, total_ms=2)
    rs = [dict(base, in_scope=True, key_fact_recall=1.0, source_hit=True, refusal_ok=True),
          dict(base, in_scope=False, key_fact_recall=None, source_hit=None, refusal_ok=False)]
    o = summarize(rs)["overall"]
    assert o["key_fact_recall"] == 1.0 and o["refused_out_of_scope"] == 0.0


def test_followup_file_is_well_formed():
    rows = load_qa("eval/qa_followup.jsonl")
    assert len(rows) >= 5
    for r in rows:
        assert r["history"] and r["expected_query"] and r["gold_urls"] and r["key_facts"]
        assert all(role in ("human", "ai") for role, _ in r["history"])


async def test_answer_one_diagnoses_retrieval_vs_generation():
    from types import SimpleNamespace
    from eval.run_answers import answer_one
    from rag.generation import Generator

    class LLM:
        async def astream(self, messages):
            yield SimpleNamespace(content="Học kỳ 1 có Nhập môn Tin học [1].")

    async def retrieve(q, cat, k):
        return [{"title": "KH", "url": "u", "category": "curriculum", "page_content": "Nhập môn Tin học, Triết học"}]

    row = dict(id="x", function="f", in_scope=True, question="HK1 học gì?", gold_urls=["u"],
               key_facts=["Nhập môn Tin học", "Triết học", "Quốc phòng"])
    res = await answer_one(row, retrieve, Generator(LLM()), k=8)
    assert res["facts_in_context"] == 2 / 3 and res["key_fact_recall"] == 1 / 3
    assert res["failure"] == "retrieval"  # "Quốc phòng" không có trong ngữ cảnh


def test_refusal_only_counts_opening_of_long_answers():
    long_ok = "### Mức lương\n\nData Engineer 0-2 năm: 17,8 triệu [1].\n" + "Chi tiết thêm. " * 40 + \
              "\n- Lộ trình thăng tiến: tài liệu không có thông tin về các cấp bậc."
    assert not is_refusal(long_ok)
    long_refuse = "Chưa có thông tin về môn Blockchain trong chương trình đào tạo. " + "Gợi ý thêm. " * 50
    assert is_refusal(long_refuse)
    assert is_refusal("### Trả lời\n\nMình không tìm thấy dữ liệu về giá ký túc xá.")


async def test_answer_one_without_catalog(monkeypatch, capsys):
    # thiếu file niên giám: không được lỗi, 3 chỉ số môn học rỗng, cảnh báo in đúng một lần
    from types import SimpleNamespace

    import rag.generation
    from eval import run_answers
    from rag.generation import Generator

    class LLM:
        async def astream(self, messages):
            yield SimpleNamespace(content="Học kỳ 1 có môn 2101999 [1].")

    async def retrieve(q, cat, k):
        return [{"title": "KH", "url": "u", "category": "curriculum", "page_content": "Nhập môn Tin học"}]

    monkeypatch.setattr(rag.generation, "default_catalog", lambda: None)
    monkeypatch.setattr(run_answers, "_no_catalog_warned", False)
    row = dict(id="x", function="f", in_scope=True, question="HK1 học gì?", gold_urls=["u"], key_facts=["Tin học"])
    for _ in range(2):
        res = await run_answers.answer_one(row, retrieve, Generator(LLM()), k=8)
        assert res["invented_codes"] == [] and res["semester_mismatch"] == [] and res["name_mismatch"] == []
    assert capsys.readouterr().out.count("Không tìm thấy niên giám") == 1
