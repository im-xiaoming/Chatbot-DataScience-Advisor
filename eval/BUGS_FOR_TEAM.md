# Lỗi cần báo nhóm khác (từ eval 23–24/11/2026)

Người ghi: Đỉnh (Generation, API, Evaluation). Các file dưới đây là code chung của nhóm, mình chỉ đọc, không sửa.
Số liệu lấy từ lượt `eval/out/v148` và `eval/out/final148` (148 câu, Qdrant hybrid, k=8, qwen3.5:4b). Collection `QQ`: 740 điểm.

## 1. Bảng quy đổi chứng chỉ tiếng Anh bị tách khỏi phần mô tả, và cột "TOEFL iBT" có vẻ sai tiêu đề (câu g09). Nhóm ingestion / chunking

- **Hiện tượng.** Câu g09 hỏi: "TOEIC bao nhiêu thì đạt chuẩn tiếng Anh để tốt nghiệp chương trình chuẩn?". Đáp án đúng là Nghe 275, Đọc 275, Nói 120, Viết 120.
  - Cả hai lượt chatbot đều trả lời "TOEIC 450". Ngữ cảnh có đủ dòng bảng.
  - Câu nối tiếp f11 cũng từng sai theo kiểu này.
- **Đã kiểm tra trong Qdrant.**
  - Chunk `3df63ff4-…` (*Quy chế đào tạo tín chỉ 2025 › Điều 23*) chỉ có bảng.
    - Chunk này không mang tên bảng.
    - Câu "chuẩn đầu ra ngoại ngữ: chứng chỉ tiếng Anh bậc 3 … theo bảng" nằm ở chunk khác (`d3dae8c2-…`).
    - Vì vậy khi LLM chỉ nhận được bảng, nó không biết bảng này dùng cho chuẩn tốt nghiệp. Khi nhận được cả hai chunk, nó cũng không biết hai chunk liên quan đến nhau.
  - Tiêu đề cột là `| … | TOEIC (4 kỹ năng) | TOEFL iBT | IELTS | TOEFL iBT* | …`.
    - Dòng Bậc 3 có giá trị `| Nghe: 275 Đọc: 275 Nói: 120 Viết: 120 | 450 | 4.0 | 30 |`. Như vậy số 450 nằm dưới cột "TOEFL iBT", nhưng điểm TOEFL iBT tối đa chỉ là 120.
    - Bảng quy đổi trong thông báo tuyển sinh 2026 ghi `TOEFL ITP 450-474`. Nhiều khả năng cột này phải là **TOEFL ITP** và bị đặt sai tên lúc chuyển PDF sang Markdown.
    - Bảng 4 trong *Cẩm nang người học* (chunk `b0ff00b0-…`) cũng sai giống hệt.
- **Đề xuất.**
  - So lại tiêu đề cột với PDF gốc.
  - Khi cắt chunk bảng, chèn lại tên bảng và câu dẫn ngay trước bảng (ví dụ "Bảng: chuẩn đầu ra ngoại ngữ để xét tốt nghiệp…") vào đầu chunk.
- Prompt đã có thêm quy tắc "chỉ lấy số dưới đúng tiêu đề cột". Quy tắc này không sửa được g09, vì chính tiêu đề cột đang sai.

## 2. k08 trượt top 5 với mọi cách tìm (dense, sparse, hybrid). Nhóm crawl / ingestion

- **Câu hỏi.** k08: "Mức lương trung vị của Data Scientist ở Mỹ theo O\*NET là bao nhiêu?". Gold là `onetonline.org/link/summary/15-2051.00`.
- **Đã kiểm tra.**
  - Trang gold có 34 chunk, trong đó có chunk *Data Scientists › Wages & Employment Trends* với nội dung `Median wages (2025) $57.80 hourly, $120,230 annual`.
  - Trang `15-2051.01` (*Business Intelligence Analysts*) cũng có một chunk *Wages & Employment Trends* gần như y hệt: "Median wage data for **Data Scientists** … $57.80 hourly, $120,230 annual". O\*NET hiển thị lương của nghề cha trên trang nghề con.
  - Chunk trùng này luôn xếp trên chunk gold, nên chatbot vẫn trả lời đúng số, nhưng nguồn trích là trang BI Analyst.
  - Trường hợp tương tự: `15-1243.01` (*Data Warehousing Specialists*) chứa lương của *Database Architects*.
- **Đề xuất.**
  - Khi crawl O\*NET, bỏ phần "Wages & Employment Trends" trên trang nghề con nếu nó nói về nghề cha.
  - Hoặc ghi rõ trong metadata của chunk rằng số liệu thuộc nghề nào.
- Mình không sửa `eval/qa.jsonl` để đổi gold.

## 3. Sparse: avgdl khi index khác avgdl khi query. Nhóm embeddings (`rag/embeddings/embedding.py`, `helper.py`)

- **Lúc index.** `pipline.py:58` tạo `SparseEmbedding(..., avg_search=True)`, nên `helper.search_avgdl()` tính avgdl thật của các chunk.
  - Đo lại trên 740 chunk đang có trong Qdrant (dùng `underthesea.word_tokenize`): avgdl khoảng **134,8** token (nhỏ nhất 3, lớn nhất 354).
- **Lúc query.** `SparseEmbedding.sparse_query(query, avgdl=256)` dùng mặc định 256. `api/rag_service.py` gọi hàm này không truyền avgdl, vì giá trị lúc index không được lưu ở đâu cả.
- **Ảnh hưởng.** Hệ số chuẩn hoá độ dài ở hai phía không khớp.
  - Với câu hỏi ngắn, trọng số các từ trong query bị kéo gần như đều nhau, nên tác động lên thứ hạng có lẽ nhỏ. Mình chưa đo riêng ảnh hưởng này.
  - Collection đã bật `modifier: idf`, nên IDF do Qdrant tính.
- **Đề xuất.**
  - Lưu avgdl lúc index (vào payload hoặc metadata của collection, hoặc vào config) rồi dùng lại giá trị đó khi query.
  - Hoặc không chuẩn hoá độ dài phía query (BM25 thường chỉ chuẩn hoá phía tài liệu).
  - Kiểm tra thêm: `pipline.py` truyền `chunk_records.model_dump()` (dict), trong khi `search_avgdl` đọc `d.page_content` theo kiểu thuộc tính. Cần xác nhận nhánh `avg_search=True` thật sự chạy được và avgdl dùng lúc index đúng là khoảng 134,8.

## Các lỗi khác đã ghi nhận

| # | Module / file | Lỗi | Đề xuất |
|---|---|---|---|
| 4 | `agent/models/loaders.py` | `import torch` ở đầu file, tốn khoảng 1,5 GB bộ nhớ commit trên Windows, kể cả khi chỉ dùng Ollama. pytest báo "paging file too small" khi Ollama đang chiếm RAM. | Chuyển import vào trong `load_cross_encoder_model`. |
| 5 | `agent/models/loaders.py` | `num_ctx` mặc định 32768 làm Ollama hết RAM trên máy 16 GB. | API đã truyền `NUM_CTX=8192`; nên hạ mặc định hoặc đọc từ config. |
| 6 | `rag/ingestion/__init__.py` | Import `injection`, kéo theo `agent.models` và torch, kể cả khi chỉ cần tìm kiếm giả. | Import lười (trong hàm). |
| 7 | `rag/embeddings/embedding.py` | Cũng `import torch` ở đầu file. | Như mục 4. |
| 8 | Qdrant | Client 1.20 và server 1.15.1 lệch phiên bản (có cảnh báo khi kết nối). | Đồng bộ phiên bản server với client. |
| 9 | Tìm kiếm | Dense có MRR 0,87, hybrid 0,84, sparse 0,65 (148 câu). Sparse đang kéo hybrid xuống. | Xem lại trọng số RRF hoặc mục 3 trước khi mặc định dùng hybrid. |
| 10 | Model embedding | qwen3-embedding:4b và qwen3.5:4b không cùng nằm vừa GPU 4 GB, nên mỗi câu hỏi Ollama phải dỡ rồi nạp lại model (thêm khoảng 16 s). | API hiện chạy embedding câu hỏi trên CPU (`EMBED_CPU=1`). Có thể cân nhắc model nhỏ hơn (qwen3-embedding:0.6b), nhưng phải index lại. |
| 11 | Dữ liệu | Có hai mã ngành KHDL: 7460108 (kế hoạch đào tạo 2023) và 7480201 (tuyển sinh 2026). Câu n03 vì thế lúc được chấm đúng, lúc bị chấm sai. | Xác nhận mã đúng và ghi chú vào metadata. |
| 12 | Dữ liệu | Báo cáo TopDev 2024-2025 chỉ có trang bìa (không có số liệu). Câu o06 hỏi theo TopDev nên LLM lấy số 40,65 triệu của ITviec gán cho TopDev. | Crawl đủ nội dung, hoặc bỏ chunk chỉ có trang bìa. |
| 13 | Tìm kiếm / chunk | Các câu thiếu ý do không có trong ngữ cảnh: c01, c05, k06, m02, g03, k12, k14, k21, k25 (cả hai lượt); thêm c19 (chỉ v148), r20 (chỉ final148), f05 (câu nối tiếp, v148). | Danh sách chi tiết (trường `failure` = `retrieval`) có trong `eval/out/final148/answers-qdrant-ollama.jsonl`. |
| 14 | `config/__init__.py` | Không export `CrossEncoderConfig`, nên `from config import CrossEncoderConfig` báo ImportError (RERANK=1 hỏng). | Thêm vào `__init__.py` và `__all__`. Tạm thời `api/rerank.py` import thẳng từ `config.config`. |

## Đã sửa trong phần của Đỉnh (24/11/2026)

- `api/doctor.py`: `import importlib` → `import importlib.util`; trước đó gọi `doctor.check_packages()` ngoài `python -m` bị AttributeError.
- `api/rerank.py`: import `CrossEncoderConfig` từ `config.config` thay vì `config` (mục 14), RERANK=1 không còn ImportError; chưa thử tải model.
- `eval/run_answers.py`: khi `default_catalog()` trả None (không thấy niên giám) thì không gọi `.check()`, ba chỉ số môn học để rỗng và in cảnh báo một lần, thay vì AttributeError.
