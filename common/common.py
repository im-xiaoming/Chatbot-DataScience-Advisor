from __future__ import annotations

import logging
import uuid
import hashlib
import json

_NAMESPACE = '6a030adf-b105-467e-aebc-515b8d9c153c'

    
def _encode_string(string: str) -> str:
    return str(uuid.uuid5(uuid.UUID(_NAMESPACE), string.encode('utf-8')))


def _dump_json(data: dict, file_name='../data/chunks.jsonl') -> None:
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4, default=lambda o: o.isoformat())
            f.write("\n")
    except Exception as e:
        logging.exception(f'Failed to dump json: {e}')
        
        
def _dump_jsons(data: list[dict], file_name='data/chunks.jsonl') -> None:
    try:
        with open(file_name, "a", encoding="utf-8") as f:
            for d in data:
                json.dump(d, f, ensure_ascii=False, indent=4, default=lambda o: o.isoformat())
                f.write("\n")
    except Exception as e:
        logging.exception(f'Failed to dump jsons: {e}')
        