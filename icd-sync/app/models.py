from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, Integer, String, Text, func
from app.database import Base


class CodeMixin:
    id         = Column(Integer,  primary_key=True, autoincrement=True)
    is_active  = Column(Boolean,  nullable=False, default=True, index=True)
    term_dt    = Column(Date,     nullable=True)
    data_hash  = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class IcdSyncMixin:
    id            = Column(Integer,  primary_key=True, autoincrement=True)
    synced_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    source_url    = Column(Text,        nullable=False)
    version       = Column(String(10),  nullable=True)
    codes_added   = Column(Integer,     default=0, nullable=False)
    codes_updated = Column(Integer,     default=0, nullable=False)
    codes_deleted = Column(Integer,     default=0, nullable=False)
    codes_skipped = Column(Integer,     default=0, nullable=False)
    status        = Column(String(20),  nullable=False)
    error_message = Column(Text,        nullable=True)


class HcpcsSyncMixin:
    id            = Column(BigInteger,   primary_key=True, autoincrement=True)
    synced_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    source_url    = Column(Text,         nullable=True)
    zip_filename  = Column(String(255),  nullable=True)
    update_cycle  = Column(String(30),   nullable=True)
    total_codes   = Column(Integer,      nullable=True)
    inserted      = Column(Integer,      default=0, nullable=False)
    updated       = Column(Integer,      default=0, nullable=False)
    deleted       = Column(Integer,      default=0, nullable=False)
    skipped       = Column(Integer,      default=0, nullable=False)
    status        = Column(String(20),   nullable=False)
    error_message = Column(Text,         nullable=True)


class IcdCode(CodeMixin, Base):
    __tablename__ = "icd_codes"
    code        = Column(String(10), nullable=False, index=True)
    description = Column(Text,       nullable=False)
    category    = Column(String(3),  nullable=False, index=True)
    eff_date    = Column(Date,       nullable=True)



class HcpcsModifier(CodeMixin, Base):
    __tablename__ = "hcpcs_modifiers"
    code        = Column(String(2),  nullable=False, index=True)
    description = Column(Text,       nullable=True)
    category    = Column(String(10), nullable=True)
    eff_date    = Column(Date,       nullable=True)


class HcpcsCode(CodeMixin, Base):
    __tablename__ = "hcpcs_codes"
    code        = Column(String(10), nullable=False, index=True)
    description = Column(Text,       nullable=True)
    category    = Column(String(10), nullable=True)
    eff_date    = Column(Date,       nullable=True)


class IcdPcsCode(CodeMixin, Base):
    __tablename__ = "icd_pcs_codes"
    code        = Column(String(7),  nullable=False, index=True)
    description = Column(Text,       nullable=False)
    category    = Column(String(10), nullable=True,  index=True)
    eff_date    = Column(Date,       nullable=True)


class SyncHistory(IcdSyncMixin, Base):
    __tablename__ = "icd_sync_history"


class IcdPcsSyncHistory(IcdSyncMixin, Base):
    __tablename__ = "icd_pcs_sync_history"


class HcpcsModifierSyncLog(HcpcsSyncMixin, Base):
    __tablename__ = "hcpcs_modifier_sync_log"


class HcpcsSyncLog(HcpcsSyncMixin, Base):
    __tablename__ = "hcpcs_sync_log"
