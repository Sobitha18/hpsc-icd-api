"""create all code tables with normalized unified schema

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-16

Creates all code tables (icd_codes, icd_sync_history, icd_pcs_codes, icd_pcs_sync_history,
hcpcs_codes, hcpcs_sync_log, hcpcs_modifiers, hcpcs_modifier_sync_log) with unified schema:
  id, code, description, category, eff_date, is_active, term_dt, data_hash, created_at, updated_at
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ICD-10-CM tables
    op.create_table(
        "icd_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(10), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(3), nullable=False, index=True),
        sa.Column("eff_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True, index=True),
        sa.Column("term_dt", sa.Date(), nullable=True),
        sa.Column("data_hash", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "icd_sync_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, index=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("version", sa.String(10), nullable=True),
        sa.Column("codes_added", sa.Integer(), default=0, nullable=False),
        sa.Column("codes_updated", sa.Integer(), default=0, nullable=False),
        sa.Column("codes_deleted", sa.Integer(), default=0, nullable=False),
        sa.Column("codes_skipped", sa.Integer(), default=0, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ICD-10-PCS tables
    op.create_table(
        "icd_pcs_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(7), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(1), nullable=True, index=True),
        sa.Column("eff_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True, index=True),
        sa.Column("term_dt", sa.Date(), nullable=True),
        sa.Column("data_hash", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "icd_pcs_sync_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, index=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("version", sa.String(10), nullable=True),
        sa.Column("codes_added", sa.Integer(), default=0, nullable=False),
        sa.Column("codes_updated", sa.Integer(), default=0, nullable=False),
        sa.Column("codes_deleted", sa.Integer(), default=0, nullable=False),
        sa.Column("codes_skipped", sa.Integer(), default=0, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # HCPCS tables
    op.create_table(
        "hcpcs_modifiers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(2), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(10), nullable=True),
        sa.Column("eff_date", sa.Date(), nullable=True),
        sa.Column("term_dt", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True, index=True),
        sa.Column("data_hash", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "hcpcs_modifier_sync_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, index=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("zip_filename", sa.String(255), nullable=True),
        sa.Column("update_cycle", sa.String(30), nullable=True),
        sa.Column("total_codes", sa.Integer(), nullable=True),
        sa.Column("inserted", sa.Integer(), default=0, nullable=False),
        sa.Column("updated", sa.Integer(), default=0, nullable=False),
        sa.Column("deleted", sa.Integer(), default=0, nullable=False),
        sa.Column("skipped", sa.Integer(), default=0, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "hcpcs_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(10), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(10), nullable=True),
        sa.Column("eff_date", sa.Date(), nullable=True),
        sa.Column("term_dt", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True, index=True),
        sa.Column("data_hash", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "hcpcs_sync_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, index=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("zip_filename", sa.String(255), nullable=True),
        sa.Column("update_cycle", sa.String(30), nullable=True),
        sa.Column("total_codes", sa.Integer(), nullable=True),
        sa.Column("inserted", sa.Integer(), default=0, nullable=False),
        sa.Column("updated", sa.Integer(), default=0, nullable=False),
        sa.Column("deleted", sa.Integer(), default=0, nullable=False),
        sa.Column("skipped", sa.Integer(), default=0, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("hcpcs_sync_log")
    op.drop_table("hcpcs_codes")
    op.drop_table("hcpcs_modifier_sync_log")
    op.drop_table("hcpcs_modifiers")
    op.drop_table("icd_pcs_sync_history")
    op.drop_table("icd_pcs_codes")
    op.drop_table("icd_sync_history")
    op.drop_table("icd_codes")
