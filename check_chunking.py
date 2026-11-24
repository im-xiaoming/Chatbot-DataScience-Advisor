from pathlib import Path

from config import RecursiveCharacterTextSplitterConfig
from rag.ingestion.loaders import Splitter


splitter = Splitter(recursive_config=RecursiveCharacterTextSplitterConfig())
chunks = splitter.split_documents("data/normalized", checked_only=True)

document_ids = {chunk.metadata["doc_id"] for chunk in chunks}
chunk_ids = {chunk.metadata["chunk_id"] for chunk in chunks}

assert len(document_ids) == 51, f"Mong đợi 51 tài liệu, nhận {len(document_ids)}"
assert len(chunks) == 870, f"Mong đợi 870 chunk, nhận {len(chunks)}"
assert len(chunk_ids) == len(chunks), "Phát hiện chunk_id trùng"

catalog = Path("data/normalized/curriculum/iuh-khdl-danh-muc-giao-trinh-tham-khao.md")
book_count = sum(
    line.startswith("## ")
    for line in catalog.read_text(encoding="utf-8").splitlines()
)
catalog_chunks = splitter.split_document(str(catalog))

assert book_count == 7, f"Mong đợi 7 đầu sách, nhận {book_count}"
assert catalog_chunks and all(
    chunk.metadata["chunk_id"] in chunk_ids for chunk in catalog_chunks
), "Danh mục giáo trình chưa được đưa vào tập chunk"

print(f"OK — {len(document_ids)} tài liệu → {len(chunks)} chunk, {book_count} đầu sách")
