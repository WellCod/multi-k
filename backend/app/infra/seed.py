"""Seed inicial para a tabela dominio.

Valores plausíveis sem hardcode em Python ou TypeScript.
A tabela será sincronizada com a API da seguradora quando a credencial chegar.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.models import Dominio

_SEED: list[dict[str, str]] = [
    # Estado civil
    {"tipo": "estado_civil", "codigo": "solteiro", "descricao": "Solteiro(a)"},
    {"tipo": "estado_civil", "codigo": "casado", "descricao": "Casado(a)"},
    {"tipo": "estado_civil", "codigo": "divorciado", "descricao": "Divorciado(a)"},
    {"tipo": "estado_civil", "codigo": "viuvo", "descricao": "Viúvo(a)"},
    {
        "tipo": "estado_civil",
        "codigo": "uniao_estavel",
        "descricao": "União estável",
    },
    # Tipo de imóvel
    {"tipo": "tipo_imovel", "codigo": "casa", "descricao": "Casa"},
    {"tipo": "tipo_imovel", "codigo": "apartamento", "descricao": "Apartamento"},
    {"tipo": "tipo_imovel", "codigo": "sobrado", "descricao": "Sobrado"},
    {"tipo": "tipo_imovel", "codigo": "galpao", "descricao": "Galpão"},
    # Tipo de construção
    {"tipo": "tipo_construcao", "codigo": "alvenaria", "descricao": "Alvenaria"},
    {"tipo": "tipo_construcao", "codigo": "madeira", "descricao": "Madeira"},
    {"tipo": "tipo_construcao", "codigo": "mista", "descricao": "Mista"},
    # Plano de pagamento
    {"tipo": "plano_pagamento", "codigo": "AVISTA", "descricao": "À vista"},
    {"tipo": "plano_pagamento", "codigo": "2X", "descricao": "2× sem juros"},
    {"tipo": "plano_pagamento", "codigo": "3X", "descricao": "3× sem juros"},
    {"tipo": "plano_pagamento", "codigo": "4X", "descricao": "4× sem juros"},
    {"tipo": "plano_pagamento", "codigo": "6X", "descricao": "6× sem juros"},
    {"tipo": "plano_pagamento", "codigo": "10X", "descricao": "10× sem juros"},
    {"tipo": "plano_pagamento", "codigo": "12X", "descricao": "12× sem juros"},
    # Coberturas — auto
    {
        "tipo": "cobertura_auto",
        "codigo": "CASCO",
        "descricao": "Casco (colisão, capotamento, incêndio)",
    },
    {
        "tipo": "cobertura_auto",
        "codigo": "RCF",
        "descricao": "Responsabilidade civil facultativa",
    },
    {
        "tipo": "cobertura_auto",
        "codigo": "APP",
        "descricao": "Acidentes pessoais de passageiros",
    },
    {
        "tipo": "cobertura_auto",
        "codigo": "VIDROS",
        "descricao": "Vidros, faróis e retrovisores",
    },
    # Coberturas — residência
    {
        "tipo": "cobertura_residencia",
        "codigo": "INCENDIO",
        "descricao": "Incêndio e explosão",
    },
    {
        "tipo": "cobertura_residencia",
        "codigo": "ROUBO",
        "descricao": "Roubo e furto qualificado",
    },
    {
        "tipo": "cobertura_residencia",
        "codigo": "RESP_CIVIL",
        "descricao": "Responsabilidade civil",
    },
    {
        "tipo": "cobertura_residencia",
        "codigo": "DANOS_ELET",
        "descricao": "Danos elétricos",
    },
    {
        "tipo": "cobertura_residencia",
        "codigo": "QUEBRA_VIDROS",
        "descricao": "Quebra de vidros",
    },
    # Franquias
    {"tipo": "franquia", "codigo": "REDUZIDA", "descricao": "Franquia reduzida"},
    {"tipo": "franquia", "codigo": "NORMAL", "descricao": "Franquia normal"},
    {"tipo": "franquia", "codigo": "MAJORADA", "descricao": "Franquia majorada"},
    # Finalidade do veículo
    {
        "tipo": "finalidade_veiculo",
        "codigo": "lazer",
        "descricao": "Lazer e trabalho próprio",
    },
    {
        "tipo": "finalidade_veiculo",
        "codigo": "comercial",
        "descricao": "Uso comercial / transporte de carga",
    },
    {
        "tipo": "finalidade_veiculo",
        "codigo": "transporte_app",
        "descricao": "Transporte por aplicativo",
    },
    # Profissão (amostra plausível)
    {"tipo": "profissao", "codigo": "autonomo", "descricao": "Autônomo"},
    {"tipo": "profissao", "codigo": "assalariado", "descricao": "Assalariado"},
    {"tipo": "profissao", "codigo": "empresario", "descricao": "Empresário"},
    {"tipo": "profissao", "codigo": "aposentado", "descricao": "Aposentado"},
    {"tipo": "profissao", "codigo": "estudante", "descricao": "Estudante"},
    {
        "tipo": "profissao",
        "codigo": "servidor_publico",
        "descricao": "Servidor público",
    },
]


async def seed_if_empty(db: AsyncSession) -> None:
    """Popula a tabela dominio se estiver vazia. Idempotente."""
    result = await db.execute(select(Dominio).limit(1))
    if result.scalar_one_or_none() is not None:
        return
    for row in _SEED:
        db.add(Dominio(**row))
    await db.commit()
