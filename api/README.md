# API chatbot tư vấn lộ trình KHDL — hướng dẫn chạy

API FastAPI (`api/main.py`) stream câu trả lời từng token bằng SSE, kèm giao diện web trong `frontend/`
(mở `http://localhost:8000`). Có đăng ký/đăng nhập và lưu lịch sử trò chuyện (`api/auth.py`, SQLite `data/app.db`).
Mọi lệnh chạy từ thư mục gốc repo.

## 1. Chạy thử ngay (không cần Ollama, Qdrant, Postgres)

Tìm kiếm giả theo từ khoá trên chính các chunk của nhóm (`data/normalized/`) và câu trả lời mẫu, đủ để xem giao diện.

Bash (Git Bash, Linux, macOS):

```bash
uv sync
uv run pytest -q
RETRIEVER=fake LLM=fake uv run uvicorn api.main:app
```

PowerShell:

```powershell
uv sync
uv run pytest -q
$env:RETRIEVER="fake"; $env:LLM="fake"; uv run uvicorn api.main:app
```

Mở `http://localhost:8000`, đăng ký một tài khoản rồi hỏi thử. Muốn bỏ bước đăng nhập thì thêm `AUTH_REQUIRED=0`
(PowerShell: `$env:AUTH_REQUIRED="0";`).

## 2. Chạy với Qdrant và Ollama

Xem [hướng dẫn chạy trên Windows](../README.md#chạy-cục-bộ-trên-windows) để khởi động Docker, kiểm tra collection `QQ` và chạy giao diện bằng PowerShell. API dùng `qwen3-embedding:4b` cho truy xuất và `qwen3.5:4b` cho câu trả lời. Khi chỉ chạy API trên collection có sẵn, dịch vụ cần Qdrant và Ollama.

Có thể chạy `uv run --locked python -m api.doctor` để kiểm tra Python, thư viện, mô hình Ollama, collection `QQ` và kết nối PostgreSQL. Xem lưu ý về pipeline trong hướng dẫn trên nếu cần lập chỉ mục từ đầu.

## 3. Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `RETRIEVER` | `fake` | `fake`: tìm theo từ khoá, không cần Qdrant. `qdrant`: tìm hybrid (dense + sparse) trên collection `QQ`. |
| `LLM` | `ollama` | `ollama`: model chat trong config (`qwen3.5:4b`). `fake`: câu trả lời mẫu, dùng cho test và làm giao diện. |
| `RERANK` | `0` | `1`: lấy 2 × TOP_K chunk rồi sắp xếp lại bằng cross-encoder `BAAI/bge-reranker-v2-m3` (lần đầu tải model khoảng 2 GB). |
| `TOP_K` | `8` | Số chunk đưa vào ngữ cảnh. Đo trên eval: k=8 đủ ý hơn k=6 nhưng chậm hơn (xem chú thích trong `api/main.py`). |
| `NUM_CTX` | `8192` | Cửa sổ ngữ cảnh gửi Ollama. Mặc định 32.768 của loader làm Ollama hết RAM trên máy 16 GB. |
| `EMBED_CPU` | `1` | `1`: nhúng câu hỏi trên CPU để Ollama giữ được cả 2 model trong GPU 4 GB (tránh dỡ/nạp model mỗi câu). `0`: theo config của nhóm. Chỉ có tác dụng khi `RETRIEVER=qdrant`. |
| `AUTH_REQUIRED` | `1` | `0`: người chưa đăng nhập vẫn chat được; hội thoại của họ không được lưu (trình duyệt tự gửi lịch sử). Người đã đăng nhập vẫn được lưu như thường. |
| `APP_DB` | `data/app.db` | File SQLite lưu người dùng và hội thoại (không đưa lên git). |
| `AUTH_SECRET` | (tự sinh) | Khoá ký token. Bỏ trống thì tự sinh một lần và lưu trong `APP_DB`. |
| `TOKEN_DAYS` | `7` | Số ngày token đăng nhập còn hạn. |

PowerShell đặt biến cho phiên hiện tại bằng `$env:TÊN="giá trị";` trước lệnh chạy.

## 4. Đánh giá

Chi tiết bộ câu hỏi và cách đọc chỉ số: `eval/README.md`. Kết quả ghi vào `eval/out/`.

```bash
uv run python -m eval.run_retrieval --mode qdrant --strategies dense,sparse,hybrid   # thêm --rerank để so cả bản rerank
uv run python -m eval.run_answers --retriever qdrant --judge                         # 148 câu, khoảng 2 giờ trên máy 4 GB VRAM
uv run python -m eval.run_answers --retriever qdrant --qa eval/qa_followup.jsonl     # 12 hội thoại nối tiếp
uv run python -m eval.run_answers --retriever qdrant --only c01,k02                  # chỉ chạy vài câu khi sửa prompt
uv run python -m eval.run_answers --llm fake --limit 5                               # thử nhanh, không cần Ollama
uv run python -m eval.rescore eval/out/answers-qdrant-ollama.jsonl                   # chấm lại sau khi sửa cách chấm, không gọi LLM
```

PowerShell dùng đúng các lệnh trên (không cần đặt biến môi trường; `run_answers` tự đặt `RETRIEVER`/`LLM` theo tham số).

Lưu ý: `uv run python -m eval.report` gộp các file trong `eval/out/` (không đọc thư mục con) và **ghi đè toàn bộ
`eval/results.md`**, kể cả phần viết tay (so sánh v148/final148). Sao lưu file đó trước khi chạy.
