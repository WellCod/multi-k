"""014 — tabela comissao_config: comissão padrão por CIA e ramo.

Revision ID: 014_comissao_config
Revises: 013_composite_indexes_perf
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op

revision = "014_comissao_config"
down_revision = "013_composite_indexes_perf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comissao_config",
        sa.Column("cia", sa.String(50), nullable=False),
        sa.Column("ramo", sa.String(20), nullable=False),
        sa.Column("pct_padrao", sa.Numeric(5, 4), nullable=False),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("cia", "ramo"),
    )


def downgrade() -> None:
    op.drop_table("comissao_config")
