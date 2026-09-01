"""Soft-delete em clientes: coluna ativo (default True).

Revision ID: 009_cliente_soft_delete
Revises: 008_cotacao_job_payload_resposta
Create Date: 2026-09-01
"""

import sqlalchemy as sa

from alembic import op

revision = "009_cliente_soft_delete"
down_revision = "008_cotacao_job_payload_resposta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clientes",
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_clientes_ativo", "clientes", ["ativo"])


def downgrade() -> None:
    op.drop_index("ix_clientes_ativo", table_name="clientes")
    op.drop_column("clientes", "ativo")
