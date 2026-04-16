"""
models.py
---------
SQLAlchemy ORM models — one class per DB table.

Tables:
  icd_codes               — current ICD-10-CM diagnosis codes (annual CMS release)
  icd_sync_history        — audit log of every ICD-10-CM sync run
  hcpcs_modifiers         — current HCPCS modifiers (2-char codes, quarterly CMS release)
  hcpcs_modifier_sync_log — audit log of every HCPCS modifier sync run
  hcpcs_codes             — current HCPCS procedure codes (quarterly CMS release)
  hcpcs_sync_log          — audit log of every HCPCS sync run
  icd_pcs_codes           — current ICD-10-PCS procedure codes (annual CMS release)
  icd_pcs_sync_history    — audit log of every ICD-10-PCS sync run
"""

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime,
    Integer, Numeric, String, Text, func,
)
from app.database import Base


# ---------------------------------------------------------------------------
# ICD-10-CM
# ---------------------------------------------------------------------------

class IcdCode(Base):
    """ICD-10-CM diagnosis codes."""

    __tablename__ = "icd_codes"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    code           = Column(String(10),  nullable=False, index=True)
    description    = Column(Text,        nullable=False)
    category       = Column(String(3),   nullable=False, index=True)
    eff_date       = Column(Date,        nullable=True)

    is_active      = Column(Boolean,     nullable=False, default=True, index=True)
    term_dt        = Column(Date,        nullable=True)
    data_hash      = Column(String(32),  nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at     = Column(DateTime(timezone=True), server_default=func.now(),
                            onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"<IcdCode {self.code} | {status} | {self.description[:40]}>"


class SyncHistory(Base):
    """Immutable audit log — one row per ICD sync run."""

    __tablename__ = "icd_sync_history"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    synced_at     = Column(DateTime(timezone=True), server_default=func.now(),
                           nullable=False, index=True)
    source_url    = Column(Text,        nullable=False)
    version       = Column(String(10),  nullable=True)
    codes_added   = Column(Integer,     default=0, nullable=False)
    codes_updated = Column(Integer,     default=0, nullable=False)
    codes_deleted = Column(Integer,     default=0, nullable=False)
    codes_skipped = Column(Integer,     default=0, nullable=False)
    status        = Column(String(20),  nullable=False)
    error_message = Column(Text,        nullable=True)

    def __repr__(self) -> str:
        return (
            f"<SyncHistory FY{self.version} | {self.status} | "
            f"+{self.codes_added} ~{self.codes_updated} -{self.codes_deleted}>"
        )


# ---------------------------------------------------------------------------
# HCPCS Level II
# ---------------------------------------------------------------------------

class HcpcsModifier(Base):
    """HCPCS modifiers (2-character codes)."""

    __tablename__ = "hcpcs_modifiers"

    id                = Column(Integer,  primary_key=True, autoincrement=True)
    code              = Column(String(2),    nullable=False, index=True)
    description       = Column(Text,         nullable=True)
    category          = Column(String(10),   nullable=True)
    eff_date          = Column(Date,         nullable=True)
    term_dt           = Column(Date,         nullable=True)

    is_active         = Column(Boolean,      nullable=False, default=True, index=True)
    data_hash         = Column(String(32),   nullable=True)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    updated_at        = Column(DateTime(timezone=True), server_default=func.now(),
                               onupdate=func.now())

    def __repr__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"<HcpcsModifier {self.code} | {status} | {(self.description or '')[:40]}>"


class HcpcsModifierSyncLog(Base):
    """Immutable audit log — one row per HCPCS modifier sync run."""

    __tablename__ = "hcpcs_modifier_sync_log"

    id            = Column(BigInteger,  primary_key=True, autoincrement=True)
    synced_at     = Column(DateTime(timezone=True), server_default=func.now(),
                           nullable=False, index=True)
    source_url    = Column(Text,        nullable=True)
    zip_filename  = Column(String(255), nullable=True)
    update_cycle  = Column(String(30),  nullable=True)
    total_codes   = Column(Integer,     nullable=True)
    inserted      = Column(Integer,     default=0, nullable=False)
    updated       = Column(Integer,     default=0, nullable=False)
    deleted       = Column(Integer,     default=0, nullable=False)
    skipped       = Column(Integer,     default=0, nullable=False)
    status        = Column(String(20),  nullable=False)
    error_message = Column(Text,        nullable=True)

    def __repr__(self) -> str:
        return (
            f"<HcpcsModifierSyncLog {self.update_cycle} | {self.status} | "
            f"+{self.inserted} ~{self.updated} -{self.deleted}>"
        )


class HcpcsCode(Base):
    """HCPCS Level II procedure codes."""

    __tablename__ = "hcpcs_codes"

    id                = Column(Integer,  primary_key=True, autoincrement=True)
    code              = Column(String(10),   nullable=False, index=True)
    description       = Column(Text,         nullable=True)
    category          = Column(String(10),   nullable=True)
    eff_date          = Column(Date,         nullable=True)
    term_dt           = Column(Date,         nullable=True)

    is_active         = Column(Boolean,      nullable=False, default=True, index=True)
    data_hash         = Column(String(32),   nullable=True)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    updated_at        = Column(DateTime(timezone=True), server_default=func.now(),
                               onupdate=func.now())

    def __repr__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"<HcpcsCode {self.code} | {status} | {(self.description or '')[:40]}>"


class HcpcsSyncLog(Base):
    """Immutable audit log — one row per HCPCS sync run."""

    __tablename__ = "hcpcs_sync_log"

    id            = Column(BigInteger,  primary_key=True, autoincrement=True)
    synced_at     = Column(DateTime(timezone=True), server_default=func.now(),
                           nullable=False, index=True)
    source_url    = Column(Text,        nullable=True)
    zip_filename  = Column(String(255), nullable=True)
    update_cycle  = Column(String(30),  nullable=True)
    total_codes   = Column(Integer,     nullable=True)
    inserted      = Column(Integer,     default=0, nullable=False)
    updated       = Column(Integer,     default=0, nullable=False)
    deleted       = Column(Integer,     default=0, nullable=False)
    skipped       = Column(Integer,     default=0, nullable=False)
    status        = Column(String(20),  nullable=False)
    error_message = Column(Text,        nullable=True)

    def __repr__(self) -> str:
        return (
            f"<HcpcsSyncLog {self.update_cycle} | {self.status} | "
            f"+{self.inserted} ~{self.updated} -{self.deleted}>"
        )


# ---------------------------------------------------------------------------
# ICD-10-PCS
# ---------------------------------------------------------------------------

class IcdPcsCode(Base):
    """ICD-10-PCS inpatient procedure codes (7 alphanumeric characters)."""

    __tablename__ = "icd_pcs_codes"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    code           = Column(String(7),   nullable=False, index=True)
    description    = Column(Text,        nullable=False)
    category       = Column(String(1),   nullable=True,  index=True)
    eff_date       = Column(Date,        nullable=True)

    is_active      = Column(Boolean,     nullable=False, default=True, index=True)
    term_dt        = Column(Date,        nullable=True)
    data_hash      = Column(String(32),  nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at     = Column(DateTime(timezone=True), server_default=func.now(),
                            onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"<IcdPcsCode {self.code} | {status} | {self.description[:40]}>"


class IcdPcsSyncHistory(Base):
    """Immutable audit log — one row per ICD-10-PCS sync run."""

    __tablename__ = "icd_pcs_sync_history"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    synced_at     = Column(DateTime(timezone=True), server_default=func.now(),
                           nullable=False, index=True)
    source_url    = Column(Text,        nullable=False)
    version       = Column(String(10),  nullable=True)
    codes_added   = Column(Integer,     default=0, nullable=False)
    codes_updated = Column(Integer,     default=0, nullable=False)
    codes_deleted = Column(Integer,     default=0, nullable=False)
    codes_skipped = Column(Integer,     default=0, nullable=False)
    status        = Column(String(20),  nullable=False)
    error_message = Column(Text,        nullable=True)

    def __repr__(self) -> str:
        return (
            f"<IcdPcsSyncHistory FY{self.version} | {self.status} | "
            f"+{self.codes_added} ~{self.codes_updated} -{self.codes_deleted}>"
        )
