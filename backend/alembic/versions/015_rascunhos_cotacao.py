"""Encrypted quotation drafts scoped to their owner."""

import sqlalchemy as sa

from alembic import op

revision = "015_rascunhos_cotacao"
down_revision = "014_comissao_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rascunhos_cotacao",
        sa.Column(
            "usuario_id", sa.Uuid(), sa.ForeignKey("usuarios.id"), primary_key=True
        ),
        sa.Column("dados", sa.Text(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
    )
    op.execute("ALTER TABLE rascunhos_cotacao ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE rascunhos_cotacao FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY rascunhos_owner ON rascunhos_cotacao
        USING (usuario_id::text = current_setting('app.usuario_id', true))
        WITH CHECK (usuario_id::text = current_setting('app.usuario_id', true))""")


def downgrade() -> None:
    op.drop_table("rascunhos_cotacao")
