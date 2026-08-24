"""fix: renomeia commissao_pct → comissao_pct na tabela propostas

Revision ID: 004
Revises: 003
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("propostas", "commissao_pct", new_column_name="comissao_pct")


def downgrade() -> None:
    op.alter_column("propostas", "comissao_pct", new_column_name="commissao_pct")
