"""Cliente HTTP para a API Justos.

Token de autorização cacheado em memória (válido 60 min).
Todas as funções são async — usam httpx.AsyncClient.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
import jwt  # PyJWT[cryptography]

from app.infra.secrets import get_optional_secret, get_secret

_BASE_PROD = "https://api.justos.com.br"
_BASE_STAGING = "https://api.staging.justos.com.br"

# Margem de 90 s antes da expiração para renovar o token proativamente
_MARGEM_RENOVACAO = 90.0


@dataclass
class _TokenCache:
    token: str = ""
    expira_em: float = field(default=0.0)


_cache = _TokenCache()


def _invalida_cache() -> None:
    """Zera o cache de token (uso exclusivo em testes)."""
    _cache.token = ""
    _cache.expira_em = 0.0


def _base_url() -> str:
    env = get_optional_secret("JUSTOS_ENV", "staging")
    return _BASE_PROD if env == "production" else _BASE_STAGING


def _gerar_jwt() -> str:
    raw_pem = get_secret("JUSTOS_PRIVATE_KEY")
    # Suporta chave com \\n escapado (comum em variáveis de ambiente)
    private_key_pem = raw_pem.replace("\\n", "\n")
    partner_name = get_secret("JUSTOS_PARTNER_NAME")
    now = int(time.time())
    payload: dict[str, object] = {
        "iss": partner_name,
        "aud": "justos",
        "iat": now,
        "exp": now + 600,
    }
    return str(jwt.encode(payload, private_key_pem, algorithm="ES256"))


async def _obter_token() -> str:
    """Retorna token de autorização Justos, renovando se necessário."""
    now = time.monotonic()
    if _cache.token and _cache.expira_em > now + _MARGEM_RENOVACAO:
        return _cache.token

    jwt_token = _gerar_jwt()
    broker_id = int(get_secret("JUSTOS_BROKER_ID"))
    cpf_cnpj = get_secret("JUSTOS_CPF_CNPJ")

    async with httpx.AsyncClient() as c:
        resp = await c.post(
            f"{_base_url()}/brokers/auth/api-token",
            json={"token": jwt_token, "brokerId": broker_id, "cpf_cnpj": cpf_cnpj},
            timeout=30.0,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

    token_str = str(data["token"])
    # Lê o exp do próprio JWT retornado — mais robusto que hardcode de 60 min
    try:
        decoded = jwt.decode(token_str, options={"verify_signature": False})
        exp_unix = int(decoded["exp"])
        # Converte wall-clock → monotonic para comparação consistente
        _cache.expira_em = now + (exp_unix - time.time())
    except Exception:
        _cache.expira_em = now + 3600.0
    _cache.token = token_str
    return _cache.token


async def criar_cotacao(payload: dict[str, Any]) -> dict[str, Any]:
    """POST /brokers/quote — cria cotação e retorna coberturas disponíveis."""
    token = await _obter_token()
    async with httpx.AsyncClient() as c:
        resp = await c.post(
            f"{_base_url()}/brokers/quote",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
        )
        resp.raise_for_status()
        return dict(resp.json())


async def calcular_preco(
    quote_id: str, coverages_selected: dict[str, Any]
) -> dict[str, Any]:
    """POST /brokers/quote/{id}/pricing — simula preço (read-only, repetível)."""
    token = await _obter_token()
    async with httpx.AsyncClient() as c:
        resp = await c.post(
            f"{_base_url()}/brokers/quote/{quote_id}/pricing",
            json={"coverages_selected": coverages_selected},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
        )
        resp.raise_for_status()
        return dict(resp.json())


async def selecionar_coberturas(
    quote_id: str,
    coverages_selected: dict[str, Any],
    policy_type: str = "monthly",
) -> None:
    """PUT /brokers/quote/{id}/coverages — persiste a cobertura escolhida."""
    token = await _obter_token()
    async with httpx.AsyncClient() as c:
        resp = await c.put(
            f"{_base_url()}/brokers/quote/{quote_id}/coverages",
            json={"coverages_selected": coverages_selected, "policy_type": policy_type},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
        )
        resp.raise_for_status()


async def converter_proposta(
    quote_uuid: str,
    email: str,
    telefone: str,
    policy_type: str = "monthly",
    installments: int | None = None,
    scheduling_date: str | None = None,
    ci_code: str | None = None,
) -> dict[str, Any]:
    """POST /brokers/quote/convert-formal-quote — formaliza proposta."""
    token = await _obter_token()
    body: dict[str, Any] = {
        "quote_uuid": quote_uuid,
        "email": email,
        "given_phone_number": telefone,
        "scheduling_date": scheduling_date,
        "policy_type": policy_type,
    }
    if installments is not None:
        body["installments"] = installments
    if ci_code is not None:
        body["ci_code"] = ci_code
    async with httpx.AsyncClient() as c:
        resp = await c.post(
            f"{_base_url()}/brokers/quote/convert-formal-quote",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
        )
        resp.raise_for_status()
        return dict(resp.json())


async def obter_checkout_link(quote_id: str) -> dict[str, Any]:
    """GET /brokers/quote/{id}/checkout-link — link para o cliente contratar."""
    token = await _obter_token()
    async with httpx.AsyncClient() as c:
        resp = await c.get(
            f"{_base_url()}/brokers/quote/{quote_id}/checkout-link",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return dict(resp.json())


async def exportar_apolices(
    updated_since: datetime,
    skip: int = 0,
    take: int = 100,
) -> dict[str, Any]:
    """GET /brokers/policy/export — apólices vendidas desde `updated_since`."""
    token = await _obter_token()
    params: dict[str, str | int] = {
        "updatedSince": updated_since.isoformat(),
        "skip": skip,
        "take": take,
    }
    async with httpx.AsyncClient() as c:
        resp = await c.get(
            f"{_base_url()}/brokers/policy/export",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
        )
        resp.raise_for_status()
        return dict(resp.json())
