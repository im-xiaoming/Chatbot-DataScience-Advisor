# Chatbot Data Science Advisor

Hệ thống lập chỉ mục và truy xuất tài liệu tiếng Việt phục vụ tư vấn ngành Khoa học dữ liệu và tra cứu thông tin học vụ tại Trường Đại học Công nghiệp TP. Hồ Chí Minh (IUH). Kho dữ liệu bao gồm tuyển sinh, chương trình đào tạo, nghề nghiệp, xu hướng thị trường, quy chế, học bổng, học phí và hỗ trợ sinh viên.

Repo hiện cung cấp pipeline lập chỉ mục và thư viện truy xuất Python. Phần sinh câu trả lời đã được thử nghiệm trong terminal với Ollama. API và giao diện chat chưa được tích hợp vào luồng chạy chính.

## Kiến trúc

```mermaid
flowchart LR
    A["Markdown đã chuẩn hóa"] --> B["Chia đoạn và tạo metadata"]
    B --> C["PostgreSQL<br/>docs và chunks"]
    B --> D["Vector dense và sparse"]
    D --> E["Qdrant<br/>Vector và payload"]
    Q["Câu hỏi và bộ lọc"] --> F["Dense và sparse prefetch"]
    E --> F
    F --> G["Hợp nhất thứ hạng bằng RRF"]
    G --> H["Đoạn trích và thông tin nguồn"]
```

- **PostgreSQL** lưu tài liệu và đoạn văn bản trong hai bảng `docs` và `chunks`. Alembic quản lý schema.
- **Qdrant** lưu một point cho mỗi đoạn, cùng hai named vector `dense` và `sparse`. Payload liên kết với PostgreSQL qua `doc_id` và `chunk_id`, đồng thời chứa tiêu đề, nội dung, mục và URL nguồn.
- **Dense retrieval** dùng `qwen3-embedding:4b` qua Ollama để tìm theo ngữ nghĩa. **Sparse retrieval** dùng trọng số từ khóa tính trong pipeline kết hợp với IDF của Qdrant. Hybrid search hợp nhất hai danh sách theo thứ hạng bằng Reciprocal Rank Fusion (RRF).
- **Filtering** áp dụng điều kiện bắt buộc cho cả hai nhánh trước khi hợp nhất. Bộ lọc riêng của mỗi nhánh được kết hợp với bộ lọc chung bằng phép AND. Payload hỗ trợ các trường như `doc_id`, `category` và `published_date`.

## Yêu cầu môi trường

- Python theo [.python-version](.python-version), hiện là 3.13, và `uv` để đồng bộ phụ thuộc.
- Docker và Docker Compose để chạy PostgreSQL 17. Các lệnh dưới đây cũng dùng Docker cho Qdrant và Ollama.
- Cấu hình phụ thuộc hiện tại lấy PyTorch và TorchVision từ kho wheel CUDA khai báo trong [pyproject.toml](pyproject.toml). Máy không có wheel tương thích với cấu hình này cần điều chỉnh cấu hình phụ thuộc theo môi trường.

## Chạy cục bộ

Chạy các lệnh từ thư mục gốc của repo. Ví dụ dành cho PowerShell.

### 1. Cài phụ thuộc và khởi động dịch vụ

```powershell
uv sync --locked
docker compose up -d --wait
docker run -d --name ds-advisor-qdrant -p 127.0.0.1:6333:6333 -v ds-advisor-qdrant:/qdrant/storage qdrant/qdrant:latest
docker run -d --name ds-advisor-ollama -p 127.0.0.1:11434:11434 -v ds-advisor-ollama:/root/.ollama ollama/ollama
docker exec ds-advisor-ollama ollama pull qwen3-embedding:4b
```

Docker Compose trong repo khởi động PostgreSQL. Hai lệnh `docker run` tạo Qdrant và Ollama cho lần thiết lập đầu tiên. Với container đã tạo, dùng `docker start ds-advisor-qdrant ds-advisor-ollama` khi cần khởi động lại. Có thể thêm `--gpus all` vào lệnh tạo container Ollama nếu Docker đã được cấu hình GPU tương thích.

### 2. Cấu hình môi trường

Tạo `.env` từ [.env.example](.env.example) ở thư mục gốc. Các giá trị dưới đây tương ứng với [Docker Compose](docker-compose.yaml) cho môi trường phát triển cục bộ.

```dotenv
DATABASE_URL=postgresql+asyncpg://myuser:mypassword@127.0.0.1:5432/mydatabase
POSTGRES_DB=mydatabase
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypassword
HOST=http://127.0.0.1:6333
```

`HOST` là endpoint Qdrant trong cấu hình dự án. Ollama chạy ở cổng mặc định `11434` trong ví dụ này. Giữ thông tin xác thực của từng môi trường trong cấu hình cục bộ và dùng giá trị phù hợp khi triển khai ngoài máy phát triển.

### 3. Chạy migration và lập chỉ mục

```powershell
uv run --locked alembic upgrade head
uv run --locked python pipline.py --collection_name QQ
```

Pipeline đọc Markdown trong `data/normalized/`, chia đoạn, ghi PostgreSQL, tạo cả hai loại vector và upsert vào Qdrant. Lần đầu có thể mất vài phút do tải mô hình vào bộ nhớ và tạo embedding cho toàn bộ kho.

### 4. Kiểm tra dữ liệu sau khi chạy

```powershell
docker exec postgres_db psql -U myuser -d mydatabase -c 'SELECT (SELECT count(*) FROM docs) AS documents, (SELECT count(*) FROM chunks) AS chunks;'
(Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:6333/collections/QQ/points/count' -ContentType 'application/json' -Body '{"exact":true}').result
```

Lần kiểm chứng trên dữ liệu của nhánh `ngythanh` cho kết quả **49 tài liệu, 740 đoạn và 740 điểm Qdrant**. Khi thay đổi dữ liệu, số lượng dự kiến sẽ thay đổi. Kiểm tra kết quả ghi và đối chiếu `chunk_id` giữa hai kho khi cần xác nhận chúng có cùng tập đoạn. Pipeline hiện chưa có quy trình tự động loại bỏ toàn bộ điểm cũ khi thay đổi cách chia đoạn hoặc xóa tài liệu khỏi nguồn.

## Ví dụ truy xuất có bộ lọc

Lưu ví dụ vào một tệp Python ở thư mục gốc và chạy bằng `uv run --locked python <tên-tệp>.py`. Ví dụ lọc nhóm `regulation` và in tiêu đề, mục cùng URL của các đoạn được tìm thấy.

```python
import asyncio

from qdrant_client import models

from config import EmbeddingsConfig, QdrantConfig
from db import create_qdrant_client
from rag.embeddings import ModelEmbeddings, SparseEmbedding
from rag.retrieval import QdrantSearch


async def main():
    question = "Quy định về buộc thôi học"
    client = create_qdrant_client(QdrantConfig())
    try:
        searcher = QdrantSearch(collection_name="QQ", client=client)
        embedder = ModelEmbeddings(config=EmbeddingsConfig())
        doc_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="category",
                    match=models.MatchValue(value="regulation"),
                )
            ]
        )

        results = await searcher.hybrid_search(
            query_vector=await embedder.aembedding_query(question),
            sparse_vector=SparseEmbedding.sparse_query(question),
            filter=doc_filter,
            limit=5,
            format=True,
        )
        for point in results:
            print(point.title, " / ".join(point.section_path), point.url)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
```

Để giới hạn truy vấn vào một tài liệu cụ thể, dùng `FieldCondition` với `key="doc_id"` và giá trị lấy từ bảng `docs` hoặc payload. Cả `search()` và `hybrid_search()` mặc định trả response Qdrant. Với `format=True`, chúng trả `list[QueryPoint]`. Khi truy vấn thành công nhưng bộ lọc không khớp, danh sách điểm rỗng. Lỗi truy vấn được truyền về bên gọi.

## Kiểm chứng và đánh giá

Kiểm thử tích hợp trên collection `QQ` đã chạy truy vấn dense-only, sparse-only và hybrid. Với câu “Quy định về buộc thôi học”, bộ lọc theo `doc_id` của Quy chế đào tạo tín chỉ ban hành năm 2025 trả về 5 đoạn, tất cả thuộc đúng tài liệu. Các ca lọc xung đột, bộ lọc không khớp, thiếu vector và lỗi Qdrant `404` cũng đã được kiểm tra.

Để đánh giá chất lượng truy xuất, dùng cùng một tập câu hỏi có nhãn nguồn hoặc đoạn đúng cho cả ba chế độ. Báo cáo **Hit@5** cho tỷ lệ câu có ít nhất một kết quả đúng trong top 5, **MRR@5** cho thứ hạng của kết quả đúng đầu tiên và **p50/p95** cho độ trễ. Khi đánh giá bộ lọc, kiểm tra riêng tỷ lệ kết quả thỏa tất cả điều kiện bắt buộc. Repo chưa công bố kết quả benchmark trên tập câu hỏi có nhãn.

## Cấu trúc mã nguồn

| Đường dẫn | Vai trò |
| --- | --- |
| [`pipline.py`](pipline.py) | Điểm chạy pipeline lập chỉ mục |
| [`data/`](data/) | Nguồn thô và tài liệu Markdown đã chuẩn hóa |
| [`rag/ingestion/`](rag/ingestion/) | Đọc, chia đoạn và lập chỉ mục |
| [`rag/embeddings/`](rag/embeddings/) | Tạo vector dense và sparse |
| [`rag/retrieval/`](rag/retrieval/) | Truy xuất Qdrant, hợp nhất và lọc kết quả |
| [`rag/rerank/`](rag/rerank/) | Mô-đun cross-encoder |
| [`db/`](db/) và [`alembic/`](alembic/) | Kết nối, mô hình lưu trữ, payload index và migration |
| [`agent/`](agent/) và [`config/`](config/) | Cấu hình, trình nạp mô hình và prompt |

## Giấy phép

Mã nguồn được phân phối theo [Apache License 2.0](LICENSE). Thông tin nguồn và giấy phép của từng tài liệu được lưu trong metadata của dữ liệu.
