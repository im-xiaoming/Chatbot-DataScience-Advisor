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
    chunk_size: int = Field(default=1500)
    chunk_overlap: int = Field(default=200)
    
    
class EmbeddingsConfig(Base):
    model_name: str = Field(default='qwen3-embedding:4b')
    model_provider: str = Field(default='ollama')


class LLMConfig(Base):
    model_name: str = Field(default='qwen3.5:4b')
    model_provider: str = Field(default='ollama')    
    
class QdrantConfig(Base):
    host: str = Field(default='localhost')
    
    
class APIConfig(Base):
    """Cấu hình api/main.py, đọc từ biến môi trường RERANK, NUM_CTX, TOP_K."""
    rerank: bool = Field(default=False)  # RERANK=1: sắp xếp lại bằng cross-encoder
    num_ctx: int = Field(default=8192)  # cửa sổ ngữ cảnh của Ollama
    # 8 x 1500 ký tự vừa ngân sách ngữ cảnh 12.000; đo bằng eval: k=6 -> 76%, k=8 -> 84% câu có tài liệu đúng
    top_k: int = Field(default=8)


class CrossEncoderConfig(Base):
    model_name: str = Field(default='BAAI/bge-reranker-v2-m3')
    
    
class QdrantDatabaseConfig(Base):
    DATABASE_URL: str
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str