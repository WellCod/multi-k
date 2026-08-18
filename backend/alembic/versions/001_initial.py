"""fundacao: tabelas, RLS e auditoria append-only

Revision ID: 001
Revises:
Create Date: 2025-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("senha_hash", sa.Text, nullable=False),
        sa.Column("papel", sa.String(20), nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=False),
            nullable=False,
            server_default=_TENANT,
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_table(
        "sessoes",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "usuario_id",
            UUID(as_uuid=False),
            sa.ForeignKey("usuarios.id"),
            nullable=False,
        ),
        sa.Column(
            "criada_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_origem", sa.String(45)),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=False),
            nullable=False,
            server_default=_TENANT,
        ),
    )
    op.create_table(
        "tentativas_login",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("identificador", sa.String(255), nullable=False),
        sa.Column("contagem", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "ultima_tentativa",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("bloqueado_ate", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_tentativas_login_identificador",
        "tentativas_login",
        ["identificador"],
    )
    op.create_table(
        "dominio",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("cia", sa.String(50)),
        sa.Column("tipo", sa.String(50), nullable=False),
        sa.Column("codigo", sa.String(50), nullable=False),
        sa.Column("descricao", sa.String(255), nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=False),
            nullable=False,
            server_default=_TENANT,
        ),
    )
    op.create_index("ix_dominio_tipo_codigo", "dominio", ["tipo", "codigo"])
    op.create_table(
        "eventos",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("tipo", sa.String(50), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("usuario_id", UUID(as_uuid=False), nullable=False),
        sa.Column(
            "ocorrido_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=False),
            nullable=False,
            server_default=_TENANT,
        ),
    )
    op.create_table(
        "auditoria",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tipo", sa.String(50), nullable=False),
        sa.Column("usuario_id", UUID(as_uuid=False)),
        sa.Column("ip_origem", sa.String(45)),
        sa.Column("dados", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=False),
            nullable=False,
            server_default=_TENANT,
        ),
    )

    # RLS — corretor vê só seus próprios eventos, admin vê tudo.
    op.execute("ALTER TABLE eventos ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE eventos FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY eventos_isolamento ON eventos
        USING (
            current_setting('app.papel', true) = 'admin'
            OR usuario_id::text = current_setting('app.usuario_id', true)
        )
        """
    )

    # Auditoria append-only — trigger impede UPDATE e DELETE.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_audit_append_only()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'auditoria é append-only: % proibido', TG_OP;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER tg_auditoria_no_update
            BEFORE UPDATE ON auditoria
            FOR EACH ROW EXECUTE FUNCTION enforce_audit_append_only()
        """
    )
    op.execute(
        """
        CREATE TRIGGER tg_auditoria_no_delete
            BEFORE DELETE ON auditoria
            FOR EACH ROW EXECUTE FUNCTION enforce_audit_append_only()
        """
    )

    # Seed — domínios com valores plausíveis (substituídos pela API Yelum).
    op.execute(
        sa.text(
            """
            INSERT INTO dominio (cia, tipo, codigo, descricao) VALUES
            (NULL, 'cobertura_auto', 'CASCO', 'Casco (colisão, incêndio, roubo)'),
            (NULL, 'cobertura_auto', 'RCF', 'Responsabilidade Civil Facultativa'),
            (NULL, 'cobertura_auto', 'APP', 'Acidentes Pessoais de Passageiros'),
            (NULL, 'cobertura_auto', 'VIDROS',       'Cobertura de Vidros'),
            (NULL, 'cobertura_auto', 'CARTA_VERDE',  'Carta Verde (Mercosul)'),
            (NULL, 'cobertura_res',  'INCENDIO',     'Incêndio, Raio e Explosão'),
            (NULL, 'cobertura_res',  'ROUBO',        'Roubo e Furto Qualificado'),
            (NULL, 'cobertura_res',  'RESP_CIVIL',   'Responsabilidade Civil'),
            (NULL, 'cobertura_res',  'DANOS_ELET',   'Danos Elétricos'),
            (NULL, 'cobertura_res',  'QUEBRA_VIDROS','Quebra de Vidros'),
            (NULL, 'cobertura_res',  'ALUGUEL',      'Perda de Aluguel'),
            (NULL, 'franquia',       'REDUZIDA',     'Franquia Reduzida'),
            (NULL, 'franquia',       'NORMAL',       'Franquia Normal'),
            (NULL, 'franquia',       'MAJORADA',     'Franquia Majorada'),
            (NULL, 'parcelamento',   'AVISTA',       'À vista'),
            (NULL, 'parcelamento',   '2X',           '2 vezes'),
            (NULL, 'parcelamento',   '3X',           '3 vezes'),
            (NULL, 'parcelamento',   '6X',           '6 vezes'),
            (NULL, 'parcelamento',   '10X',          '10 vezes'),
            (NULL, 'estado_civil',   'SOLTEIRO',     'Solteiro(a)'),
            (NULL, 'estado_civil',   'CASADO',       'Casado(a)'),
            (NULL, 'estado_civil',   'DIVORCIADO',   'Divorciado(a)'),
            (NULL, 'estado_civil',   'VIUVO',        'Viúvo(a)'),
            (NULL, 'estado_civil',   'UNIAO_ESTAVEL','União Estável')
            """
        )
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tg_auditoria_no_delete ON auditoria")
    op.execute("DROP TRIGGER IF EXISTS tg_auditoria_no_update ON auditoria")
    op.execute("DROP FUNCTION IF EXISTS enforce_audit_append_only CASCADE")
    op.drop_table("auditoria")
    op.drop_table("eventos")
    op.drop_table("dominio")
    op.drop_table("tentativas_login")
    op.drop_table("sessoes")
    op.drop_table("usuarios")
