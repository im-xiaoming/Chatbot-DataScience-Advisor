from __future__ import annotations

from rag.types import ChunkRecord

_cache: dict[str, str] = dict()


def group_docs_chunks(chunks: list[ChunkRecord]):
    for chunk in chunks:
        _cache.setdefault(chunk.doc_id, []).append(chunk.chunk_id)
        
    return _cache