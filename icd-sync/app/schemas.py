from typing import Optional
from pydantic import BaseModel


class SyncResult(BaseModel):
    status:        str
    version:       Optional[str] = None
    codes_added:   int
    codes_updated: int
    codes_deleted: int
    codes_skipped: int
    message:       str


class HcpcsSyncResult(BaseModel):
    status:             str
    update_cycle:       Optional[str] = None
    zip_filename:       Optional[str] = None
    modifiers_inserted: int
    modifiers_updated:  int
    modifiers_deleted:  int
    modifiers_skipped:  int
    codes_inserted:     int
    codes_updated:      int
    codes_deleted:      int
    codes_skipped:      int
    message:            str
