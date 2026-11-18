from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class Base(BaseModel):
    model_config = ConfigDict(extra='ignore', frozen=True)
    

class DocRecord(Base):
    doc_id: str
    title: str
    page_content: str
    
    url: str
    category: str
    section_path: list[str]
    publisher: str
    authority: str
    language: str
    region: str
    published_date: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    license: str
    fetched_at: Optional[datetime] = None
    normalized_at: datetime
    pipeline_version: str
    
    
class ChunkRecord(Base):
    doc_id: str
    chunk_id: str
    title: str
    page_content: str
    
    url: str
    category: str
    section_path: list[str]
    publisher: str
    authority: str
    language: str
    region: str
    published_date: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    license: str
    fetched_at: Optional[datetime] = None
    normalized_at: datetime
    pipeline_version: str
    
    
class QueryPoint(Base):
    point_id: str
    version: int
    score: float
    vector: Optional[list[float]] = None
    
    doc_id: str
    chunk_id: str
    title: str
    page_content: str
    
    url: str
    category: str
    section_path: list[str]
    publisher: str
    authority: str
    language: str
    region: str
    published_date: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    license: str
    fetched_at: Optional[datetime] = None
    normalized_at: datetime
    pipeline_version: str