"""Autenticação Justos (J1/J2 §3): claims do JWT, cache e origem da chave."""

from __future__ import annotations

import json
import time
from typing import Any

import jwt
import pytest
import respx
from httpx import Response

from app.adapters.justos import client
from app.infra.secrets import EnvSecretProvider, set_provider

_AUTH_URL = "https://api.staging.justos.com.br/brokers/auth/api-token"

# Só assina o token devolvido pelo mock; nunca sai daqui.
_SEGREDO_SINTETICO = "segredo-sintetico-apenas-para-teste-32b"

_TEST_EC_KEY = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgYqQQSZA0evZwbYt+\n"
    "9jewzOhw0/IQm01U6mKufI1vo2OhRANCAAQt5Sb19Sv1EeFXd0/9nS9f2saBhQE0\n"
    "kqQklcBPMV06ju1TZVaKL+6T9piYvnKWMgGkxYdalAOOnuA98qtllZXI\n"
    "-----END PRIVATE KEY-----\n"
)


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTOS_PARTNER_NAME", "test_partner")
    monkeypatch.setenv("JUSTOS_BROKER_ID", "7")
    monkeypatch.setenv("JUSTOS_CPF_CNPJ", "00000000000")
    monkeypatch.setenv("JUSTOS_PRIVATE_KEY", _TEST_EC_KEY)
    monkeypatch.setenv("JUSTOS_ENV", "staging")
    monkeypatch.delenv("JUSTOS_PRIVATE_KEY_PATH", raising=False)
    set_provider(EnvSecretProvider())
    client._invalida_cache()


def _token_remoto(expira_em: float | None) -> str:
    conteudo: dict[str, Any] = {"sub": "corretora"}
    if expira_em is not None:
        conteudo["exp"] = int(expira_em)
    return jwt.encode(conteudo, _SEGREDO_SINTETICO, algorithm="HS256")


async def test_claims_e_identificacao_da_corretora() -> None:
    capturado: list[dict[str, Any]] = []

    with respx.mock as r:

        def _responder(request: Any) -> Response:
            capturado.append(json.loads(request.content))
            return Response(200, json={"token": _token_remoto(time.time() + 3600)})

        r.post(_AUTH_URL).mock(side_effect=_responder)
        await client._obter_token()

    corpo = capturado[0]
    assert corpo["brokerId"] == 7
    assert corpo["cpf_cnpj"] == "00000000000"
    claims = jwt.decode(corpo["token"], options={"verify_signature": False})
    assert claims["iss"] == "test_partner"
    assert claims["aud"] == "justos"
    assert claims["exp"] - claims["iat"] == 600


async def test_token_valido_e_reaproveitado_sem_nova_chamada() -> None:
    with respx.mock as r:
        rota = r.post(_AUTH_URL).mock(
            return_value=Response(
                200, json={"token": _token_remoto(time.time() + 3600)}
            )
        )
        primeiro = await client._obter_token()
        segundo = await client._obter_token()

    assert primeiro == segundo
    assert rota.call_count == 1


async def test_token_proximo_do_fim_e_renovado() -> None:
    with respx.mock as r:
        rota = r.post(_AUTH_URL).mock(
            side_effect=[
                Response(200, json={"token": _token_remoto(time.time() + 30)}),
                Response(200, json={"token": _token_remoto(time.time() + 3600)}),
            ]
        )
        await client._obter_token()
        await client._obter_token()

    assert rota.call_count == 2


async def test_expiracao_ilegivel_nao_invalida_o_token() -> None:
    """Sem exp legível, vale a janela padrão de 60 min em vez de renovar sempre."""
    with respx.mock as r:
        rota = r.post(_AUTH_URL).mock(
            return_value=Response(200, json={"token": _token_remoto(None)})
        )
        await client._obter_token()
        await client._obter_token()

    assert rota.call_count == 1


async def test_chave_pode_vir_de_arquivo_fora_do_repositorio(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    arquivo = tmp_path / "justos-ec.pem"
    arquivo.write_text(_TEST_EC_KEY)
    monkeypatch.delenv("JUSTOS_PRIVATE_KEY", raising=False)
    monkeypatch.setenv("JUSTOS_PRIVATE_KEY_PATH", str(arquivo))

    capturado: list[dict[str, Any]] = []

    with respx.mock as r:

        def _responder(request: Any) -> Response:
            capturado.append(json.loads(request.content))
            return Response(200, json={"token": _token_remoto(time.time() + 3600)})

        r.post(_AUTH_URL).mock(side_effect=_responder)
        await client._obter_token()

    claims = jwt.decode(capturado[0]["token"], options={"verify_signature": False})
    assert claims["iss"] == "test_partner"
