"""Complete domain options missing from databases seeded before they existed."""

import sqlalchemy as sa

from alembic import op
from app.domain.auth import TENANT_ID
from app.infra.seed import dominio_rows

revision = "018_dominios_faltantes"
down_revision = "017_parentesco_enum_justos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Completa apenas os tipos sem nenhuma opção.

    A checagem é por tipo, não por código: a 001 semeou estado_civil em
    MAIÚSCULA e o _SEED usa minúscula, então comparar código inseriria a
    mesma opção duas vezes. Tipo que já tem opção fica como está.
    """
    connection = op.get_bind()
    for row in dominio_rows():
        exists = connection.execute(
            sa.text("SELECT 1 FROM dominio WHERE tipo = :tipo AND cia IS NULL"),
            {"tipo": row["tipo"]},
        ).scalar()
        if not exists:
            connection.execute(
                sa.text(
                    "INSERT INTO dominio"
                    " (tipo, codigo, descricao, ativo, atualizado_em, tenant_id)"
                    " VALUES (:tipo, :codigo, :descricao, true, now(), :tenant)"
                ),
                {**row, "tenant": str(TENANT_ID)},
            )


def downgrade() -> None:
    # Domain data may have been synchronized since upgrade; never delete it blindly.
    pass
