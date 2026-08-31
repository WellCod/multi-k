"""Testes dos endpoints FIPE: cache hit, fetch e erro 502."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest_asyncio
import respx
from httpx import ASGITransport, AsyncClient, Response

from app.infra import fipe_cache
from app.main import app

_PARALLELUM = "https://parallelum.com.br/fipe/api/v1"


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest_asyncio.fixture(autouse=True)
async def _limpa_cache() -> AsyncGenerator[None, None]:
    """Garante cache limpo antes e depois de cada teste."""
    fipe_cache._cache.clear()
    yield
    fipe_cache._cache.clear()


# ---------------------------------------------------------------------------
# /fipe/marcas
# ---------------------------------------------------------------------------


@respx.mock
async def test_fipe_marcas_retorna_lista(client: AsyncClient) -> None:
    """GET /fipe/marcas deve retornar lista normalizada de marcas."""
    respx.get(f"{_PARALLELUM}/carros/marcas").mock(
        return_value=Response(
            200,
            json=[{"codigo": "59", "nome": "Honda"}, {"codigo": "22", "nome": "Fiat"}],
        )
    )
    r = await client.get("/fipe/marcas")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert body[0]["codigo"] == "59"
    assert body[0]["nome"] == "Honda"


@respx.mock
async def test_fipe_marcas_usa_cache(client: AsyncClient) -> None:
    """Segunda chamada deve usar cache — Parallelum não é contactado."""
    route = respx.get(f"{_PARALLELUM}/carros/marcas").mock(
        return_value=Response(200, json=[{"codigo": "1", "nome": "Acme"}])
    )
    await client.get("/fipe/marcas")
    await client.get("/fipe/marcas")
    assert route.call_count == 1  # segunda chamada usou cache


@respx.mock
async def test_fipe_marcas_502_quando_upstream_falha(client: AsyncClient) -> None:
    """Erro do upstream deve resultar em 502."""
    respx.get(f"{_PARALLELUM}/carros/marcas").mock(
        return_value=Response(503, text="Service Unavailable")
    )
    r = await client.get("/fipe/marcas")
    assert r.status_code == 502


# ---------------------------------------------------------------------------
# /fipe/modelos
# ---------------------------------------------------------------------------


@respx.mock
async def test_fipe_modelos_retorna_lista(client: AsyncClient) -> None:
    """GET /fipe/modelos deve retornar lista de modelos da marca."""
    respx.get(f"{_PARALLELUM}/carros/marcas/59/modelos").mock(
        return_value=Response(
            200, json={"modelos": [{"codigo": "5993", "nome": "Civic"}]}
        )
    )
    r = await client.get("/fipe/modelos", params={"tipo": "carros", "marca_id": "59"})
    assert r.status_code == 200
    body = r.json()
    assert body[0]["nome"] == "Civic"


# ---------------------------------------------------------------------------
# /fipe/anos
# ---------------------------------------------------------------------------


@respx.mock
async def test_fipe_anos_retorna_lista(client: AsyncClient) -> None:
    """GET /fipe/anos deve retornar lista de anos do modelo."""
    respx.get(f"{_PARALLELUM}/carros/marcas/59/modelos/5993/anos").mock(
        return_value=Response(
            200, json=[{"codigo": "2022-1", "nome": "2022 Gasolina"}]
        )
    )
    r = await client.get(
        "/fipe/anos", params={"tipo": "carros", "marca_id": "59", "modelo_id": "5993"}
    )
    assert r.status_code == 200
    assert r.json()[0]["codigo"] == "2022-1"


# ---------------------------------------------------------------------------
# /fipe/preco
# ---------------------------------------------------------------------------


@respx.mock
async def test_fipe_preco_retorna_item(client: AsyncClient) -> None:
    """GET /fipe/preco deve retornar dict com campos normalizados."""
    respx.get(
        f"{_PARALLELUM}/carros/marcas/59/modelos/5993/anos/2022-1"
    ).mock(
        return_value=Response(
            200,
            json={
                "CodigoFipe": "001004-9",
                "Marca": "Honda",
                "Modelo": "Civic",
                "AnoModelo": 2022,
                "Combustivel": "Gasolina",
                "Valor": "R$ 120.000,00",
                "MesReferencia": "agosto de 2026",
            },
        )
    )
    r = await client.get(
        "/fipe/preco",
        params={
            "tipo": "carros",
            "marca_id": "59",
            "modelo_id": "5993",
            "ano_id": "2022-1",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["codigo_fipe"] == "001004-9"
    assert body["valor"] == "R$ 120.000,00"


async def test_fipe_marcas_rate_limit(client: AsyncClient) -> None:
    """Rate limit deve bloquear com 429 quando atingido."""
    with patch(
        "app.api.fipe_router.rate_limit.allow",
        return_value=False,
    ):
        r = await client.get("/fipe/marcas")
    assert r.status_code == 429


@respx.mock
async def test_fipe_modelos_502_quando_upstream_falha(client: AsyncClient) -> None:
    respx.get(f"{_PARALLELUM}/carros/marcas/59/modelos").mock(
        return_value=Response(503, text="unavailable")
    )
    r = await client.get("/fipe/modelos", params={"tipo": "carros", "marca_id": "59"})
    assert r.status_code == 502


@respx.mock
async def test_fipe_anos_502_quando_upstream_falha(client: AsyncClient) -> None:
    respx.get(f"{_PARALLELUM}/carros/marcas/59/modelos/5993/anos").mock(
        return_value=Response(503, text="unavailable")
    )
    r = await client.get(
        "/fipe/anos", params={"tipo": "carros", "marca_id": "59", "modelo_id": "5993"}
    )
    assert r.status_code == 502


def test_fipe_cache_ttl_expirado_retorna_none() -> None:
    """Entrada com TTL expirado deve ser removida e retornar None."""
    import time

    from app.infra import fipe_cache

    fipe_cache._cache["_ttl_expirado"] = fipe_cache._Entry(
        data=[{"codigo": "1", "nome": "Test"}],
        expira_em=time.monotonic() - 1.0,
    )
    result = fipe_cache.get("_ttl_expirado")
    assert result is None
    assert "_ttl_expirado" not in fipe_cache._cache


@respx.mock
async def test_fipe_preco_502_quando_upstream_falha(client: AsyncClient) -> None:
    respx.get(f"{_PARALLELUM}/carros/marcas/59/modelos/5993/anos/2022-1").mock(
        return_value=Response(503, text="unavailable")
    )
    r = await client.get(
        "/fipe/preco",
        params={
            "tipo": "carros",
            "marca_id": "59",
            "modelo_id": "5993",
            "ano_id": "2022-1",
        },
    )
    assert r.status_code == 502
