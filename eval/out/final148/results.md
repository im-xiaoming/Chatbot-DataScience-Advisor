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
