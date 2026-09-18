"""Exportação de apólices vendidas (J3 §4) — paginação e conversão canônica.

Os testes fixam o comportamento atual. Duas ressalvas seguem abertas na
auditoria e por isso não são afirmadas como corretas aqui: a causa do
encerramento derivada de ACTIVE/INACTIVE e o resultado parcial devolvido
quando uma página falha.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
import respx
from httpx import Response

from app.adapters.justos.adapter import JustosSeguradora
from app.infra.secrets import EnvSecretProvider, set_provider
from tests.conftest import CHAVE_EC_TESTE as _TEST_EC_KEY

_BASE = "https://api.staging.justos.com.br"
_AUTH_URL = f"{_BASE}/brokers/auth/api-token"
_EXPORT_URL = f"{_BASE}/brokers/policy/export"


_DESDE = date(2026, 9, 1)


@pytest.fixture(autouse=True)
def _inject_justos_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTOS_PARTNER_NAME", "test_partner")
    monkeypatch.setenv("JUSTOS_BROKER_ID", "1")
    monkeypatch.setenv("JUSTOS_CPF_CNPJ", "00000000000")
    monkeypatch.setenv("JUSTOS_PRIVATE_KEY", _TEST_EC_KEY)
    monkeypatch.setenv("JUSTOS_ENV", "staging")
    set_provider(EnvSecretProvider())


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    from app.adapters.justos import client as justos_client

    justos_client._invalida_cache()


def _apolice(**extra: Any) -> dict[str, Any]:
    return {
        "policyId": "POL-1",
        "status": "ACTIVE",
        "updatedAt": "2026-09-10T12:00:00Z",
        "policyType": "monthly",
        "validFrom": "2026-09-10",
        "validUntil": "2026-10-10",
        "insurerPolicyNumber": "AP-9",
        "commission": {"percentage": 15},
        "vehicle": {"plate": "FHL4853"},
        "premium": {"totalPremium": "250.5"},
        **extra,
    }


async def test_converte_apolice_para_movimento_canonico() -> None:
    with respx.mock as r:
        r.post(_AUTH_URL).mock(return_value=Response(200, json={"token": "t"}))
        r.get(_EXPORT_URL).mock(return_value=Response(200, json={"data": [_apolice()]}))
        movimentos = await JustosSeguradora().movimentos(_DESDE)

    assert len(movimentos) == 1
    movimento = movimentos[0]
    assert movimento.id_movimento == "POL-1"
    assert movimento.data == date(2026, 9, 10)
    assert movimento.valor == Decimal("250.50")
    assert movimento.dados["insurer_policy_number"] == "AP-9"
    assert movimento.dados["vehicle"] == {"plate": "FHL4853"}


async def test_estado_da_apolice_e_preservado_sem_reinterpretacao() -> None:
    """J3 §4.3: o estado bruto tem de chegar ao domínio como veio."""
    with respx.mock as r:
        r.post(_AUTH_URL).mock(return_value=Response(200, json={"token": "t"}))
        r.get(_EXPORT_URL).mock(
            return_value=Response(200, json={"data": [_apolice(status="INACTIVE")]})
        )
        movimentos = await JustosSeguradora().movimentos(_DESDE)

    assert movimentos[0].dados["status"] == "INACTIVE"


async def test_apolice_sem_identificador_e_descartada() -> None:
    with respx.mock as r:
        r.post(_AUTH_URL).mock(return_value=Response(200, json={"token": "t"}))
        r.get(_EXPORT_URL).mock(
            return_value=Response(200, json={"data": [_apolice(policyId="")]})
        )
        assert await JustosSeguradora().movimentos(_DESDE) == []


async def test_data_ilegivel_cai_para_o_inicio_da_janela() -> None:
    with respx.mock as r:
        r.post(_AUTH_URL).mock(return_value=Response(200, json={"token": "t"}))
        r.get(_EXPORT_URL).mock(
            return_value=Response(200, json={"data": [_apolice(updatedAt="ontem")]})
        )
        assert (await JustosSeguradora().movimentos(_DESDE))[0].data == _DESDE


async def test_premio_ausente_nao_vira_zero() -> None:
    with respx.mock as r:
        r.post(_AUTH_URL).mock(return_value=Response(200, json={"token": "t"}))
        r.get(_EXPORT_URL).mock(
            return_value=Response(200, json={"data": [_apolice(premium={})]})
        )
        assert (await JustosSeguradora().movimentos(_DESDE))[0].valor is None


async def test_pagina_cheia_pede_a_proxima(monkeypatch: pytest.MonkeyPatch) -> None:
    """take=100: página cheia continua a paginação, página curta encerra."""
    paginas = [
        {"data": [_apolice(policyId=f"POL-{i}") for i in range(100)]},
        {"data": [_apolice(policyId="POL-ultima")]},
    ]
    chamadas: list[dict[str, Any]] = []

    with respx.mock as r:
        r.post(_AUTH_URL).mock(return_value=Response(200, json={"token": "t"}))

        def _responder(request: Any) -> Response:
            chamadas.append(dict(request.url.params))
            return Response(200, json=paginas[len(chamadas) - 1])

        r.get(_EXPORT_URL).mock(side_effect=_responder)
        movimentos = await JustosSeguradora().movimentos(_DESDE)

    assert [c["skip"] for c in chamadas] == ["0", "100"]
    assert chamadas[0]["take"] == "100"
    assert chamadas[0]["updatedSince"].startswith("2026-09-01T00:00:00")
    assert len(movimentos) == 101


async def test_falha_de_pagina_encerra_o_laco_com_o_parcial() -> None:
    """Ressalva aberta na auditoria: o parcial não se distingue do completo."""
    respostas = [
        Response(200, json={"data": [_apolice() for _ in range(100)]}),
        Response(500, json={}),
    ]

    with respx.mock as r:
        r.post(_AUTH_URL).mock(return_value=Response(200, json={"token": "t"}))
        r.get(_EXPORT_URL).mock(side_effect=respostas)
        movimentos = await JustosSeguradora().movimentos(_DESDE)

    assert len(movimentos) == 100
