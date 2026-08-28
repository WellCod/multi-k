"""Cliente HTTP para a API Yelum (Grupo HDI Seguros).

Token de acesso opaco (~28 chars) — sem JWT, sem campo expires_in confirmado.
Estratégia: cache em memória com TTL fixo de 1 h; trata 401 como expirado,
reautentica e repete **uma vez**. Nunca persiste o token em Redis ou disco.

Ambientes controlados por YELUM_ENV:
  "mock"          → sandbox Yelum (padrão — sem credencial real)
  "homologacao"   → integracao-tst com dados de homologação
  "producao"      → integracao (produção)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.infra.secrets import get_optional_secret, get_secret

_HOST_TST = "https://integracao-tst.grupohdiseguros.com.br"
_HOST_PROD = "https://integracao.grupohdiseguros.com.br"

_BASE_MOCK = f"{_HOST_TST}/offer/property/sandbox/v1"
_BASE_HOMOL = f"{_HOST_TST}/offer/v1"
_BASE_PROD = f"{_HOST_PROD}/offer/v1"

_TTL_S = 3600.0  # TTL fixo: 1 h (Yelum não publica expires_in)
_MARGEM_S = 120.0  # renova 2 min antes do TTL


@dataclass
class _TokenCache:
    token: str = ""
    expira_em: float = field(default=0.0)


_cache = _TokenCache()


def _env() -> str:
    return get_optional_secret("YELUM_ENV", "mock")


def _base_url() -> str:
    env = _env()
    if env == "producao":
        return _BASE_PROD
    if env == "homologacao":
        return _BASE_HOMOL
    return _BASE_MOCK


def _auth_host() -> str:
    return _HOST_PROD if _env() == "producao" else _HOST_TST


async def _autenticar() -> str:
    """Obtém token via password-grant disfarçado de client_credentials."""
    async with httpx.AsyncClient() as c:
        resp = await c.post(
            f"{_auth_host()}/controledeacesso/token",
            params={"grant_type": "client_credentials"},
            data={
                "client_id": get_secret("YELUM_CLIENT_ID"),
                "client_secret": get_secret("YELUM_CLIENT_SECRET"),
                "username": get_secret("YELUM_USERNAME"),
                "password": get_secret("YELUM_PASSWORD"),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
        resp.raise_for_status()
    return str(resp.json()["access_token"])


async def _obter_token() -> str:
    now = time.monotonic()
    if _cache.token and _cache.expira_em > now + _MARGEM_S:
        return _cache.token
    _cache.token = await _autenticar()
    _cache.expira_em = now + _TTL_S
    return _cache.token


def _invalida_cache() -> None:
    _cache.token = ""
    _cache.expira_em = 0.0


async def _request(
    method: str,
    path: str,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Executa request autenticado com retry único em 401."""
    token = await _obter_token()
    async with httpx.AsyncClient() as c:
        resp = await c.request(
            method,
            f"{_base_url()}{path}",
            json=json,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
        )
        if resp.status_code == 401:
            _invalida_cache()
            token = await _obter_token()
            resp = await c.request(
                method,
                f"{_base_url()}{path}",
                json=json,
                headers={"Authorization": f"Bearer {token}"},
                timeout=60.0,
            )
        resp.raise_for_status()
    return dict(resp.json())


async def cotar(payload: dict[str, Any]) -> dict[str, Any]:
    """POST /quote — cotação de residência."""
    return await _request("POST", "/quote", json=payload)


async def recotar(
    broker_proposal_number: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """PUT /quote/{BrokerProposalNumber} — re-cotação a partir de ID Yelum."""
    return await _request("PUT", f"/quote/{broker_proposal_number}", json=payload)


async def propor(payload: dict[str, Any]) -> dict[str, Any]:
    """POST /proposal — transmissão de proposta."""
    return await _request("POST", "/proposal", json=payload)
