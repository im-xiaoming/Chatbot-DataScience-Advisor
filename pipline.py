from __future__ import annotations

import asyncio

from rag.ingestion.loaders import Splitter, Record
from rag.embeddings import ModelEmbeddings

from config import RecursiveCharacterTextSplitterConfig
from config import EmbeddingsConfig


DOCUMENTS_GLOB_PATH = r'./data/normalized/'

if __name__ == '__main__':
    # splitter and load documents
    splitter = Splitter(recursive_config=RecursiveCharacterTextSplitterConfig())
    
    documents = splitter.split_documents(glob_path=DOCUMENTS_GLOB_PATH)
    chunk_records = Record.build_chunk_records(docs=documents)
    
    
    # embeddings
    embedding_model = ModelEmbeddings(config=EmbeddingsConfig())
    r = chunk_records.tolist()
    res = embedding_model.aembedding_documents(r)
    
    