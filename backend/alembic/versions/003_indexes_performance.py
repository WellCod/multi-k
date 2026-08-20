"""perf: índices em foreign keys e colunas de filtro frequente

Revision ID: 003
Revises: db3e30d3388b
Create Date: 2026-08-20

"""

from collections.abc import Sequence

from alembic import op

revision: str = "003"
down_revision: str | None = "db3e30d3388b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_cotacoes_usuario_id", "cotacoes", ["usuario_id"])
    op.create_index("ix_cotacoes_cliente_id", "cotacoes", ["cliente_id"])
    op.create_index("ix_cotacoes_criado_em", "cotacoes", ["criado_em"])
    op.create_index("ix_cotacoes_status", "cotacoes", ["status"])
    op.create_index("ix_propostas_usuario_id", "propostas", ["usuario_id"])
    op.create_index("ix_propostas_cotacao_id", "propostas", ["cotacao_id"])
    op.create_index("ix_propostas_transmitida_em", "propostas", ["transmitida_em"])
    op.create_index(
        "ix_cotacao_jobs_status_criado_em",
        "cotacao_jobs",
        ["status", "criado_em"],
    )


def downgrade() -> None:
    op.drop_index("ix_cotacao_jobs_status_criado_em", table_name="cotacao_jobs")
    op.drop_index("ix_propostas_transmitida_em", table_name="propostas")
    op.drop_index("ix_propostas_cotacao_id", table_name="propostas")
    op.drop_index("ix_propostas_usuario_id", table_name="propostas")
    op.drop_index("ix_cotacoes_status", table_name="cotacoes")
    op.drop_index("ix_cotacoes_criado_em", table_name="cotacoes")
    op.drop_index("ix_cotacoes_cliente_id", table_name="cotacoes")
    op.drop_index("ix_cotacoes_usuario_id", table_name="cotacoes")
