"""Complete parentesco options with the enum accepted by Justos (J2 §4)."""

import sqlalchemy as sa

from alembic import op
from app.domain.auth import TENANT_ID
from app.infra.ui_domain_seed import ui_domain_rows

revision = "017_parentesco_enum_justos"
down_revision = "016_ui_domains"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    for row in ui_domain_rows():
        exists = connection.execute(
            sa.text(
                "SELECT 1 FROM dominio"
                " WHERE tipo = :tipo AND codigo = :codigo AND cia IS NULL"
            ),
            {"tipo": row["tipo"], "codigo": row["codigo"]},
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
