"""Testes unitários do adapter Yelum.

Usa respx para mockar as chamadas HTTP — nenhuma rede real é acessada.
Os secrets Yelum são fornecidos via DummyProvider injetado no conftest-local.

Fluxos cobertos:
  - cotar() sucesso → ResultadoCotacao com prêmio e BrokerProposalNumber
  - cotar() com NeedInspectionRisk=True → necessita_vistoria=True
  - cotar() falha de negócio (Success=false) → sucesso=False
  - cotar() ramo não suportado → sucesso=False sem chamada HTTP
  - cotar() 401 → reautentica e repete
  - recotar() delega para PUT /quote/{id}
  - transmitir() sucesso → ResultadoTransmissao com protocolo
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.adapters.base import PropostaCanonica, RiscoCanonico
from app.adapters.yelum.adapter import YelumSeguradora
from app.infra.secrets import EnvSecretProvider, set_provider

_RISCO_RESIDENCIA: dict[str, object] = {
    "cpf": "12345678901",
    "nome": "Maria Silva",
    "nascimento": "1985-03-15",
    "sexo": "F",
    "estado_civil": "2",
    "profissao": "100",
    "email": "maria@example.com",
    "telefone": "11999990000",
    "cep": "01310100",
    "tipo_imovel": "apartamento",
    "tipo_construcao": "1",
    "valor_imovel": "500000.00",
    "valor_conteudo": "50000.00",
    "alarme": True,
    "cerca_eletrica": False,
    "grades": True,
    "inicio_vigencia": "2026-09-01",
    "fim_vigencia": "2027-09-01",
    "coberturas": ["CBE10", "CBE20"],
    "comissao_pct": 20,
}

_AUTH_URL = "https://integracao-tst.grupohdiseguros.com.br/controledeacesso/token"
_QUOTE_URL = (
    "https://integracao-tst.grupohdiseguros.com.br/offer/property/sandbox/v1/quote"
)

_FAKE_TOKEN = "tokenopaco12345678901234567"

_RESP_COTACAO_SUCESSO = {
    "Success": True,
    "BrokerProposalNumber": "YELUM-2026-001",
    "TotalPremiumValue": 1200.50,
    "NeedInspectionRisk": False,
    "Restricao": [],
    "MensagemInformativa": [],
}

_RESP_COTACAO_VISTORIA = {
    "Success": True,
    "BrokerProposalNumber": "YELUM-2026-002",
    "TotalPremiumValue": 980.00,
    "NeedInspectionRisk": True,
    "Restricao": [{"Code": "R001", "Description": "Vistoria prévia obrigatória."}],
    "MensagemInformativa": ["Imóvel requer inspeção antes da emissão."],
}

_RESP_COTACAO_RECUSADA = {
    "Success": False,
    "Messages": ["Risco não aceito para este CEP."],
    "BrokerProposalNumber": None,
}

_RESP_PROPOSTA_SUCESSO = {
    "Success": True,
    "ProposalNumber": "PROP-2026-9999",
}


@pytest.fixture(autouse=True)
def _inject_yelum_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Injeta segredos Yelum fictícios para que o cliente não levante KeyError."""
    monkeypatch.setenv("YELUM_CLIENT_ID", "fake_client_id")
    monkeypatch.setenv("YELUM_CLIENT_SECRET", "fake_client_secret")
    monkeypatch.setenv("YELUM_USERNAME", "fake_user")
    monkeypatch.setenv("YELUM_PASSWORD", "fake_pass")
    monkeypatch.setenv("YELUM_ENV", "mock")
    set_provider(EnvSecretProvider())


@pytest.fixture(autouse=True)
def _reset_token_cache() -> None:
    """Zera o cache de token entre os testes."""
    from app.adapters.yelum import client as yelum_client

    yelum_client._invalida_cache()


def _mock_auth(router: respx.MockRouter) -> None:
    router.post(_AUTH_URL).mock(
        return_value=Response(200, json={"access_token": _FAKE_TOKEN})
    )


async def test_cotar_sucesso() -> None:
    with respx.mock as r:
        _mock_auth(r)
        r.post(_QUOTE_URL).mock(return_value=Response(200, json=_RESP_COTACAO_SUCESSO))

        resultado = await YelumSeguradora().cotar(
            RiscoCanonico(ramo="imovel", dados=_RISCO_RESIDENCIA)
        )

    assert resultado.sucesso is True
    assert resultado.cotacao_id == "YELUM-2026-001"
    assert resultado.premio_total is not None
    assert resultado.premio_total == pytest.approx(1200.50, abs=0.01)  # type: ignore[arg-type]
    assert resultado.necessita_vistoria is False
    assert resultado.restricoes == []


async def test_cotar_necessita_vistoria() -> None:
    with respx.mock as r:
        _mock_auth(r)
        r.post(_QUOTE_URL).mock(return_value=Response(200, json=_RESP_COTACAO_VISTORIA))

        resultado = await YelumSeguradora().cotar(
            RiscoCanonico(ramo="imovel", dados=_RISCO_RESIDENCIA)
        )

    assert resultado.sucesso is True
    assert resultado.necessita_vistoria is True
    assert len(resultado.restricoes) == 1
    assert resultado.restricoes[0].codigo == "R001"
    assert len(resultado.mensagens) == 1


async def test_cotar_recusada() -> None:
    with respx.mock as r:
        _mock_auth(r)
        r.post(_QUOTE_URL).mock(return_value=Response(200, json=_RESP_COTACAO_RECUSADA))

        resultado = await YelumSeguradora().cotar(
            RiscoCanonico(ramo="imovel", dados=_RISCO_RESIDENCIA)
        )

    assert resultado.sucesso is False
    assert "não aceito" in resultado.mensagens[0]


async def test_cotar_ramo_nao_suportado() -> None:
    with respx.mock:
        resultado = await YelumSeguradora().cotar(
            RiscoCanonico(ramo="auto", dados={"cep_pernoite": "01310100"})
        )

    assert resultado.sucesso is False
    assert "auto" in resultado.mensagens[0]


async def test_cotar_retry_em_401() -> None:
    """401 na primeira chamada deve reautenticar e repetir."""
    calls: list[int] = []

    with respx.mock as r:
        r.post(_AUTH_URL).mock(
            return_value=Response(200, json={"access_token": _FAKE_TOKEN})
        )

        def _quote_side_effect(request: respx.patterns.M) -> Response:  # type: ignore[name-defined]
            calls.append(1)
            if len(calls) == 1:
                return Response(401, json={"error": "unauthorized"})
            return Response(200, json=_RESP_COTACAO_SUCESSO)

        r.post(_QUOTE_URL).mock(side_effect=_quote_side_effect)

        resultado = await YelumSeguradora().cotar(
            RiscoCanonico(ramo="imovel", dados=_RISCO_RESIDENCIA)
        )

    assert resultado.sucesso is True
    assert len(calls) == 2


async def test_recotar_usa_put() -> None:
    _recotar_url = (
        "https://integracao-tst.grupohdiseguros.com.br"
        "/offer/property/sandbox/v1/quote/YELUM-2026-001"
    )
    with respx.mock as r:
        _mock_auth(r)
        r.put(_recotar_url).mock(return_value=Response(200, json=_RESP_COTACAO_SUCESSO))

        resultado = await YelumSeguradora().recotar(
            "YELUM-2026-001",
            RiscoCanonico(ramo="imovel", dados=_RISCO_RESIDENCIA),
        )

    assert resultado.sucesso is True
    assert resultado.cotacao_id == "YELUM-2026-001"


async def test_transmitir_sucesso() -> None:
    _proposta_url = (
        "https://integracao-tst.grupohdiseguros.com.br"
        "/offer/property/sandbox/v1/proposal"
    )
    with respx.mock as r:
        _mock_auth(r)
        r.post(_proposta_url).mock(
            return_value=Response(200, json=_RESP_PROPOSTA_SUCESSO)
        )

        resultado = await YelumSeguradora().transmitir(
            PropostaCanonica(
                cotacao_id="YELUM-2026-001",
                risco=RiscoCanonico(ramo="imovel", dados=_RISCO_RESIDENCIA),
                dados_negocio={
                    "BrokerCode": "001",
                    "BrokerBranchCode": "01",
                    "broker_proposal_number": "YELUM-2026-001",
                    "CommissionPct": 20,
                },
            )
        )

    assert resultado.sucesso is True
    assert resultado.protocolo == "PROP-2026-9999"
