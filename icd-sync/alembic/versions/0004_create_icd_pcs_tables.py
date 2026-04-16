"""create icd pcs tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-16

Creates:
  - icd_pcs_codes        (ICD-10-PCS inpatient procedure codes)
  - icd_pcs_sync_history (audit log for PCS syncs)
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # icd_pcs_codes (ICD-10-PCS procedure codes)
    # ------------------------------------------------------------------
    op.create_table(
        "icd_pcs_codes",
        sa.Column("id",             sa.Integer(),      autoincrement=True, nullable=False),
        sa.Column("code",           sa.String(7),      nullable=False),
        sa.Column("description",    sa.Text(),         nullable=False),
        sa.Column("section",        sa.String(1),      nullable=True),
        sa.Column("section_name",   sa.String(100),    nullable=True),
        sa.Column("is_valid",       sa.Boolean(),      nullable=False, default=True),
        sa.Column("version",        sa.String(10),     nullable=False),
        sa.Column("effective_date", sa.Date(),         nullable=True),
        sa.Column("is_active",      sa.Boolean(),      nullable=False, default=True),
        sa.Column("term_dt",        sa.Date(),         nullable=True),
        sa.Column("data_hash",      sa.String(32),     nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at",     sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes for PCS codes
    op.create_index("ix_icd_pcs_codes_code",     "icd_pcs_codes", ["code"])
    op.create_index("ix_icd_pcs_codes_section",  "icd_pcs_codes", ["section"])
    op.create_index("ix_icd_pcs_codes_is_valid", "icd_pcs_codes", ["is_valid"])
    op.create_index("ix_icd_pcs_codes_is_active", "icd_pcs_codes", ["is_active"])

    # ------------------------------------------------------------------
    # icd_pcs_sync_history (audit log for PCS syncs)
    # ------------------------------------------------------------------
    op.create_table(
        "icd_pcs_sync_history",
        sa.Column("id",            sa.Integer(),      autoincrement=True, nullable=False),
        sa.Column("synced_at",     sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("source_url",    sa.Text(),         nullable=False),
        sa.Column("version",       sa.String(10),     nullable=True),
        sa.Column("codes_added",   sa.Integer(),      default=0, nullable=False),
        sa.Column("codes_updated", sa.Integer(),      default=0, nullable=False),
        sa.Column("codes_deleted", sa.Integer(),      default=0, nullable=False),
        sa.Column("codes_skipped", sa.Integer(),      default=0, nullable=False),
        sa.Column("status",        sa.String(20),     nullable=False),
        sa.Column("error_message", sa.Text(),         nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_icd_pcs_sync_history_synced_at", "icd_pcs_sync_history", ["synced_at"])


def downgrade() -> None:
    # Undo in reverse order
    op.drop_index("ix_icd_pcs_sync_history_synced_at", table_name="icd_pcs_sync_history")
    op.drop_table("icd_pcs_sync_history")

    op.drop_index("ix_icd_pcs_codes_is_active", table_name="icd_pcs_codes")
    op.drop_index("ix_icd_pcs_codes_is_valid", table_name="icd_pcs_codes")
    op.drop_index("ix_icd_pcs_codes_section", table_name="icd_pcs_codes")
    op.drop_index("ix_icd_pcs_codes_code", table_name="icd_pcs_codes")
    op.drop_table("icd_pcs_codes")
