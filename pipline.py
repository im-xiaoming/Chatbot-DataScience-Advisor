from __future__ import annotations

import asyncio
import argparse


from rag.ingestion.loaders import Splitter, Record
from rag.ingestion.indexer import QdrantIndexer
from rag.embeddings import ModelEmbeddings, SparseEmbedding
from rag.ingestion import Injection

from rag.retrieval import QdrantSearch

from db import create_qdrant_client
from db.qdrant_db.session import create
from utils import save_to_db

from config import RecursiveCharacterTextSplitterConfig, EmbeddingsConfig, QdrantConfig, LLMConfig

from agent.prompt import CONTEXT_SYSTEM_PROMPT, CONTEXT_USER_PROMPT


DOCUMENTS_GLOB_PATH = r'./data/normalized/'

async def main():
    parser = argparse.ArgumentParser()
    
    parser.add_argument("--collection_name", type=str ,default='QQ')
    args = parser.parse_args()
    
    # ============================== splitter and load documents ==============================
    splitter = Splitter(recursive_config=RecursiveCharacterTextSplitterConfig())
    
    documents, chunks = splitter.split_documents(glob_path=DOCUMENTS_GLOB_PATH)
    doc_records = Record.build_doc_records(docs=documents)[:1]
    chunk_records = Record.build_chunk_records(docs=chunks)
    
    await save_to_db(docs=doc_records, chunks=chunk_records.model_dump())
    
    # =========================== injection ==========================================
    engine, Session = create()
    injector = Injection(
        Session=Session,
        config=LLMConfig(),
        temperature=0,
        CONTEXT_USER_PROMPT=CONTEXT_USER_PROMPT,
        CONTEXT_SYSTEM_PROMPT=CONTEXT_SYSTEM_PROMPT
    )
    CONTEXT_USER_PROMPT = await injector.inject(docs=doc_records)
    
    
    # =========================== embeddings ================================================
    # embedding_model = ModelEmbeddings(config=EmbeddingsConfig())
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
    # query = 'Quy định về buộc thôi học'
    # searcher = QdrantSearch(
    #     collection_name=args.collection_name,
    #     client=create_qdrant_client,
    # )
    
    # response = await searcher.hybrid_search(
    #     query_vector = await embedding_model.aembedding_query(query=query),
    #     sparse_vector = SparseEmbedding.sparse_query(query=query, avgdl=256),
    # )

    # print(response)
    

if __name__ == '__main__':
    asyncio.run(main())
