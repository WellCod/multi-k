"""Bônus, CI e comissão conforme a Justos confirmou em 17/09/2026.

O gatilho do ci_code é a classe de bônus, não a natureza do negócio: bônus
transferido em negócio novo também exige o código. E a comissão que vale é a
devolvida pela seguradora, que aplica piso próprio em renovação de apólice
dela e responde com percentual diferente do enviado.
"""

from decimal import Decimal

import pytest

from app.adapters.base import PropostaCanonica, RiscoCanonico
from app.adapters.justos.adapter import (
    JustosSeguradora,
    _bonus_anterior,
    _comissao_confirmada,
    _tipo_negocio,
)


def _proposta(risco: dict[str, object], negocio: dict[str, object]) -> PropostaCanonica:
    return PropostaCanonica(
        cotacao_id="Q-001",
        risco=RiscoCanonico(ramo="auto", dados=risco),
        dados_negocio={
            "email": "cliente@test.com",
            "telefone": "11999999999",
            "coverages_selected": {"colisao": "opcao"},
            **negocio,
        },
    )


# ---------------------------------------------------------------------------
# Natureza do negócio — segue declarada, nunca inferida
# ---------------------------------------------------------------------------


def test_ausencia_de_declaracao_e_negocio_novo() -> None:
    assert _tipo_negocio({}) == "novo"


def test_bonus_alto_nao_transforma_em_renovacao() -> None:
    assert _tipo_negocio({"bonus_anterior": 10}) == "novo"


def test_tipo_desconhecido_nao_vira_novo_silenciosamente() -> None:
    with pytest.raises(ValueError, match="tipo_negocio inválido"):
        _tipo_negocio({"tipo_negocio": "endosso"})


# ---------------------------------------------------------------------------
# Classe de bônus
# ---------------------------------------------------------------------------


def test_bonus_ausente_e_zero() -> None:
    assert _bonus_anterior({}) == 0
    assert _bonus_anterior({"bonus_anterior": ""}) == 0


def test_bonus_declarado_e_lido() -> None:
    assert _bonus_anterior({"bonus_anterior": "7"}) == 7


@pytest.mark.parametrize("bruto", ["onze", "11", "-1"])
def test_bonus_invalido_nao_vira_zero(bruto: str) -> None:
    with pytest.raises(ValueError, match="bonus_anterior"):
        _bonus_anterior({"bonus_anterior": bruto})


# ---------------------------------------------------------------------------
# CI da apólice anterior — exigido pelo bônus
# ---------------------------------------------------------------------------


async def test_bonus_maior_que_zero_sem_ci_nao_transmite() -> None:
    resultado = await JustosSeguradora().transmitir(
        _proposta({"bonus_anterior": 5}, {})
    )
    assert resultado.sucesso is False
    assert "código CI" in resultado.mensagens[0]


async def test_negocio_novo_com_bonus_transferido_tambem_exige_ci() -> None:
    """A regra é o bônus: negócio novo com bônus herdado precisa do CI."""
    resultado = await JustosSeguradora().transmitir(
        _proposta({"tipo_negocio": "novo", "bonus_anterior": 3}, {})
    )
    assert resultado.sucesso is False
    assert "código CI" in resultado.mensagens[0]


async def test_bonus_invalido_bloqueia_antes_da_chamada() -> None:
    resultado = await JustosSeguradora().transmitir(
        _proposta({"bonus_anterior": "onze"}, {"ci_code": "CI-1"})
    )
    assert resultado.sucesso is False
    assert "bonus_anterior" in resultado.mensagens[0]


async def test_tipo_invalido_no_risco_bloqueia_transmissao() -> None:
    resultado = await JustosSeguradora().transmitir(
        _proposta({"tipo_negocio": "endosso"}, {"ci_code": "CI-1"})
    )
    assert resultado.sucesso is False
    assert "tipo_negocio inválido" in resultado.mensagens[0]


# ---------------------------------------------------------------------------
# Comissão — vale a devolvida
# ---------------------------------------------------------------------------


def test_comissao_devolvida_prevalece_sobre_a_enviada() -> None:
    """Piso da Justos em renovação de apólice dela chega na resposta."""
    confirmada = _comissao_confirmada(
        {"commission": 15}, {"broker_commission_percentage": 10}
    )
    assert confirmada == Decimal("0.15")


def test_sem_comissao_na_resposta_vale_a_enviada() -> None:
    confirmada = _comissao_confirmada({}, {"broker_commission_percentage": 20})
    assert confirmada == Decimal("0.20")


@pytest.mark.parametrize("bruto", [None, "", "quinze", -1])
def test_comissao_ilegivel_na_resposta_cai_para_a_enviada(bruto: object) -> None:
    confirmada = _comissao_confirmada(
        {"commission": bruto}, {"broker_commission_percentage": 12}
    )
    assert confirmada == Decimal("0.12")
