"""payload_resposta on cotacao_jobs

Revision ID: 008_cotacao_job_payload_resposta
Revises: 007_cobertura_imovel_dominios
Create Date: 2026-08-28
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "008_cotacao_job_payload_resposta"
down_revision = "007_cobertura_imovel_dominios"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cotacao_jobs",
        sa.Column("payload_resposta", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cotacao_jobs", "payload_resposta")
