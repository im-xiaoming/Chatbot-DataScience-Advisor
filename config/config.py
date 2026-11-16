from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Base(BaseSettings):
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        frozen=True
    )
    
class RecursiveCharacterTextSplitterConfig(Base):
    chunk_size: int = Field(default=1024)
    chunk_overlap: int = Field(default=200)
    
    
class EmbeddingsConfig(Base):
    model_name: str = Field(default='embeddinggemma-2:latest')
    model_provider: str = Field(default='ollama')
    
    
class QDrantConfig(Base):
    host: str = Field(default='localhost')
    
    
class CrossEncoderConfig(Base):
    model_name: str = Field(default='BAAI/bge-reranker-v2-m3')