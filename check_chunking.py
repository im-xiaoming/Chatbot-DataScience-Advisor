from config import RecursiveCharacterTextSplitterConfig
from rag.ingestion.loaders import Splitter


splitter = Splitter(recursive_config=RecursiveCharacterTextSplitterConfig())
chunks = splitter.split_documents("data/normalized", checked_only=True)

document_ids = {chunk.metadata["doc_id"] for chunk in chunks}
chunk_ids = {chunk.metadata["chunk_id"] for chunk in chunks}

assert len(document_ids) == 40, f"Mong đợi 40 tài liệu, nhận {len(document_ids)}"
assert len(chunks) == 809, f"Mong đợi 809 chunk, nhận {len(chunks)}"
assert len(chunk_ids) == len(chunks), "Phát hiện chunk_id trùng"

print(f"OK — {len(document_ids)} tài liệu → {len(chunks)} chunk")
