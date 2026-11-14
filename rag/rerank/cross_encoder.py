
from __future__ import annotations

import torch

from agent.models import load_cross_encoder_model


class CrossEncoder:
    def __init__(self, config, device='cuda'):
        self.tokenizer, self.model = load_cross_encoder_model(config.model_name)
        self.device = torch.device(device if torch.cuda.is_available() else 'cpu')
        
    def __call__(self, pairs: list[tuple[str, str]]) -> torch.Tensor:
        with torch.no_grad():
            inputs = self.tokenizer(pairs, padding=True, truncation=True,
                               return_tensors='pt', max_length=512).to(self.device)
            scores = self.model(**inputs, return_dict=True).logits.view(-1, ).float().sigmoid()
        
        return scores