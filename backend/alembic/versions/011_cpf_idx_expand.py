"""011 — expand cpf_idx to VARCHAR(70) for v1: prefix + 64-char SHA-256 hash.

Revision ID: 011_cpf_idx_expand
Revises: 010_clientes_trgm_search
Create Date: 2026-09-01
"""

import sqlalchemy as sa

from alembic import op

revision = "011_cpf_idx_expand"
down_revision = "010_clientes_trgm_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "clientes",
        "cpf_idx",
        existing_type=sa.String(64),
        type_=sa.String(70),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "clientes",
        "cpf_idx",
        existing_type=sa.String(70),
        type_=sa.String(64),
        existing_nullable=False,
    )
