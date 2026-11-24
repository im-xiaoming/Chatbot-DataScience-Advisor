# Frontend, đăng nhập và streaming

Tài liệu này ghi lại phần giao diện và API chat hiện có trong project, cách chạy thử và điểm cần nối tiếp khi nhóm hoàn thiện RAG/LLM.

## 1. Đã làm gì?

| Phần | Hiện trạng | File chính |
| --- | --- | --- |
| Giao diện | Trang đăng ký/đăng nhập, khung chat, câu hỏi gợi ý, nút dừng trả lời và tạo cuộc trò chuyện mới | [`frontend/index.html`](../frontend/index.html), [`frontend/styles.css`](../frontend/styles.css), [`frontend/app.js`](../frontend/app.js) |
| Đăng ký/đăng nhập | FastAPI tạo tài khoản, đăng nhập, xem phiên hiện tại và đăng xuất; mật khẩu lưu dạng Argon2 hash | [`api/main.py`](../api/main.py), [`api/models.py`](../api/models.py) |
| Lưu tài khoản | Bảng `users` trong PostgreSQL, tạo bằng Alembic | [`api/database.py`](../api/database.py), [`alembic/versions/b6d0f1a4c8e2_add_users.py`](../alembic/versions/b6d0f1a4c8e2_add_users.py) |
| Streaming | API gửi sự kiện SSE qua `POST /chat/stream`; frontend đọc stream và nối nội dung vào câu trả lời khi nhận được | [`api/main.py`](../api/main.py), [`frontend/app.js`](../frontend/app.js) |
| Kiểm tra | Test API cho xác thực, cookie, kiểm tra dữ liệu đầu vào và luồng phản hồi tăng dần | [`tests/test_api.py`](../tests/test_api.py) |

## 2. Hai chế độ chạy

- **Demo giao diện:** mở `http://localhost:5500`. Đăng nhập và câu trả lời đều được mô phỏng trong trình duyệt; không tạo tài khoản trong database. Chỉ tên hiển thị được giữ trong `sessionStorage` của tab hiện tại.
- **Kết nối API:** mở `http://localhost:5500/?api=http://localhost:8000`. Đăng ký/đăng nhập dùng FastAPI và PostgreSQL. Trình duyệt nhận luồng SSE thật qua HTTP. **Nội dung câu trả lời vẫn là mẫu**, chưa truy xuất tài liệu hoặc gọi LLM.

Vì vậy, hiện đã có **cơ chế truyền và hiển thị nội dung tăng dần**, nhưng chưa có **token thật do mô hình sinh ra**. API hiện tách câu trả lời mẫu thành các từ và gửi từng phần với khoảng dừng ngắn.

## 3. Luồng xử lý

1. Người dùng đăng ký qua `POST /auth/register`, rồi đăng nhập qua `POST /auth/login`.
2. API xác thực email/mật khẩu và đặt cookie phiên `datapath_session` có `HttpOnly` và `SameSite=Strict`. Frontend gửi cookie trong các request bằng `credentials: "include"`.
3. Người dùng gửi câu hỏi; frontend gọi `POST /chat/stream` với JSON `{"message":"..."}`.
4. API kiểm tra phiên đăng nhập, trả `text/event-stream` với nhiều sự kiện `text` và một sự kiện `done`.
5. Frontend đọc từng phần bằng `fetch()` và `ReadableStream`, ghép các sự kiện SSE, rồi thêm `content` vào ô trả lời. Nút dừng dùng `AbortController` để hủy request ở trình duyệt.

Ví dụ sự kiện hiện có:

```text
data: {"type":"text","content":"Xin chào "}

data: {"type":"done"}

```

Frontend cũng hiểu sự kiện `sources` để hiện liên kết nguồn và `error` để báo lỗi, nhưng API mô phỏng hiện chưa phát hai loại này. Một phần dữ liệu HTTP nhận được không nhất thiết tương ứng với một token của LLM; frontend ghép dữ liệu theo ranh giới sự kiện SSE.

## 4. Chạy thử trên máy

Cần Python 3.13+, `uv` và một PostgreSQL cục bộ. Có thể dùng PostgreSQL trong [`docker-compose.yaml`](../docker-compose.yaml); không cần tài khoản SQL trên mạng.

Từ thư mục gốc project:

1. Chạy `uv sync` để cài phụ thuộc.
2. Sao chép [`.env.example`](../.env.example) thành `.env`. Điền `SESSION_SECRET` bằng giá trị ngẫu nhiên, ví dụ lấy từ `python -c "import secrets; print(secrets.token_hex(32))"`. Cấu hình `DATABASE_URL` cho PostgreSQL của bạn.
3. Chạy `docker compose up -d postgres` nếu dùng Docker, sau đó `uv run alembic upgrade head` để tạo bảng.
4. Chạy API: `uv run uvicorn api.main:app --reload`.
5. Ở terminal khác, chạy frontend: `python -m http.server 5500 --directory frontend`.
6. Mở `http://localhost:5500/?api=http://localhost:8000`, đăng ký, đăng nhập và gửi một câu hỏi.

Nếu chỉ muốn xem giao diện, chỉ cần bước 5 rồi mở `http://localhost:5500`; khi đó ứng dụng chạy ở chế độ demo. Hướng dẫn ngắn hơn nằm tại [`api/README.md`](../api/README.md) và [`frontend/README.md`](../frontend/README.md).

## 5. Cần gì từ các phần khác để hoàn thiện?

Frontend và giao thức SSE có thể phát triển độc lập với RAG. Để trả lời bằng dữ liệu thật, nhóm cần nối endpoint `POST /chat/stream` với pipeline hỏi đáp:

1. **Phần dữ liệu và chunking/embedding:** cung cấp tài liệu đã xử lý và index để tìm kiếm.
2. **Phần database/vector database/retrieval:** trả về các đoạn tài liệu phù hợp cho câu hỏi; hiện API chat chưa gọi phần này.
3. **Phần LLM:** nhận câu hỏi cùng các đoạn tìm được và hỗ trợ phát câu trả lời tăng dần. Đây là phần cần có để stream token sinh ra thật.
4. **Phần kiểm thử/evaluation:** kiểm tra luồng chat tích hợp và chất lượng câu trả lời sau khi thay nội dung mẫu.

Khi tích hợp, có thể giữ giao diện và định dạng SSE hiện tại: thay đoạn tạo câu trả lời mẫu trong [`api/main.py`](../api/main.py) bằng kết quả từ retrieval + LLM, gửi từng phần dưới dạng `text`, rồi gửi `done`. Nếu muốn hiện trích dẫn, API phát thêm `sources` với `title` và `url`. Cần thống nhất định dạng nguồn với nhóm làm retrieval trước khi nối.

## 6. Giới hạn hiện tại

- Chưa nối endpoint chat với RAG, Qdrant hoặc LLM; câu trả lời API là mẫu cố định theo câu hỏi.
- Chưa lưu lịch sử chat vào database; tạo cuộc trò chuyện mới chỉ xóa nội dung trên màn hình.
- Test hiện kiểm tra API với SQLite tạm thời; chưa có kiểm tra tích hợp với PostgreSQL thật trong bộ test.
