"""012 — numero_apolice on propostas

Revision ID: 012_proposta_numero_apolice
Revises: 011_cpf_idx_expand
Create Date: 2026-09-02
"""

import sqlalchemy as sa

from alembic import op

revision = "012_proposta_numero_apolice"
down_revision = "011_cpf_idx_expand"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "propostas",
        sa.Column("numero_apolice", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("propostas", "numero_apolice")
