"""result columns on cotacao_jobs (multi-CIA)

Revision ID: 006_cotacao_job_resultado
Revises: 005_encrypt_payload_original
Create Date: 2026-08-28
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "006_cotacao_job_resultado"
down_revision = "005_encrypt_payload_original"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cotacao_jobs", sa.Column("cotacao_id_cia", sa.String(100), nullable=True)
    )
    op.add_column(
        "cotacao_jobs",
        sa.Column("premio_total", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "cotacao_jobs",
        sa.Column(
            "restricoes",
            postgresql.JSONB(),
            nullable=True,
            server_default="[]",
        ),
    )
    op.add_column(
        "cotacao_jobs",
        sa.Column(
            "mensagens",
            postgresql.JSONB(),
            nullable=True,
            server_default="[]",
        ),
    )
    op.add_column(
        "cotacao_jobs",
        sa.Column(
            "necessita_vistoria",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "cotacao_jobs",
        sa.Column("status_resultado", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    for col in [
        "cotacao_id_cia",
        "premio_total",
        "restricoes",
        "mensagens",
        "necessita_vistoria",
        "status_resultado",
    ]:
        op.drop_column("cotacao_jobs", col)
