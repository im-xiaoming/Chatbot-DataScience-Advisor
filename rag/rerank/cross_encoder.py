
from __future__ import annotations

import torch
import asyncio

import torch
from rag.types import QueryPoint
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def _load_cross_encoder_model(model_name: str):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    model.eval()
    return (tokenizer, model)


class CrossEncoder:
    def __init__(self, config, device='cuda'):
        self.tokenizer, self.model = _load_cross_encoder_model(config.model_name)
        self.device = torch.device(device if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
            
        
    async def __call__(self, pairs: list[tuple[str, str]]) -> torch.Tensor:
        inputs = self.tokenizer(pairs, padding=True, truncation=True, return_tensors='pt', max_length=512).to(self.device)
            
        def predict():
            with torch.no_grad():
                return self.model(**inputs, return_dict=True).logits.view(-1, ).float().sigmoid()
                
        scores = await asyncio.to_thread(lambda: predict())
        
        return scores.cpu().numpy().tolist()
    
    async def encoder(self, query: str, docs: list[str], topk: int = 10):
        pairs = [
            (query, doc) for doc in docs
        ]
        scores = await self(pairs)
        results = [
            (i, doc, score) for i, (doc, score) in enumerate(zip(docs, scores))
        ]
        return sorted(results, key=lambda x: -x[-1])


from qdrant_client import models
        
def format_query(points: list[models.ScoredPoint]) -> list[QueryPoint]:
    query_points = []
    for point in points:
        query_points.append(
            QueryPoint(
                point_id=point.id,
                version=point.version,
                score=point.score,
                **point.payload
            )
        )
    return query_points