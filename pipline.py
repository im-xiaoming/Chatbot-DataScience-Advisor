from __future__ import annotations

import asyncio
import argparse

from rag.ingestion.loaders import Splitter, Record
from config import RecursiveCharacterTextSplitterConfig, EmbeddingsConfig, QDrantConfig


DOCUMENTS_GLOB_PATH = r'./data/normalized/'

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    
    parser.add_argument("--collection_name", type=str ,default='ying')
    parser.add_argument("--review-only", action="store_true")
    args = parser.parse_args()
    
    # splitter and load documents
    splitter = Splitter(recursive_config=RecursiveCharacterTextSplitterConfig())
    
    if args.review_only:
        splitter.split_documents(DOCUMENTS_GLOB_PATH, review_only=True)
        raise SystemExit(0)

    from rag.ingestion.indexer import QdrantIndexer
    from rag.embeddings import ModelEmbeddings, SparseEmbedding
    from db import create_qdrant_client

    documents = splitter.split_documents(glob_path=DOCUMENTS_GLOB_PATH)[:10]
    chunk_records = Record.build_chunk_records(docs=documents)
    
    
    # embeddings
    embedding_model = ModelEmbeddings(config=EmbeddingsConfig())
    embeddings = embedding_model.aembedding_documents(chunk_records.tolist())
    
    
    # build sparse vectors
    sparse_embedding = SparseEmbedding(chunks=chunk_records.model_dump(), avg_search=True)
    sparse_vectors = sparse_embedding.build_sparses()
    
    
    # qdrant
    indexer = QdrantIndexer(
        collection_name=args.collection_name,
        client=create_qdrant_client,
    )
    # indexer.create_collection(create_payload=True)
    points = indexer.build_points(
        records=chunk_records.model_dump(),
        embeddings=embeddings,
        sparse_vector=sparse_vectors
    )
    indexer.upsert(points=points)
