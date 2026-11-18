from __future__ import annotations

import asyncio
import argparse


from rag.ingestion.loaders import Splitter, Record
from rag.ingestion.indexer import QdrantIndexer
from rag.embeddings import ModelEmbeddings, SparseEmbedding

from rag.retrieval import QdrantSearch

from db import create_qdrant_client

from config import RecursiveCharacterTextSplitterConfig, EmbeddingsConfig, QdrantConfig


DOCUMENTS_GLOB_PATH = r'./data/normalized/'

async def main():
    parser = argparse.ArgumentParser()
    
    parser.add_argument("--collection_name", type=str ,default='QQ')
    args = parser.parse_args()
    
    # ============================== splitter and load documents ==============================
    # splitter = Splitter(recursive_config=RecursiveCharacterTextSplitterConfig())
    
    # documents = splitter.split_documents(glob_path=DOCUMENTS_GLOB_PATH)
    # chunk_records = Record.build_chunk_records(docs=documents)
    
    
    # =========================== embeddings ================================================
    embedding_model = ModelEmbeddings(config=EmbeddingsConfig())
    # docs_embeddings = await embedding_model.aembedding_documents(chunk_records.tolist())
    
    
    # build sparse vectors
    # sparse_embedding = SparseEmbedding(chunks=chunk_records.model_dump(), avg_search=True)
    # sparse_vectors = sparse_embedding.build_sparses()
    
    
    # ================================= qdrant ============================================
    # indexer = QdrantIndexer(
    #     collection_name=args.collection_name,
    #     client=create_qdrant_client,
    # )
    # await indexer.create_collection(create_payload=True)
    # points = indexer.build_points(
    #     records=chunk_records.model_dump(),
    #     embeddings=docs_embeddings,
    #     sparse_vector=sparse_vectors
    # )
    # await indexer.upsert(points=points)
    
    # ============================= query ==============================================
    query = 'Quy định về buộc thôi học'
    searcher = QdrantSearch(
        collection_name=args.collection_name,
        client=create_qdrant_client,
    )
    
    response = await searcher.hybrid_search(
        query_vector = await embedding_model.aembedding_query(query=query),
        sparse_vector = SparseEmbedding.sparse_query(query=query, avgdl=256),
    )

    print(response)
    

if __name__ == '__main__':
    asyncio.run(main())
