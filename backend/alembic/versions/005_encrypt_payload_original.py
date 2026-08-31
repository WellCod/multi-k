"""encrypt payload_original with AES-256-GCM (C1)

Revision ID: 005_encrypt_payload_original
Revises: 004
Create Date: 2026-08-28
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "005_encrypt_payload_original"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Null out existing JSONB values (dev data — no prod yet)
    op.execute("UPDATE cotacoes SET payload_original = NULL")
    # 2. Change column type from JSONB to TEXT
    op.alter_column(
        "cotacoes",
        "payload_original",
        existing_type=postgresql.JSONB(),
        type_=sa.Text(),
        existing_nullable=True,
        postgresql_using="NULL::text",
    )


def downgrade() -> None:
    op.alter_column(
        "cotacoes",
        "payload_original",
        existing_type=sa.Text(),
        type_=postgresql.JSONB(),
        existing_nullable=True,
        postgresql_using="NULL::jsonb",
    )
