"""Renovação é declarada e exige CI — bônus não substitui a declaração."""

import pytest

from app.adapters.base import PropostaCanonica, RiscoCanonico
from app.adapters.justos.adapter import JustosSeguradora, _tipo_negocio


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


def test_ausencia_de_declaracao_e_negocio_novo() -> None:
    assert _tipo_negocio({}) == "novo"


def test_bonus_alto_nao_transforma_em_renovacao() -> None:
    assert _tipo_negocio({"bonus_anterior": 10}) == "novo"


def test_tipo_desconhecido_nao_vira_novo_silenciosamente() -> None:
    with pytest.raises(ValueError, match="tipo_negocio inválido"):
        _tipo_negocio({"tipo_negocio": "endosso"})


async def test_renovacao_sem_ci_nao_transmite() -> None:
    resultado = await JustosSeguradora().transmitir(
        _proposta({"tipo_negocio": "renovacao"}, {})
    )
    assert resultado.sucesso is False
    assert resultado.protocolo is None
    assert "código CI" in resultado.mensagens[0]


async def test_tipo_invalido_no_risco_bloqueia_transmissao() -> None:
    resultado = await JustosSeguradora().transmitir(
        _proposta({"tipo_negocio": "endosso"}, {"ci_code": "CI-1"})
    )
    assert resultado.sucesso is False
    assert "tipo_negocio inválido" in resultado.mensagens[0]
