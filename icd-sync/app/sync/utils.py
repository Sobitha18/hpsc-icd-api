"""
sync/utils.py
-------------
Shared utilities used by both ICD and HCPCS sync processors.

hash_row() is the single source of truth for change detection across
all code types. Both processors must use the same algorithm so hashes
stored from one run are comparable on the next run.
"""

import hashlib
import json
from datetime import date


def hash_row(data: dict) -> str:
    """
    Compute a stable MD5 hash over the data fields of a record dict.

    Rules:
      - DB-only fields (id, data_hash, created_at, updated_at) are excluded
        so that inserting a row and re-hashing the same source data always
        produces the same digest.
      - date objects are serialised as ISO strings ("2024-10-01") for
        cross-run stability.
      - None stays None (serialised as JSON null, not the string "None").
      - Everything else is cast to str() so numeric types (int, float,
        Decimal) are compared as text — consistent with how pandas reads
        Excel cells whose types can vary between CMS releases.
      - Keys are sorted so dict insertion order never matters.
    """
    _skip = {"data_hash", "created_at", "updated_at", "id"}
    clean: dict = {}
    for k, v in data.items():
        if k in _skip:
            continue
        if isinstance(v, date):
            clean[k] = v.isoformat()
        elif v is None:
            clean[k] = None
        else:
            clean[k] = str(v)
    return hashlib.md5(
        json.dumps(clean, sort_keys=True).encode("utf-8")
    ).hexdigest()
