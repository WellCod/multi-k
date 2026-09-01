"""010 — pg_trgm extension + GIN indexes for client search.

Revision ID: 010_clientes_trgm_search
Revises: 009_cliente_soft_delete
Create Date: 2026-09-01
"""

from alembic import op

revision = "010_clientes_trgm_search"
down_revision = "009_cliente_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_clientes_nome_trgm "
        "ON clientes USING gin (nome gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_clientes_email_trgm "
        "ON clientes USING gin (email gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_clientes_telefone_trgm "
        "ON clientes USING gin (telefone gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_clientes_telefone_trgm")
    op.execute("DROP INDEX IF EXISTS ix_clientes_email_trgm")
    op.execute("DROP INDEX IF EXISTS ix_clientes_nome_trgm")
