import hashlib
import json
from datetime import date

_SKIP = {"data_hash", "created_at", "updated_at", "id"}


def hash_row(data: dict) -> str:
    clean = {}
    for k, v in data.items():
        if k in _SKIP:
            continue
        clean[k] = v.isoformat() if isinstance(v, date) else (None if v is None else str(v))
    return hashlib.md5(json.dumps(clean, sort_keys=True).encode()).hexdigest()
