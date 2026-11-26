"""MetadataFilter (rag/retrieval/metadata.py): kiểm tra dữ liệu vào và cách dịch sang bộ lọc Qdrant."""
from datetime import datetime

import pytest
from pydantic import ValidationError
from qdrant_client import models

from rag.retrieval import MetadataFilter


def test_empty_filter_is_none():
    assert MetadataFilter().to_qdrant() is None


def test_single_value_and_list_match():
    flt = MetadataFilter(category="regulation", publisher=["IUH", "ITviec"]).to_qdrant()
    assert flt.must == [
        models.FieldCondition(key="category", match=models.MatchValue(value="regulation")),
        models.FieldCondition(key="publisher", match=models.MatchAny(any=["IUH", "ITviec"])),
    ] and flt.must_not is None


def test_exclude_goes_to_must_not():
    flt = MetadataFilter(exclude_category=["market_trend"]).to_qdrant()
    assert flt.must is None and flt.must_not[0].match == models.MatchAny(any=["market_trend"])


@pytest.mark.parametrize("bad", [
    {"catgory": "regulation"},                                                  # gõ sai tên trường
    {"category": []},                                                           # danh sách rỗng
    {"published_from": "2026-01-01", "published_to": "2025-01-01"},            # khoảng ngày ngược
])
def test_invalid_input_is_rejected(bad):
    with pytest.raises(ValidationError):
        MetadataFilter(**bad)


def test_parses_iso_dates_from_json():
    f = MetadataFilter.model_validate({"published_from": "2025-01-01", "valid_at": "2026-11-26T00:00:00Z"})
    assert f.published_from == datetime(2025, 1, 1) and f.valid_at.year == 2026
