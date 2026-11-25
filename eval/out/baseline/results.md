# Kết quả đánh giá chatbot tư vấn lộ trình KHDL

Cập nhật: 23/11/2026 14:37. Bộ câu hỏi: `eval/qa.jsonl`.

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
| dense | 55 | 86% | 96% | 98% | 97% | 0.91 |
| sparse | 55 | 58% | 80% | 86% | 81% | 0.69 |
| hybrid | 55 | 80% | 98% | 98% | 97% | 0.89 |

Theo chức năng (cách tìm dense):

| Chức năng | Số câu | Hit@5 | MRR |
|---|---|---|---|
| Chọn môn theo học kỳ | 10 | 100% | 0.93 |
| Hỏi đáp ngành học | 24 | 100% | 0.96 |
| Thị trường tuyển dụng | 5 | 100% | 0.90 |
| Vị trí công việc | 9 | 89% | 0.83 |
| Yêu cầu đầu ra | 7 | 100% | 0.81 |

Câu trượt top 5: k08

### Câu trả lời — tìm kiếm qdrant, LLM ollama, bộ eval/qa_followup.jsonl

| Chỉ số | Toàn bộ | Chọn môn theo học kỳ | Hỏi đáp ngành học | Vị trí công việc | Yêu cầu đầu ra |
|---|---|---|---|---|---|
| Ý bắt buộc có trong câu trả lời | 83% | 100% | 67% | 100% | 100% |
| Ý bắt buộc có trong ngữ cảnh | 100% | 100% | 100% | 100% | 100% |
| Tài liệu đúng có trong ngữ cảnh | 100% | 100% | 100% | 100% | 100% |
| Câu thiếu ý do tìm kiếm | 0 | 0 | 0 | 0 | 0 |
| Câu thiếu ý do LLM bỏ sót | 1 | 0 | 1 | 0 | 0 |
| Có ghi nguồn [n] | 100% | 100% | 100% | 100% | 100% |
| Trích dẫn sai số | 0 | 0 | 0 | 0 | 0 |
| Mã môn bịa (không có trong niên giám) | 0 | 0 | 0 | 0 | 0 |
| Môn ghi sai học kỳ | 0 | 0 | 0 | 0 | 0 |
| Mã môn ghép sai tên | 0 | 0 | 0 | 0 | 0 |
| Viết lại câu hỏi nối tiếp đúng | 100% | 100% | 100% | 100% | 100% |
| Trả lời câu trong phạm vi | 100% | 100% | 100% | 100% | 100% |
| Từ chối câu ngoài phạm vi | – | – | – | – | – |
| Token đầu (ms) | 22006 | 23079 | 23059 | 19084 | 20697 |
| Tổng thời gian (ms) | 52387 | 53269 | 55879 | 62116 | 31301 |

### Câu trả lời — tìm kiếm qdrant, LLM ollama, có giám khảo LLM

| Chỉ số | Toàn bộ | Chọn môn theo học kỳ | Hỏi đáp ngành học | Thị trường tuyển dụng | Vị trí công việc | Yêu cầu đầu ra |
|---|---|---|---|---|---|---|
| Ý bắt buộc có trong câu trả lời | 89% | 92% | 98% | 70% | 78% | 86% |
| Ý bắt buộc có trong ngữ cảnh | 94% | 94% | 100% | 80% | 89% | 86% |
| Tài liệu đúng có trong ngữ cảnh | 98% | 100% | 100% | 100% | 89% | 100% |
| Câu thiếu ý do tìm kiếm | 5 | 2 | 0 | 1 | 1 | 1 |
| Câu thiếu ý do LLM bỏ sót | 3 | 0 | 1 | 1 | 1 | 0 |
| Có ghi nguồn [n] | 98% | 100% | 100% | 100% | 100% | 86% |
| Trích dẫn sai số | 0 | 0 | 0 | 0 | 0 | 0 |
| Mã môn bịa (không có trong niên giám) | 0 | 0 | 0 | 0 | 0 | 0 |
| Môn ghi sai học kỳ | 0 | 0 | 0 | 0 | 0 | 0 |
| Mã môn ghép sai tên | 0 | 0 | 0 | 0 | 0 | 0 |
| Viết lại câu hỏi nối tiếp đúng | – | – | – | – | – | – |
| Trả lời câu trong phạm vi | 82% | 70% | 96% | 20% | 89% | 86% |
| Từ chối câu ngoài phạm vi | 100% | 100% | 100% | 100% | – | – |
| Bám ngữ cảnh (1-5) | 4.78 | 4.7 | 4.88 | 5 | 4.67 | 4.57 |
| Đúng so với đáp án (1-5) | 4.33 | 4.6 | 4.42 | 3.4 | 4.22 | 4.43 |
| Token đầu (ms) | 18816 | 18087 | 19397 | 18630 | 18130 | 18761 |
| Tổng thời gian (ms) | 51466 | 53393 | 44978 | 64665 | 60446 | 50607 |
