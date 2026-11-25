"""Chạy bộ câu hỏi qua toàn bộ pipeline (tìm kiếm + Generation) và chấm câu trả lời.

Chạy:
  uv run python -m eval.run_answers                       # tìm kiếm giả + Ollama thật
  uv run python -m eval.run_answers --retriever qdrant     # khi Qdrant đã có dữ liệu
  uv run python -m eval.run_answers --judge                # thêm LLM làm giám khảo (chậm hơn)
  uv run python -m eval.run_answers --llm fake --limit 5   # thử nhanh không cần Ollama
  uv run python -m eval.run_answers --qa eval/qa_followup.jsonl   # câu hỏi nối tiếp nhiều lượt

Chỉ số tự động (không cần LLM):
  key_fact_recall   tỉ lệ ý bắt buộc xuất hiện trong câu trả lời
  facts_in_context  tỉ lệ ý bắt buộc có trong ngữ cảnh đưa cho LLM (đúng tài liệu nhưng sai chunk thì thấp)
  failure           câu thiếu ý: "retrieval" (ý không có trong ngữ cảnh) hay "generation" (có mà LLM bỏ sót)
  source_hit        tài liệu đúng có nằm trong các nguồn đưa cho LLM không
  cited_rate        câu trả lời trong phạm vi có ghi nguồn [n] không
  invalid_citations số trích dẫn trỏ tới nguồn không tồn tại
  invented_codes    mã môn không có trong niên giám (đề bài cấm bịa môn)
  semester_mismatch môn ghi sai học kỳ so với niên giám
  name_mismatch     mã môn ghép với tên của môn khác
  condense_ok       (bộ câu nối tiếp) câu hỏi viết lại có đủ ý của lượt trước không
  refusal_ok        câu ngoài phạm vi: có nói "chưa có thông tin" không (in_scope: có trả lời không)
Giám khảo LLM (--judge): faithfulness (bám ngữ cảnh) và correctness (đúng so với đáp án mẫu), thang 1-5.
  Giám khảo là chính model 4B và chỉ đọc 3000 ký tự đầu của ngữ cảnh, nên dao động nhiều; dùng để xem xu hướng,
  không dùng để kết luận từng câu.
Kết quả: eval/out/answers-<retriever>-<llm>[-<tên bộ>].jsonl (từng câu) và .summary.json (tổng hợp).
Biến môi trường RETRIEVER/LLM được đặt theo tham số rồi mới import api.main, nên chạy đúng cấu hình như API
(NUM_CTX, TOP_K, EMBED_CPU... đọc như khi chạy uvicorn).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from collections import defaultdict
from collections.abc import Callable, Coroutine, Mapping, Sequence
from statistics import mean
from typing import TYPE_CHECKING, Any

from eval.common import is_refusal, key_fact_hits, load_qa, save_json

if TYPE_CHECKING:
    from eval.types import AnswerResult, Judge, QARow
    from rag.generation import Generator
    from rag.generation.types import Point

    Retrieve = Callable[..., Coroutine[Any, Any, list[Point]]]  # api.rag_service.retrieve hoặc api.fake.fake_retrieve

JUDGE_PROMPT = """Bạn là giám khảo chấm câu trả lời của chatbot tư vấn học tập. Chấm theo thang 1-5.

faithfulness: câu trả lời chỉ dùng thông tin có trong NGỮ CẢNH (5 = hoàn toàn bám ngữ cảnh, 1 = bịa nhiều).
correctness: câu trả lời đúng và đủ so với ĐÁP ÁN MẪU (5 = đúng đủ, 3 = đúng một phần, 1 = sai).

CÂU HỎI: {question}

ĐÁP ÁN MẪU: {reference}

NGỮ CẢNH (rút gọn):
{context}

CÂU TRẢ LỜI CỦA CHATBOT:
{answer}

Chỉ trả về một dòng JSON, ví dụ: {{"faithfulness": 4, "correctness": 3, "reason": "thiếu ý về tín chỉ"}}"""


_no_catalog_warned = False


def _warn_no_catalog() -> None:
    """In cảnh báo thiếu niên giám một lần cho cả lượt chạy (không lặp mỗi câu)."""
    global _no_catalog_warned
    if not _no_catalog_warned:
        print("Không tìm thấy niên giám, bỏ qua kiểm tra môn học", flush=True)
        _no_catalog_warned = True


def parse_judge(text: str) -> Judge | None:
    """Đọc dòng JSON điểm của giám khảo (bỏ phần <think>); None nếu không đọc được hoặc điểm ngoài 1-5."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        f, c = int(d["faithfulness"]), int(d["correctness"])
        if 1 <= f <= 5 and 1 <= c <= 5:
            return {"faithfulness": f, "correctness": c, "reason": str(d.get("reason", ""))[:300]}
    except (ValueError, KeyError, TypeError):
        pass
    return None


async def answer_one(row: QARow, retrieve: Retrieve, generator: Generator, k: int) -> AnswerResult:
    """Chạy một câu qua đúng các bước như /chat của API rồi tính các chỉ số tự động.

    Args:
        row: một dòng qa*.jsonl.
        retrieve: hàm tìm kiếm, gọi dạng retrieve(câu, category, k=k).
        generator: Generator dùng chung với API.
        k: số chunk lấy về (mặc định 8 = TOP_K của API).

    Returns:
        Một dòng answers-*.jsonl (chưa có "judge").

    Raises:
        Exception: lỗi tìm kiếm/LLM để nguyên cho main() thử lại.
    """
    from rag.generation import CourseCheck, default_catalog, extract_citations
    t0 = time.perf_counter()
    history: list[tuple[str, str]] = [tuple(h) for h in row.get("history", [])]  # type: ignore[misc]  # mỗi lượt trong JSON là [vai, nội dung]
    question = await generator.condense(row["question"], history)  # câu hỏi nối tiếp -> câu đầy đủ
    found = await retrieve(generator.search_query(question, row.get("goal")), None, k=k)
    points = generator.select_points(found)
    messages = generator.build_messages(question, points, goal=row.get("goal"), history=history)
    answer, first = "", None
    async for text in generator.stream(messages, n_sources=len(points)):
        first = first or time.perf_counter()
        answer += text
    cited, invalid = extract_citations(answer, len(points))
    hits = key_fact_hits(answer, row["key_facts"])
    context = messages[-1][1]
    ctx_hits = key_fact_hits(context, row["key_facts"])  # ý bắt buộc có nằm trong ngữ cảnh đưa cho LLM không
    catalog = default_catalog()
    if catalog is None:  # chạy ngoài thư mục gốc repo hoặc thiếu file niên giám: 3 chỉ số môn học để rỗng
        _warn_no_catalog()
    courses = catalog.check(answer) if catalog else CourseCheck()
    used_urls = [p["url"] for p in points]
    expected = row.get("expected_query")  # bộ câu nối tiếp: câu viết lại phải chứa các ý này
    return {
        "id": row["id"], "function": row["function"], "in_scope": row["in_scope"], "question": row["question"],
        "query": question,
        "condense_ok": all(key_fact_hits(question, expected)) if expected else None,
        "answer": answer, "sources": used_urls, "context": context,
        "source_hit": bool(set(row["gold_urls"]) & set(used_urls)) if row["in_scope"] else None,
        "key_fact_recall": (sum(hits) / len(hits)) if hits else None,
        "missing_facts": [k for k, h in zip(row["key_facts"], hits) if not h],
        "facts_in_context": (sum(ctx_hits) / len(ctx_hits)) if ctx_hits else None,
        # chẩn đoán tự động: ý thiếu trong câu trả lời là do tìm kiếm (không có trong ngữ cảnh) hay do LLM bỏ sót
        "failure": (None if not hits or all(hits) else
                    "retrieval" if any(not c for h, c in zip(hits, ctx_hits) if not h) else "generation"),
        "cited": cited, "invalid_citations": invalid,
        "invented_codes": courses.unknown, "semester_mismatch": courses.semester_mismatch,
        "name_mismatch": courses.name_mismatch,
        "refusal": is_refusal(answer),
        "refusal_ok": is_refusal(answer) if not row["in_scope"] else not is_refusal(answer),
        "first_token_ms": round(((first or time.perf_counter()) - t0) * 1000),
        "total_ms": round((time.perf_counter() - t0) * 1000),
    }


async def judge_one(llm: Any, row: QARow, res: AnswerResult) -> Judge | None:
    """Nhờ LLM chấm một câu trả lời; lỗi gọi LLM hoặc trả sai định dạng thì None (câu đó không tính điểm giám khảo)."""
    prompt = JUDGE_PROMPT.format(question=row["question"], reference=row["answer"],
                                 context=res["context"][:3000], answer=res["answer"][:3000])
    try:
        out = await llm.ainvoke([("human", prompt)])
        return parse_judge(str(out.content))
    except Exception as e:
        print("  giám khảo lỗi:", e)
        return None


def summarize(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Tổng hợp chỉ số cho toàn bộ và theo từng chức năng.

    Chỉ số tỉ lệ trả lời / ý bắt buộc / nguồn chỉ tính trên câu trong phạm vi; refused_out_of_scope chỉ tính
    trên câu ngoài phạm vi. Câu lỗi LLM (không có trong results) không được tính.

    Args:
        results: các dòng AnswerResult. Khai báo kiểu lỏng (Mapping) vì eval.rescore và các script phân tích
            đưa vào cả các dòng đọc lại từ file JSON, chưa kiểm tra kiểu.

    Returns:
        {"overall": {...}, "by_function": {tên chức năng: {...}}}; tên khoá giống LABEL trong eval/report.py.
    """
    def agg(rs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        ins = [r for r in rs if r["in_scope"]]
        outs = [r for r in rs if not r["in_scope"]]
        j = [r["judge"] for r in rs if r.get("judge")]
        s = {
            "n": len(rs),
            "key_fact_recall": round(mean(r["key_fact_recall"] for r in ins), 3) if ins else None,
            "facts_in_context": (round(mean(r["facts_in_context"] for r in ins if r.get("facts_in_context") is not None), 3)
                                 if any(r.get("facts_in_context") is not None for r in ins) else None),
            "fail_retrieval": sum(r.get("failure") == "retrieval" for r in ins),
            "fail_generation": sum(r.get("failure") == "generation" for r in ins),
            "source_hit": round(mean(r["source_hit"] for r in ins), 3) if ins else None,
            "cited_rate": round(mean(bool(r["cited"]) for r in ins), 3) if ins else None,
            "invalid_citations": sum(len(r["invalid_citations"]) for r in rs),
            "condense_ok": (round(mean(r["condense_ok"] for r in rs if r.get("condense_ok") is not None), 3)
                            if any(r.get("condense_ok") is not None for r in rs) else None),
            "invented_codes": sum(len(r.get("invented_codes", [])) for r in rs),
            "semester_mismatch": sum(len(r.get("semester_mismatch", [])) for r in rs),
            "name_mismatch": sum(len(r.get("name_mismatch", [])) for r in rs),
            "answered_in_scope": round(mean(r["refusal_ok"] for r in ins), 3) if ins else None,
            "refused_out_of_scope": round(mean(r["refusal_ok"] for r in outs), 3) if outs else None,
            "first_token_ms_avg": round(mean(r["first_token_ms"] for r in rs)),
            "total_ms_avg": round(mean(r["total_ms"] for r in rs)),
        }
        if j:
            s["faithfulness"] = round(mean(x["faithfulness"] for x in j), 2)
            s["correctness"] = round(mean(x["correctness"] for x in j), 2)
        return s

    by_fn = defaultdict(list)
    for r in results:
        by_fn[r["function"]].append(r)
    return {"overall": agg(results), "by_function": {k: agg(v) for k, v in sorted(by_fn.items())}}


async def main() -> None:
    """Đọc tham số, chạy từng câu (thử lại tối đa 3 lần khi Ollama lỗi), ghi kết quả ra eval/out/."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--retriever", choices=["fake", "qdrant"], default=os.getenv("RETRIEVER", "fake"))
    ap.add_argument("--llm", choices=["ollama", "fake"], default=os.getenv("LLM", "ollama"))
    ap.add_argument("--qa", default="eval/qa.jsonl")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="chỉ chạy N câu đầu để thử nhanh")
    ap.add_argument("--only", default="", help="chỉ chạy các id, ví dụ c01,k02")
    ap.add_argument("--judge", action="store_true", help="dùng LLM chấm faithfulness/correctness")
    a = ap.parse_args()

    os.environ.update(RETRIEVER=a.retriever, LLM=a.llm)
    from api.main import generator, llm, retrieve  # dùng đúng cấu hình như API thật

    rows = load_qa(a.qa)
    if a.only:
        rows = [r for r in rows if r["id"] in a.only.split(",")]
    if a.limit:
        rows = rows[: a.limit]

    results, errors = [], []
    for i, row in enumerate(rows, 1):
        res = None
        for attempt in range(3):  # Ollama đôi khi hết RAM (bad_alloc) trên máy 16 GB rồi tự khởi động lại runner
            try:
                res = await answer_one(row, retrieve, generator, a.k)
                break
            except Exception as e:
                print(f"  lỗi {row['id']} lần {attempt + 1}: {type(e).__name__}: {str(e)[:150]}", flush=True)
                await asyncio.sleep(15)
        if res is None:
            errors.append(row["id"])
            continue
        if a.judge and row["in_scope"]:
            res["judge"] = await judge_one(llm, row, res)
        mark = "OK " if res["refusal_ok"] and (res["key_fact_recall"] in (None, 1.0)) else "-- "
        print(f"{mark}[{i}/{len(rows)}] {row['id']} recall={res['key_fact_recall']} "
              f"hit={res['source_hit']} {res['total_ms']}ms  {row['question'][:60]}", flush=True)
        results.append(res)

    tag = f"{a.retriever}-{a.llm}" + ("" if a.qa == "eval/qa.jsonl" else "-" + os.path.basename(a.qa).split(".")[0])
    summary: dict[str, Any] = {"config": vars(a), "errors": errors, "summary": summarize(results)}
    if errors:
        print("Các câu lỗi sau 3 lần thử (không tính vào chỉ số):", ", ".join(errors))
    save_json(f"answers-{tag}.summary.json", summary)
    with open(f"eval/out/answers-{tag}.jsonl", "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps(summary["summary"]["overall"], ensure_ascii=False, indent=2))
    print(f"Chi tiết: eval/out/answers-{tag}.jsonl  ·  Tổng hợp: eval/out/answers-{tag}.summary.json")


if __name__ == "__main__":
    asyncio.run(main())
