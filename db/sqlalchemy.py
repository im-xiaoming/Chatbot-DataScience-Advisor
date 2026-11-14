from __future__ import annotations

from typing import Optional
from sqlalchemy import create_engine, String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ModelDoc(Base):
    __tablename__ = 'docs'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # relationship
    chunks: Mapped['ModelChunk'] = relationship(back_populates='doc')


class ModelChunk(Base):
    __tablename__ = 'chunks'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[int] = ForeignKey('docs.id')
    
    # relationship
    doc: Mapped[str] = relationship(back_populates="chunks")
   