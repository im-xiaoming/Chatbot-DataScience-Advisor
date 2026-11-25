# Đánh giá (Evaluation) — Lê Quang Đỉnh

## Bộ câu hỏi `qa.jsonl`

148 câu: 138 câu có đáp án trong `data/normalized/`, 10 câu ngoài phạm vi (bot phải nói "chưa có thông tin"; có câu cố tình hỏi số liệu mà tài liệu không có, như lương theo TopDev).
Theo 5 chức năng của đề bài (câu trong phạm vi): Hỏi đáp ngành học 65, Vị trí công việc 27, Chọn môn theo học kỳ 21, Thị trường tuyển dụng 14, Yêu cầu đầu ra 11. 48/49 tài liệu có câu hỏi; báo cáo TopDev chỉ có mục lục, không có số liệu, nên dùng làm câu ngoài phạm vi (o06).
Bản đầu (23/11) có 60 câu (id c01–c10, k01–k09, m01–m05, g01–g07, r01–r08, n01–n03, a01–a03, s01–s04, t01–t06, o01–o05); bản 24/11 thêm 88 câu. Muốn so với kết quả cũ thì chạy `--only` với các id bản đầu.
`qa_followup.jsonl`: 12 đoạn hội thoại hỏi nối tiếp.

Mỗi dòng:

| Trường | Ý nghĩa |
|---|---|
| `id` | c = chọn môn, k = nghề nghiệp, m = thị trường, g = tốt nghiệp, r/n/a/s/t = quy chế, ngành, thông báo, học bổng, hỗ trợ SV, o = ngoài phạm vi |
| `function` | 1 trong 5 chức năng của đề bài |
| `goal` | Mục tiêu nghề nghiệp gửi kèm (nếu có) |
| `gold_urls` | `url` trong front-matter của tài liệu chứa đáp án (không dùng `chunk_id` vì đổi khi chỉnh cách chia chunk) |
| `answer` | Đáp án mẫu, viết lại từ tài liệu |
| `key_facts` | Ý bắt buộc phải có trong câu trả lời; `"a\|b"` = chấp nhận một trong các cách viết |
| `in_scope` | `false` với câu ngoài dữ liệu |

Mọi `gold_urls` và `key_facts` đã được kiểm tra là có thật trong tài liệu gốc (`tests/test_eval_common.py` kiểm tra định dạng).
Thêm câu mới: giữ đúng định dạng trên, đọc tài liệu gốc trước khi viết đáp án.

## Cách chạy

```bash
# 1. Tìm kiếm: so sánh các cách tìm (giả = từ khoá, làm mốc)
uv run python -m eval.run_retrieval
uv run python -m eval.run_retrieval --mode qdrant --strategies dense,sparse,hybrid --rerank   # khi Qdrant có dữ liệu

# 0. Kiểm tra máy trước (Ollama, model, Qdrant, Postgres) và lấy lệnh chạy gợi ý
uv run python -m api.doctor

# 2. Câu trả lời: chạy cả pipeline, chấm tự động
uv run python -m eval.run_answers                          # tìm kiếm giả + Ollama
uv run python -m eval.run_answers --qa eval/qa_followup.jsonl   # 6 đoạn hội thoại hỏi nối tiếp
uv run python -m eval.run_answers --retriever qdrant --judge
uv run python -m eval.run_answers --llm fake --limit 5     # thử nhanh

# 3. Gộp kết quả thành bảng Markdown cho báo cáo
uv run python -m eval.report      # -> eval/results.md
```

Kết quả chi tiết từng câu nằm ở `eval/out/answers-*.jsonl` (câu trả lời, nguồn, ý còn thiếu, thời gian).

## Chỉ số

| Chỉ số | Cách tính |
|---|---|
| Hit@k, Recall@k, MRR | Theo `url` tài liệu, sau khi gộp các chunk cùng tài liệu |
| Ý bắt buộc có trong câu trả lời | Tỉ lệ `key_facts` xuất hiện (không phân biệt hoa thường) |
| Tài liệu đúng có trong ngữ cảnh | Ít nhất 1 `gold_url` nằm trong các chunk đưa cho LLM |
| Có ghi nguồn / Trích dẫn sai số | Câu trả lời có `[n]`; số `[n]` vượt quá số nguồn |
| Mã môn bịa / Môn ghi sai học kỳ | Mã 7 chữ số không có trong niên giám 2023; dòng ghi 1 mã môn + 1 học kỳ khác niên giám (`rag/generation/course_check.py`) |
| Viết lại câu hỏi nối tiếp đúng | Bộ `qa_followup.jsonl`: câu viết lại chứa đủ `expected_query` |
| Từ chối câu ngoài phạm vi | Câu trả lời có cụm "chưa có thông tin", "không tìm thấy"... |
| Bám ngữ cảnh, Đúng so với đáp án | LLM giám khảo chấm 1–5 (`--judge`); nên chấm tay 10 câu để kiểm tra giám khảo |

## Kết quả mốc (23/11/2026, tìm kiếm giả theo từ khoá)

Hit@5 = 85%, MRR = 0,64 trên 55 câu. Câu trượt: k08, m03, m04 (tài liệu tiếng Anh: O*NET, WEF — tìm theo từ khoá tiếng Việt không khớp, cần dense embedding), g07, r06, a02, t03, t06.
Lấy 8 chunk thay vì 6 tăng tỉ lệ có tài liệu đúng trong ngữ cảnh từ 76% lên 84%, nên `TOP_K` mặc định là 8.
