"""create icd tables

Revision ID: 0001
Revises:
Create Date: 2025-01-01

Creates:
  - icd_codes       (main code table)
  - sync_history    (audit log)
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # icd_codes
    # ------------------------------------------------------------------
    op.create_table(
        "icd_codes",
        sa.Column("id",             sa.Integer(),      autoincrement=True, nullable=False),
        sa.Column("code",           sa.String(10),     nullable=False),
        sa.Column("code_with_dot",  sa.String(12),     nullable=False),
        sa.Column("description",    sa.Text(),         nullable=False),
        sa.Column("category",       sa.String(3),      nullable=False),
        sa.Column("chapter",        sa.String(80),     nullable=True),
        sa.Column("is_billable",    sa.Boolean(),      nullable=False, default=False),
        sa.Column("version",        sa.String(10),     nullable=False),
        sa.Column("effective_date", sa.Date(),         nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at",     sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes
    op.create_index("ix_icd_codes_code",        "icd_codes", ["code"],        unique=True)
    op.create_index("ix_icd_codes_category",    "icd_codes", ["category"])
    op.create_index("ix_icd_codes_is_billable", "icd_codes", ["is_billable"])

    # ------------------------------------------------------------------
    # sync_history
    # ------------------------------------------------------------------
    op.create_table(
        "sync_history",
        sa.Column("id",            sa.Integer(),      autoincrement=True, nullable=False),
        sa.Column("synced_at",     sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("source_url",    sa.Text(),         nullable=False),
        sa.Column("version",       sa.String(10),     nullable=True),
        sa.Column("codes_added",   sa.Integer(),      nullable=False, default=0),
        sa.Column("codes_updated", sa.Integer(),      nullable=False, default=0),
        sa.Column("codes_deleted", sa.Integer(),      nullable=False, default=0),
        sa.Column("status",        sa.String(20),     nullable=False),
        sa.Column("error_message", sa.Text(),         nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_history_synced_at", "sync_history", ["synced_at"])


def downgrade() -> None:
    # Undo in reverse order
    op.drop_index("ix_sync_history_synced_at", table_name="sync_history")
    op.drop_table("sync_history")

    op.drop_index("ix_icd_codes_is_billable", table_name="icd_codes")
    op.drop_index("ix_icd_codes_category",    table_name="icd_codes")
    op.drop_index("ix_icd_codes_code",        table_name="icd_codes")
    op.drop_table("icd_codes")
