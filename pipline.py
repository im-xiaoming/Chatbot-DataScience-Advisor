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

from config import RecursiveCharacterTextSplitterConfig, EmbeddingsConfig, QdrantConfig, \
LLMConfig, CrossEncoderConfig
from rag.rerank import CrossEncoder, format_query

from agent.prompt import CONTEXT_SYSTEM_PROMPT, CONTEXT_USER_PROMPT


DOCUMENTS_GLOB_PATH = r'./data/normalized/'

async def main():
    parser = argparse.ArgumentParser()
    
    parser.add_argument("--collection_name", type=str ,default='ying')
    parser.add_argument("--review-only", action="store_true")
    args = parser.parse_args()
    
    
    if args.review_only:
        splitter.split_documents(DOCUMENTS_GLOB_PATH, review_only=True)
        raise SystemExit(0)

    from rag.ingestion.indexer import QdrantIndexer
    from rag.embeddings import ModelEmbeddings, SparseEmbedding
    from db import create_qdrant_client

    documents = splitter.split_documents(glob_path=DOCUMENTS_GLOB_PATH)[:10]
    chunk_records = Record.build_chunk_records(docs=documents)
    
    # await save_to_db(docs=doc_records, chunks=chunk_records.model_dump())
    
    # =========================== injection ==========================================
    # engine, Session = create()
    # injector = Injection(
    #     Session=Session,
    #     config=LLMConfig(),
    #     temperature=0,
    #     CONTEXT_USER_PROMPT=CONTEXT_USER_PROMPT,
    #     CONTEXT_SYSTEM_PROMPT=CONTEXT_SYSTEM_PROMPT
    # )
    # chunk_records = await injector.inject(docs=doc_records)
    
    
    # =========================== embeddings ================================================
    embedding_model = ModelEmbeddings(config=EmbeddingsConfig())
    # docs_embeddings = await embedding_model.aembedding_documents(chunk_records.tolist())
    
    
    # # build sparse vectors
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
    
    query_points = format_query(response.points)
    
    # ================================ Cross Encoding ===============================
    cross_encoder = CrossEncoder(
        config=CrossEncoderConfig()
    )
    
    cross_results = await cross_encoder.encoder(
        query=query,
        docs=[point.page_content for point in query_points],
        topk=10
    )
    

if __name__ == '__main__':
    asyncio.run(main())
