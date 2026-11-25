# Kết quả đánh giá chatbot tư vấn lộ trình KHDL

Cập nhật: 24/11/2026 21:03. Bộ câu hỏi: `eval/qa.jsonl`.

### Tìm kiếm — fake

| Cách tìm | Số câu | Hit@1 | Hit@3 | Hit@5 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| keyword (giả) | 55 | 51% | 74% | 86% | 77% | 0.64 |

Theo chức năng (cách tìm keyword (giả)):

| Chức năng | Số câu | Hit@5 | MRR |
|---|---|---|---|
| Chọn môn theo học kỳ | 10 | 100% | 0.70 |
| Hỏi đáp ngành học | 24 | 83% | 0.58 |
| Thị trường tuyển dụng | 5 | 60% | 0.50 |
| Vị trí công việc | 9 | 89% | 0.70 |
| Yêu cầu đầu ra | 7 | 86% | 0.79 |

Câu trượt top 5: k08, m03, m04, g07, r06, a02, t03, t06

### Tìm kiếm — qdrant

| Cách tìm | Số câu | Hit@1 | Hit@3 | Hit@5 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| dense | 138 | 78% | 97% | 99% | 98% | 0.87 |
| sparse | 138 | 51% | 79% | 84% | 82% | 0.65 |
| hybrid | 138 | 72% | 96% | 99% | 98% | 0.84 |

Theo chức năng (cách tìm dense):

| Chức năng | Số câu | Hit@5 | MRR |
|---|---|---|---|
| Chọn môn theo học kỳ | 21 | 100% | 0.96 |
| Hỏi đáp ngành học | 65 | 100% | 0.89 |
| Thị trường tuyển dụng | 14 | 100% | 0.80 |
| Vị trí công việc | 27 | 96% | 0.83 |
| Yêu cầu đầu ra | 11 | 100% | 0.73 |

Câu trượt top 5: k08

### Câu trả lời — tìm kiếm qdrant, LLM ollama, bộ eval/qa_followup.jsonl

| Chỉ số | Toàn bộ | Chọn môn theo học kỳ | Hỏi đáp ngành học | Vị trí công việc | Yêu cầu đầu ra |
|---|---|---|---|---|---|
| Ý bắt buộc có trong câu trả lời | 100% | 100% | 100% | 100% | 100% |
| Ý bắt buộc có trong ngữ cảnh | 100% | 100% | 100% | 100% | 100% |
| Tài liệu đúng có trong ngữ cảnh | 100% | 100% | 100% | 100% | 100% |
| Câu thiếu ý do tìm kiếm | 0 | 0 | 0 | 0 | 0 |
| Câu thiếu ý do LLM bỏ sót | 0 | 0 | 0 | 0 | 0 |
| Có ghi nguồn [n] | 100% | 100% | 100% | 100% | 100% |
| Trích dẫn sai số | 0 | 0 | 0 | 0 | 0 |
| Mã môn bịa (không có trong niên giám) | 0 | 0 | 0 | 0 | 0 |
| Môn ghi sai học kỳ | 0 | 0 | 0 | 0 | 0 |
| Mã môn ghép sai tên | 0 | 0 | 0 | 0 | 0 |
| Viết lại câu hỏi nối tiếp đúng | 83% | 100% | 83% | 100% | 50% |
| Trả lời câu trong phạm vi | 92% | 100% | 100% | 50% | 100% |
| Từ chối câu ngoài phạm vi | – | – | – | – | – |
| Token đầu (ms) | 6249 | 5806 | 6517 | 5049 | 7086 |
| Tổng thời gian (ms) | 30109 | 24848 | 26156 | 44128 | 33210 |

### Câu trả lời — tìm kiếm qdrant, LLM ollama, có giám khảo LLM

| Chỉ số | Toàn bộ | Chọn môn theo học kỳ | Hỏi đáp ngành học | Thị trường tuyển dụng | Vị trí công việc | Yêu cầu đầu ra |
|---|---|---|---|---|---|---|
| Ý bắt buộc có trong câu trả lời | 91% | 93% | 97% | 86% | 83% | 82% |
| Ý bắt buộc có trong ngữ cảnh | 95% | 97% | 98% | 93% | 86% | 91% |
| Tài liệu đúng có trong ngữ cảnh | 99% | 100% | 100% | 100% | 96% | 100% |
| Câu thiếu ý do tìm kiếm | 10 | 2 | 1 | 1 | 5 | 1 |
| Câu thiếu ý do LLM bỏ sót | 7 | 1 | 2 | 2 | 1 | 1 |
| Có ghi nguồn [n] | 99% | 95% | 100% | 100% | 100% | 100% |
| Trích dẫn sai số | 1 | 0 | 1 | 0 | 0 | 0 |
| Mã môn bịa (không có trong niên giám) | 0 | 0 | 0 | 0 | 0 | 0 |
| Môn ghi sai học kỳ | 1 | 1 | 0 | 0 | 0 | 0 |
| Mã môn ghép sai tên | 1 | 1 | 0 | 0 | 0 | 0 |
| Viết lại câu hỏi nối tiếp đúng | – | – | – | – | – | – |
| Trả lời câu trong phạm vi | 71% | 48% | 83% | 64% | 59% | 82% |
| Từ chối câu ngoài phạm vi | 60% | 100% | 40% | 67% | – | – |
| Bám ngữ cảnh (1-5) | 4.7 | 4.86 | 4.94 | 4.43 | 4.22 | 4.45 |
| Đúng so với đáp án (1-5) | 4.3 | 4.38 | 4.8 | 3.71 | 3.56 | 3.82 |
| Token đầu (ms) | 4525 | 5579 | 4463 | 4447 | 3801 | 4610 |
| Tổng thời gian (ms) | 34289 | 43230 | 27289 | 33603 | 43918 | 37565 |


## So sánh v148 (prompt trước) và final148 (prompt sau), tách 60 câu cũ / 88 câu mới

- v148: chạy 24/11 16:42–18:39, prompt như commit trước. final148: chạy 24/11 19:14–21:03, sau khi thêm quy tắc đọc đúng cột bảng,
  câu có/không, không thay nguồn được hỏi, và sửa prompt viết lại câu hỏi nối tiếp. Cùng Qdrant hybrid, k=8, NUM_CTX=8192, EMBED_CPU=1.
- Hai dòng từ chối ghi "bộ dò cũ → bộ dò mới". Bộ dò cũ (`is_refusal` trước patch 4) tìm cụm từ chối trong toàn bộ câu trả lời nên
  đếm nhầm các ghi chú phụ "chưa có thông tin về ..." ở cuối câu trả lời đúng; bộ dò mới chỉ xét phần mở đầu (300 ký tự, hoặc cả câu nếu < 400 ký tự).
  Số mới tính bằng `uv run python -m eval.rescore`, không chạy lại LLM. Các dòng khác không phụ thuộc bộ dò.
- Giám khảo LLM (qwen3.5:4b, ngữ cảnh cắt 3000 ký tự) dao động nhiều giữa hai lượt cho cùng câu trả lời (ví dụ n03 trả lời đúng mã 7460108 nhưng bị chấm 1),
  nên chênh lệch faithfulness/correctness dưới ~0,2 coi như không đổi.

| Chỉ số | 60 cũ v148 | 60 cũ final | 88 mới v148 | 88 mới final | 148 v148 | 148 final | 12 hội thoại v148 | 12 hội thoại final |
|---|---|---|---|---|---|---|---|---|
| key_fact_recall | 0.93 | 0.926 | 0.904 | 0.904 | 0.914 | 0.912 | 0.667 | 1.0 |
| facts_in_context | 0.935 | 0.935 | 0.95 | 0.954 | 0.944 | 0.946 | 0.833 | 1.0 |
| fail_retrieval | 5 | 5 | 5 | 5 | 10 | 10 | 2 | 0 |
| fail_generation | 0 | 0 | 7 | 7 | 7 | 7 | 2 | 0 |
| source_hit | 0.982 | 0.982 | 1 | 1 | 0.993 | 0.993 | 1 | 1 |
| cited_rate | 1 | 0.982 | 0.988 | 1 | 0.993 | 0.993 | 1 | 1 |
| invented_codes | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| semester_mismatch | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 |
| name_mismatch | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 |
| faithfulness | 4.82 | 4.78 | 4.46 | 4.64 | 4.6 | 4.7 | – | – |
| correctness | 4.47 | 4.35 | 4.2 | 4.28 | 4.31 | 4.3 | – | – |
| answered_in_scope | 0.8 → 0.982 | 0.727 → 0.982 | 0.892 → 0.988 | 0.699 → 0.964 | 0.855 → 0.986 | 0.71 → 0.971 | 0.833 → 0.917 | 0.917 → 1 |
| refused_out_of_scope | 0.8 → 0.6 | 0.8 → 0.8 | 0.6 → 0.4 | 0.4 → 0.2 | 0.7 → 0.5 | 0.6 → 0.5 | – | – |
| first_token_ms_avg | 4703 | 4549 | 4416 | 4508 | 4532 | 4525 | 6626 | 6249 |
| total_ms_avg | 36494 | 30260 | 35062 | 37036 | 35642 | 34289 | 29793 | 30109 |

Từng câu (bộ dò mới):
- Tốt lên rõ: a06 (trước trả lời ngược "có thể hủy"), o04, o05 (từ chối đúng), 4 câu nối tiếp f03, f05, f09, f11 (recall 0 → 1).
- Lùi thật: c15 ghép mã 2101634 với tên "Công nghệ phần mềm" (name_mismatch), c16 ghi Máy học ở học kỳ 7 (đúng là 6), m14 thiếu "Bank Teller",
  o02 (hỏi học phí Bách khoa, chatbot trả lời về IUH), o06 (vẫn gán số 40,65 triệu của ITviec cho báo cáo TopDev — trong dữ liệu chỉ có trang bìa TopDev).
- Lùi do bộ dò mới bắt nhầm (câu trả lời đúng, cụm từ chối nằm trong 300 ký tự đầu nhưng là ghi chú cho một ý phụ): n02 ("chưa có thông tin"), a10 ("không có thông tin"),
  m06 ("chưa có dữ liệu" cho nhóm < 1 năm), r19 ("không nằm trong" là nội dung câu trả lời).
- Bộ dò (cả cũ và mới) bỏ sót từ chối đúng vì cụm từ không có trong danh sách: o07 "không có số liệu cụ thể", o09 "chưa có số liệu cụ thể",
  o04 ở v148 "ngữ cảnh không cung cấp". Bộ dò mới bỏ sót thêm o10 (cụm "chưa có thông tin" nằm sau 300 ký tự). Chưa sửa REFUSAL_PATTERNS, chờ nhóm quyết.
- Câu lỗi LLM (bad_alloc) sau 3 lần thử: không có ở cả hai lượt.
