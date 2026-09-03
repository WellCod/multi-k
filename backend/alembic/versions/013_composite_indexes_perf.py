"""013 — índices compostos de performance em propostas, cotacoes e cotacao_jobs.

Revision ID: 013_composite_indexes_perf
Revises: 012_proposta_numero_apolice
Create Date: 2026-09-03
"""

from alembic import op

revision = "013_composite_indexes_perf"
down_revision = "012_proposta_numero_apolice"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CONCURRENTLY exige autocommit (fora de bloco transacional).
    with op.get_context().autocommit_block():
        # propostas: queries por corretor ordenadas por data de transmissão
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_propostas_usuario_transmitida "
            "ON propostas (usuario_id, transmitida_em DESC)"
        )
        # cotacoes: queries por corretor + relatórios por período
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cotacoes_usuario_criado "
            "ON cotacoes (usuario_id, criado_em DESC)"
        )
        # cotacao_jobs: lookup frequente por cotacao + cia + status na transmissão
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cotacao_jobs_cot_cia_status "
            "ON cotacao_jobs (cotacao_id, cia, status)"
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cotacao_jobs_cot_cia_status")
    op.execute("DROP INDEX IF EXISTS ix_cotacoes_usuario_criado")
    op.execute("DROP INDEX IF EXISTS ix_propostas_usuario_transmitida")
