"""Yelum com as mesmas regras já aplicadas à Justos: sem zero inventado.

O adapter Yelum inventava prêmio zero quando a resposta vinha sem valor e
assumia "casa" e uma construção padrão quando o risco não declarava — os
dois defeitos já corrigidos do outro lado.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
import respx
from httpx import Response

from app.adapters.base import RiscoCanonico
from app.adapters.yelum.adapter import YelumSeguradora, _payload_cotacao
from app.infra.secrets import EnvSecretProvider, set_provider
from tests.test_yelum_adapter import (
    _AUTH_URL,
    _FAKE_TOKEN,
    _QUOTE_URL,
    _RISCO_RESIDENCIA,
)


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YELUM_CLIENT_ID", "id-teste")
    monkeypatch.setenv("YELUM_CLIENT_SECRET", "segredo-teste")
    monkeypatch.setenv("YELUM_USERNAME", "usuario-teste")
    monkeypatch.setenv("YELUM_PASSWORD", "senha-teste")
    set_provider(EnvSecretProvider())
    from app.adapters.yelum import client as yelum_client

    yelum_client._invalida_cache()


def _payload(**extra: Any) -> dict[str, Any]:
    return _payload_cotacao({**_RISCO_RESIDENCIA, **extra})


async def _cotar_com(resposta: dict[str, Any]) -> Any:
    with respx.mock as r:
        r.post(_AUTH_URL).mock(
            return_value=Response(200, json={"access_token": _FAKE_TOKEN})
        )
        r.post(_QUOTE_URL).mock(return_value=Response(200, json=resposta))
        return await YelumSeguradora().cotar(
            RiscoCanonico(ramo="imovel", dados=_RISCO_RESIDENCIA)
        )


async def test_resposta_sem_premio_nao_vira_zero() -> None:
    resultado = await _cotar_com(
        {"Success": True, "BrokerProposalNumber": "YELUM-1", "Restricao": []}
    )
    assert resultado.sucesso is False
    assert resultado.premio_total is None
    assert "não informou o prêmio" in resultado.mensagens[0]


async def test_premio_ilegivel_nao_vira_zero() -> None:
    resultado = await _cotar_com(
        {
            "Success": True,
            "BrokerProposalNumber": "YELUM-1",
            "TotalPremiumValue": "sob consulta",
            "Restricao": [],
        }
    )
    assert resultado.sucesso is False
    assert resultado.premio_total is None


async def test_premio_informado_vira_decimal() -> None:
    resultado = await _cotar_com(
        {
            "Success": True,
            "BrokerProposalNumber": "YELUM-1",
            "TotalPremiumValue": 1200.5,
            "Restricao": [],
        }
    )
    assert resultado.sucesso is True
    assert resultado.premio_total == Decimal("1200.50")


@pytest.mark.parametrize("campo", ["tipo_imovel", "tipo_construcao", "valor_imovel"])
def test_caracteristica_do_risco_nao_e_presumida(campo: str) -> None:
    """Assumir casa, construção ou LMI muda o risco sem o corretor declarar."""
    dados = {k: v for k, v in _RISCO_RESIDENCIA.items() if k != campo}
    with pytest.raises(ValueError, match=campo):
        _payload_cotacao(dados)


def test_lmi_zerado_e_recusado() -> None:
    with pytest.raises(ValueError, match="valor_imovel"):
        _payload(valor_imovel="0")


def test_conteudo_ausente_continua_valendo_zero() -> None:
    dados = {k: v for k, v in _RISCO_RESIDENCIA.items() if k != "valor_conteudo"}
    assert _payload_cotacao(dados) is not None
