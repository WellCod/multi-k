"""Testes unitários do adapter Justos.

Usa respx para mockar as chamadas HTTP — nenhuma rede real é acessada.

Fluxos cobertos:
  - cotar() com dados planos → sucesso
  - cotar() com proponente aninhado (formato real do frontend)
  - cotar() ramo não suportado → sucesso=False sem chamada HTTP
  - transmitir() sem ci_code → body sem ci_code
  - transmitir() com ci_code → body inclui ci_code (renovação)
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.adapters.base import PropostaCanonica, RiscoCanonico
from app.adapters.justos.adapter import JustosSeguradora
from app.infra.secrets import EnvSecretProvider, set_provider

_BASE = "https://api.staging.justos.com.br"
_AUTH_URL = f"{_BASE}/brokers/auth/api-token"
_QUOTE_URL = f"{_BASE}/brokers/quote"
_PRICING_URL = f"{_BASE}/brokers/quote/Q-001/pricing"
_COVERAGES_URL = f"{_BASE}/brokers/quote/Q-001/coverages"
_CONVERT_URL = f"{_BASE}/brokers/quote/convert-formal-quote"
_CHECKOUT_URL = f"{_BASE}/brokers/quote/Q-001/checkout-link"

_FAKE_TOKEN = "apitoken123"

_TEST_EC_KEY = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgYqQQSZA0evZwbYt+\n"
    "9jewzOhw0/IQm01U6mKufI1vo2OhRANCAAQt5Sb19Sv1EeFXd0/9nS9f2saBhQE0\n"
    "kqQklcBPMV06ju1TZVaKL+6T9piYvnKWMgGkxYdalAOOnuA98qtllZXI\n"
    "-----END PRIVATE KEY-----\n"
)

_RESP_AUTH = {"token": _FAKE_TOKEN}

_RESP_COTACAO = {
    "quote_id": "Q-001",
    "coverages_available": {
        "colisao-e-desastres-naturais": {
            "mandatory": True,
            "peril_options": [
                {"slug": "colisao-franquia-20", "price": 80.0},
                {"slug": "colisao-franquia-10", "price": 100.0},
            ],
        }
    },
    "fipe_price_percentage_covered": 100,
    "commission": 15,
    "plans": [],
    "coverages_selected": {},
}

_RESP_PRICING = {
    "monthly": {"total": 250.0},
    "annual": {"total": 2800.0},
    "info": "Desconto de 5% para pagamento anual.",
}

_RESP_CHECKOUT = {"checkout_url": "https://app.justos.com.br/checkout/Q-001"}

_RISCO_AUTO_PLANO: dict[str, object] = {
    "cpf": "12345678901",
    "nome": "João Silva",
    "sexo": "M",
    "data_nascimento": "1990-05-10",
    "cep_pernoite": "01310100",
    "codigo_fipe": "023108-8",
    "ano_modelo": "2022",
}

_RISCO_AUTO_ANINHADO: dict[str, object] = {
    "proponente": {
        "cpf": "12345678901",
        "nome": "João Silva",
        "sexo": "M",
        "data_nascimento": "1990-05-10",
        "telefone": "11999990000",
    },
    "cep_pernoite": "01310100",
    "codigo_fipe": "023108-8",
    "ano_modelo": "2022",
}


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


def _mock_auth(router: respx.MockRouter) -> None:
    router.post(_AUTH_URL).mock(return_value=Response(200, json=_RESP_AUTH))


def _mock_cotar(router: respx.MockRouter) -> None:
    router.post(_QUOTE_URL).mock(return_value=Response(200, json=_RESP_COTACAO))
    router.post(_PRICING_URL).mock(return_value=Response(200, json=_RESP_PRICING))


async def test_cotar_sucesso() -> None:
    with respx.mock as r:
        _mock_auth(r)
        _mock_cotar(r)

        resultado = await JustosSeguradora().cotar(
            RiscoCanonico(ramo="auto", dados=_RISCO_AUTO_PLANO)
        )

    assert resultado.sucesso is True
    assert resultado.cotacao_id == "Q-001"
    assert resultado.premio_total is not None
    assert resultado.mensagens == ["Desconto de 5% para pagamento anual."]
    assert resultado.payload_resposta is not None
    assert resultado.payload_resposta["fipe_price_percentage_covered"] == 100
    assert resultado.payload_resposta["commission"] == 15
    assert resultado.payload_resposta["plans"] == []


async def test_cotar_proponente_aninhado() -> None:
    """Aceita proponente aninhado (formato real do frontend)."""
    with respx.mock as r:
        _mock_auth(r)
        _mock_cotar(r)

        resultado = await JustosSeguradora().cotar(
            RiscoCanonico(ramo="auto", dados=_RISCO_AUTO_ANINHADO)
        )

    assert resultado.sucesso is True
    assert resultado.cotacao_id == "Q-001"


async def test_cotar_ramo_nao_suportado() -> None:
    with respx.mock:
        resultado = await JustosSeguradora().cotar(
            RiscoCanonico(ramo="imovel", dados={"cep": "01310100"})
        )

    assert resultado.sucesso is False
    assert "imovel" in resultado.mensagens[0]


async def test_transmitir_sem_ci_code() -> None:
    captured: list[dict] = []

    with respx.mock as r:
        _mock_auth(r)
        r.put(_COVERAGES_URL).mock(return_value=Response(200, json={}))

        def _capture_convert(request: respx.patterns.M) -> Response:  # type: ignore[name-defined]
            import json

            captured.append(json.loads(request.content))
            return Response(200, json={})

        r.post(_CONVERT_URL).mock(side_effect=_capture_convert)
        r.get(_CHECKOUT_URL).mock(return_value=Response(200, json=_RESP_CHECKOUT))

        await JustosSeguradora().transmitir(
            PropostaCanonica(
                cotacao_id="Q-001",
                risco=RiscoCanonico(ramo="auto", dados=_RISCO_AUTO_PLANO),
                dados_negocio={
                    "email": "joao@test.com",
                    "telefone": "11999990000",
                    "coverages_selected": {
                        "colisao-e-desastres-naturais": "colisao-franquia-20"
                    },
                },
            )
        )

    assert len(captured) == 1
    assert "ci_code" not in captured[0]


async def test_transmitir_email_de_risco_dados() -> None:
    """email/telefone lidos de risco.dados.proponente quando ausentes de dados_negocio."""  # noqa: E501
    captured: list[dict] = []

    with respx.mock as r:
        _mock_auth(r)
        r.put(_COVERAGES_URL).mock(return_value=Response(200, json={}))

        def _cap(request: respx.patterns.M) -> Response:  # type: ignore[name-defined]
            import json

            captured.append(json.loads(request.content))
            return Response(200, json={})

        r.post(_CONVERT_URL).mock(side_effect=_cap)
        r.get(_CHECKOUT_URL).mock(return_value=Response(200, json=_RESP_CHECKOUT))

        await JustosSeguradora().transmitir(
            PropostaCanonica(
                cotacao_id="Q-001",
                risco=RiscoCanonico(ramo="auto", dados=_RISCO_AUTO_ANINHADO),
                dados_negocio={
                    "coverages_selected": {
                        "colisao-e-desastres-naturais": "colisao-franquia-20"
                    }
                },
            )
        )

    assert len(captured) == 1
    assert captured[0]["email"] == ""
    assert captured[0]["given_phone_number"] == "11999990000"


async def test_transmitir_com_ci_code() -> None:
    """ci_code obrigatório em renovações deve ser enviado ao converter_proposta."""
    captured: list[dict] = []

    with respx.mock as r:
        _mock_auth(r)
        r.put(_COVERAGES_URL).mock(return_value=Response(200, json={}))

        def _capture_convert(request: respx.patterns.M) -> Response:  # type: ignore[name-defined]
            import json

            captured.append(json.loads(request.content))
            return Response(200, json={})

        r.post(_CONVERT_URL).mock(side_effect=_capture_convert)
        r.get(_CHECKOUT_URL).mock(return_value=Response(200, json=_RESP_CHECKOUT))

        await JustosSeguradora().transmitir(
            PropostaCanonica(
                cotacao_id="Q-001",
                risco=RiscoCanonico(ramo="auto", dados=_RISCO_AUTO_PLANO),
                dados_negocio={
                    "email": "joao@test.com",
                    "telefone": "11999990000",
                    "coverages_selected": {
                        "colisao-e-desastres-naturais": "colisao-franquia-20"
                    },
                    "ci_code": "CI-2025-999",
                },
            )
        )

    assert len(captured) == 1
    assert captured[0]["ci_code"] == "CI-2025-999"
