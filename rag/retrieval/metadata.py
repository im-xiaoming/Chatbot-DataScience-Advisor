"""Bộ lọc metadata khi tìm kiếm: pydantic model -> models.Filter của Qdrant.

Các trường lọc đều có payload index trong Qdrant (db/schemas.py): keyword cho chuỗi, datetime cho ngày.
Dùng ở api/rag_service.retrieve, agent (node search_documents) và body POST /chat ("filters").

Ví dụ: MetadataFilter(category=["regulation", "academic_notice"], authority="official", valid_at=datetime.now())
  -> chỉ tài liệu chính thức về quy chế/thông báo học vụ, còn hiệu lực hôm nay.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator
from qdrant_client import models

# Một giá trị (khớp đúng) hoặc danh sách không rỗng (khớp một trong các giá trị).
Keywords = str | Annotated[list[str], Field(min_length=1)] | None

# Trường của model trùng tên khoá payload, lọc bằng khớp giá trị.
_KEYWORD_FIELDS = ("category", "doc_id", "publisher", "authority", "language", "region")


def _match(key: str, value: str | list[str]) -> models.FieldCondition:
    match = models.MatchValue(value=value) if isinstance(value, str) else models.MatchAny(any=value)
    return models.FieldCondition(key=key, match=match)


class MetadataFilter(BaseModel):
    """Lọc chunk theo metadata; mọi trường đều tuỳ chọn, None = không lọc theo trường đó, các điều kiện nối bằng AND."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: Keywords = None           # curriculum, regulation, career_role, market_trend, scholarship_tuition, ...
    exclude_category: Keywords = None   # bỏ các nhóm tài liệu này
    doc_id: Keywords = None
    publisher: Keywords = None          # "IUH", "Phòng Đào tạo - IUH", "ITviec", ...
    authority: Keywords = None          # "official" | "third_party"
    language: Keywords = None           # "vi" | "en"
    region: Keywords = None             # "VN" | "US" | "global"
    section: str | None = None          # một mục trong section_path (khớp nguyên văn), ví dụ "Điều 2. Giải thích thuật ngữ"
    published_from: datetime | None = None  # published_date >= mốc này (chunk không có ngày ban hành bị loại)
    published_to: datetime | None = None    # published_date <= mốc này
    valid_at: datetime | None = None    # còn hiệu lực tại thời điểm này: valid_until trống hoặc >= valid_at

    @model_validator(mode="after")
    def _check_range(self) -> MetadataFilter:
        if self.published_from and self.published_to and self.published_from > self.published_to:
            raise ValueError("published_from phải trước hoặc bằng published_to")
        return self

    def to_qdrant(self) -> models.Filter | None:
        """Dịch sang bộ lọc Qdrant; None nếu không có điều kiện nào."""
        must: list[models.Condition] = [_match(k, v) for k in _KEYWORD_FIELDS if (v := getattr(self, k)) is not None]
        must_not: list[models.Condition] = []
        if self.exclude_category is not None:
            must_not.append(_match("category", self.exclude_category))
        if self.section:
            must.append(_match("section_path", self.section))  # khớp khi một phần tử của mảng bằng giá trị này
        if self.published_from or self.published_to:
            must.append(models.FieldCondition(
                key="published_date", range=models.DatetimeRange(gte=self.published_from, lte=self.published_to)))
        if self.valid_at:
            valid_until = models.PayloadField(key="valid_until")
            must.append(models.Filter(should=[
                models.IsNullCondition(is_null=valid_until),
                models.IsEmptyCondition(is_empty=valid_until),
                models.FieldCondition(key="valid_until", range=models.DatetimeRange(gte=self.valid_at)),
            ]))
        if not must and not must_not:
            return None
        return models.Filter(must=must or None, must_not=must_not or None)
