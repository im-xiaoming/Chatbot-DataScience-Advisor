from __future__ import annotations

import zlib
import logging
from rag.types import ChunkRecord
from collections import Counter
from common import logs
from qdrant_client.models import SparseVector

logger = logging.getLogger(__name__)

_AVGDL = 256

def search_avgdl(docs: list[ChunkRecord]) -> float:
    global _AVGDL
    s = [len(d.page_content.split()) for d in docs]
    _AVGDL = sum(s) / len(s)
    logger.info("Search AVG DL = " + str(_AVGDL))
    return _AVGDL


def _to_int(x: str) -> int:
    return zlib.crc32(x.encode('utf-8'))


def _TF(d: ChunkRecord, k1: float = 1.25, b: float = 0.75, avgdl: float = 256):
    counter = Counter(d.page_content.split())
    tf = {
        _to_int(w): (counter[w] * (k1 + 1)) / (counter[w] + k1 * (1 - b  + b * len(counter) / avgdl))
        for w in counter
    }
    return SparseVector(
        indices=tf.keys(),
        values=tf.values()
    )
    