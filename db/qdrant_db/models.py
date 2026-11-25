from __future__ import annotations

from typing import Optional
from sqlalchemy import String, Text, Integer, ForeignKey, ARRAY, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from .base import Base


class ModelDoc(Base):
    __tablename__ = 'docs'
    
    doc_id: Mapped[str] = mapped_column(primary_key=True)
    
    title: Mapped[str] = mapped_column(String())
    page_content: Mapped[str] = mapped_column(Text())
    
    url: Mapped[str] = mapped_column(String())
    category: Mapped[str] = mapped_column(String())
    section_path: Mapped[list[str]] = mapped_column(ARRAY(String()))
    publisher: Mapped[str] = mapped_column(String())
    authority: Mapped[str] = mapped_column(String())
    language: Mapped[str] = mapped_column(String())
    region: Mapped[str] = mapped_column(String())
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    license: Mapped[str] = mapped_column(String())
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    normalized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pipeline_version: Mapped[str] = mapped_column(String())
    
    # relationship
    chunks: Mapped[list['ModelChunk']] = relationship(back_populates='doc')
    
    def __repr__(self):
        return f'Document ID: {self.doc_id}.'


class ModelChunk(Base):
    __tablename__ = 'chunks'
    
    chunk_id: Mapped[str] = mapped_column(primary_key=True)
    doc_id: Mapped[str] = mapped_column(ForeignKey('docs.doc_id'))
    
    title: Mapped[str] = mapped_column(String())
    page_content: Mapped[str] = mapped_column(Text())
    
    url: Mapped[str] = mapped_column(String())
    category: Mapped[str] = mapped_column(String())
    section_path: Mapped[list[str]] = mapped_column(ARRAY(String()))
    publisher: Mapped[str] = mapped_column(String())
    authority: Mapped[str] = mapped_column(String())
    language: Mapped[str] = mapped_column(String())
    region: Mapped[str] = mapped_column(String())
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    license: Mapped[str] = mapped_column(String())
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    normalized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pipeline_version: Mapped[str] = mapped_column(String())
    
    # relationship
    doc: Mapped['ModelDoc'] = relationship(back_populates="chunks")
    
    def __repr__(self):
        return f'Chunk ID: {self.chunk_id} - Document ID: {self.doc_id}.'
   
