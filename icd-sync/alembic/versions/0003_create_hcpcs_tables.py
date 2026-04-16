"""create hcpcs tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-16

Creates:
  - hcpcs_modifiers          (2-character HCPCS modifiers)
  - hcpcs_modifier_sync_log  (audit log for modifier syncs)
  - hcpcs_codes              (HCPCS procedure codes)
  - hcpcs_sync_log           (audit log for code syncs)
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # hcpcs_modifiers (2-character modifier codes)
    # ------------------------------------------------------------------
    op.create_table(
        "hcpcs_modifiers",
        sa.Column("id",                sa.Integer(),      autoincrement=True, nullable=False),
        sa.Column("hcpc",              sa.String(2),      nullable=False),
        sa.Column("seqnum",            sa.Integer(),      nullable=True),
        sa.Column("recid",             sa.Integer(),      nullable=True),
        sa.Column("long_description",  sa.Text(),         nullable=True),
        sa.Column("add_dt",            sa.Date(),         nullable=True),
        sa.Column("act_eff_dt",        sa.Date(),         nullable=True),
        sa.Column("term_dt",           sa.Date(),         nullable=True),
        sa.Column("is_active",         sa.Boolean(),      nullable=False, default=True),
        sa.Column("data_hash",         sa.String(32),     nullable=True),
        sa.Column("created_at",        sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at",        sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes for modifiers
    op.create_index("ix_hcpcs_modifiers_hcpc",      "hcpcs_modifiers", ["hcpc"])
    op.create_index("ix_hcpcs_modifiers_is_active", "hcpcs_modifiers", ["is_active"])

    # ------------------------------------------------------------------
    # hcpcs_modifier_sync_log (audit log for modifier syncs)
    # ------------------------------------------------------------------
    op.create_table(
        "hcpcs_modifier_sync_log",
        sa.Column("id",            sa.BigInteger(),    autoincrement=True, nullable=False),
        sa.Column("synced_at",     sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("source_url",    sa.Text(),          nullable=True),
        sa.Column("zip_filename",  sa.String(255),     nullable=True),
        sa.Column("update_cycle",  sa.String(30),      nullable=True),
        sa.Column("total_codes",   sa.Integer(),       nullable=True),
        sa.Column("inserted",      sa.Integer(),       nullable=False, default=0),
        sa.Column("updated",       sa.Integer(),       nullable=False, default=0),
        sa.Column("deleted",       sa.Integer(),       nullable=False, default=0),
        sa.Column("skipped",       sa.Integer(),       nullable=False, default=0),
        sa.Column("status",        sa.String(20),      nullable=False),
        sa.Column("error_message", sa.Text(),          nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hcpcs_modifier_sync_log_synced_at", "hcpcs_modifier_sync_log", ["synced_at"])

    # ------------------------------------------------------------------
    # hcpcs_codes (HCPCS procedure codes)
    # ------------------------------------------------------------------
    op.create_table(
        "hcpcs_codes",
        sa.Column("id",                sa.Integer(),      autoincrement=True, nullable=False),
        sa.Column("hcpc",              sa.String(10),     nullable=False),
        sa.Column("seqnum",            sa.Integer(),      nullable=True),
        sa.Column("recid",             sa.Integer(),      nullable=True),
        sa.Column("long_description",  sa.Text(),         nullable=True),
        sa.Column("add_dt",            sa.Date(),         nullable=True),
        sa.Column("act_eff_dt",        sa.Date(),         nullable=True),
        sa.Column("term_dt",           sa.Date(),         nullable=True),
        sa.Column("is_active",         sa.Boolean(),      nullable=False, default=True),
        sa.Column("data_hash",         sa.String(32),     nullable=True),
        sa.Column("created_at",        sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at",        sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes for codes
    op.create_index("ix_hcpcs_codes_hcpc",      "hcpcs_codes", ["hcpc"])
    op.create_index("ix_hcpcs_codes_is_active", "hcpcs_codes", ["is_active"])

    # ------------------------------------------------------------------
    # hcpcs_sync_log (audit log for code syncs)
    # ------------------------------------------------------------------
    op.create_table(
        "hcpcs_sync_log",
        sa.Column("id",            sa.BigInteger(),    autoincrement=True, nullable=False),
        sa.Column("synced_at",     sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("source_url",    sa.Text(),          nullable=True),
        sa.Column("zip_filename",  sa.String(255),     nullable=True),
        sa.Column("update_cycle",  sa.String(30),      nullable=True),
        sa.Column("total_codes",   sa.Integer(),       nullable=True),
        sa.Column("inserted",      sa.Integer(),       nullable=False, default=0),
        sa.Column("updated",       sa.Integer(),       nullable=False, default=0),
        sa.Column("deleted",       sa.Integer(),       nullable=False, default=0),
        sa.Column("skipped",       sa.Integer(),       nullable=False, default=0),
        sa.Column("status",        sa.String(20),      nullable=False),
        sa.Column("error_message", sa.Text(),          nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hcpcs_sync_log_synced_at", "hcpcs_sync_log", ["synced_at"])


def downgrade() -> None:
    # Undo in reverse order
    op.drop_index("ix_hcpcs_sync_log_synced_at", table_name="hcpcs_sync_log")
    op.drop_table("hcpcs_sync_log")

    op.drop_index("ix_hcpcs_codes_is_active", table_name="hcpcs_codes")
    op.drop_index("ix_hcpcs_codes_hcpc", table_name="hcpcs_codes")
    op.drop_table("hcpcs_codes")

    op.drop_index("ix_hcpcs_modifier_sync_log_synced_at", table_name="hcpcs_modifier_sync_log")
    op.drop_table("hcpcs_modifier_sync_log")

    op.drop_index("ix_hcpcs_modifiers_is_active", table_name="hcpcs_modifiers")
    op.drop_index("ix_hcpcs_modifiers_hcpc", table_name="hcpcs_modifiers")
    op.drop_table("hcpcs_modifiers")
