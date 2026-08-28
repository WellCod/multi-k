"""Renomeia cobertura_residencia → cobertura_imovel e atualiza códigos para CBE.

Revision ID: 007_cobertura_imovel_dominios
Revises: 006_cotacao_job_resultado
Create Date: 2026-08-28
"""

import sqlalchemy as sa

from alembic import op

revision = "007_cobertura_imovel_dominios"
down_revision = "006_cotacao_job_resultado"
branch_labels = None
depends_on = None

_NOVOS = [
    ("CBE10", "Incêndio, Raio e Explosão"),
    ("CBE20", "Danos Elétricos"),
    ("CBE30", "Roubo e Furto de Bens"),
    ("CBE40", "Vendaval, Granizo e Queda de Aeronaves"),
    ("CBE50", "Responsabilidade Civil Familiar"),
    ("CBE60", "Quebra de Vidros"),
    ("CBE70", "Aluguel"),
    ("CBE80", "Desmoronamento"),
]

_ANTIGOS = ["INCENDIO", "ROUBO", "RESP_CIVIL", "DANOS_ELET", "QUEBRA_VIDROS"]


def upgrade() -> None:
    conn = op.get_bind()
    # Remove registros antigos de cobertura_residencia
    conn.execute(sa.text("DELETE FROM dominio WHERE tipo = 'cobertura_residencia'"))
    # Insere novos registros cobertura_imovel (CBE)
    for codigo, descricao in _NOVOS:
        conn.execute(
            sa.text(
                "INSERT INTO dominio (tipo, codigo, descricao)"
                " VALUES ('cobertura_imovel', :codigo, :descricao)"
                " ON CONFLICT (tipo, codigo)"
                " DO UPDATE SET descricao = EXCLUDED.descricao"
            ),
            {"codigo": codigo, "descricao": descricao},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM dominio WHERE tipo = 'cobertura_imovel'"))
    _old = [
        ("INCENDIO", "Incêndio e explosão"),
        ("ROUBO", "Roubo e furto qualificado"),
        ("RESP_CIVIL", "Responsabilidade civil"),
        ("DANOS_ELET", "Danos elétricos"),
        ("QUEBRA_VIDROS", "Quebra de vidros"),
    ]
    for codigo, descricao in _old:
        conn.execute(
            sa.text(
                "INSERT INTO dominio (tipo, codigo, descricao)"
                " VALUES ('cobertura_residencia', :codigo, :descricao)"
                " ON CONFLICT (tipo, codigo)"
                " DO UPDATE SET descricao = EXCLUDED.descricao"
            ),
            {"codigo": codigo, "descricao": descricao},
        )
