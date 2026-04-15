"""rename sync_history to icd_sync_history

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-15

Renames sync_history → icd_sync_history so the table name clearly
belongs to the ICD sync (HCPCS will have its own hcpcs_sync_history).
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("sync_history", "icd_sync_history")
    op.execute(
        "ALTER INDEX ix_sync_history_synced_at "
        "RENAME TO ix_icd_sync_history_synced_at"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX ix_icd_sync_history_synced_at "
        "RENAME TO ix_sync_history_synced_at"
    )
    op.rename_table("icd_sync_history", "sync_history")
