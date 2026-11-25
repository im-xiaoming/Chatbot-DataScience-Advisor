import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # để import được rag, db, config...

from rag.types import ChunkRecord


@pytest.fixture
def make_chunk():
    """Tạo ChunkRecord giả, chỉ cần truyền trường muốn đổi."""
    def _make(**kw):
        base = dict(
            doc_id="doc-1", chunk_id="doc-1+000000000000000", title="Buộc thôi học",
            page_content="Sinh viên bị buộc thôi học nếu bị cảnh báo học tập 3 lần liên tiếp.",
            url="https://camnang.iuh.edu.vn/buoc-thoi-hoc.php", category="regulation",
            section_path=["Buộc thôi học"], publisher="IUH", authority="official",
            language="vi", region="VN", license="internal",
            normalized_at=datetime(2026, 10, 31, tzinfo=timezone.utc), pipeline_version="1.0.0",
        )
        return ChunkRecord(**{**base, **kw})
    return _make
