from __future__ import annotations

import torch
import logging

from typing import Literal
from functools import lru_cache

from langchain_ollama import OllamaEmbeddings
from langchain_core.embeddings import Embeddings
from langchain.chat_models import init_chat_model


from common import logs

logger = logging.getLogger(__name__)


@lru_cache(maxsize=16)
def load_embedding_model(
    *,
    model_name: str,
    model_provider: Literal['ollama', 'openai'] = 'ollama'
) -> Embeddings:
    model = None
    global EMBEDDING_DIMENSIONS
    
    if model_provider == 'ollama':
        model = OllamaEmbeddings(
            model=model_name
        )
        EMBEDDING_DIMENSIONS = len(model.embed_query(text="I miss you Ying."))
        logger.info("Init ollama embedding model.")
        
    elif model_provider == 'openai':
        logger.info("Init openai embedding model.")
    
    return model


@lru_cache(maxsize=16)
def load_llm_model(
    model_name: str,
    model_provider: Literal['ollama', 'openai'] = 'ollama',
    temperature: float = 0.2,
    reasoning: bool = False,
    num_ctx: int = 32_768
):
    if temperature < 0 or temperature > 1:
        raise ValueError("temperature must be between 0 and 1.")
    
    model = init_chat_model(
        model=model_name,
        model_provider=model_provider,
        temperature=temperature,
        reasoning=reasoning,
        num_ctx=num_ctx
    )
    return model

