"""Testes para api/dominio_router.py."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

import app.api.dominio_router as dominio_router
from app.domain.auth import Papel
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        c._auth = CsrfAuth(c.cookies)  # type: ignore[assignment]
        yield c


async def _login(client: AsyncClient, db: AsyncSession, email: str) -> None:
    await criar_usuario(db, email, Papel.CORRETOR)
    await db.commit()
    r = await client.post("/auth/login", json={"email": email, "senha": "Senha@123"})
    assert r.status_code == 200


async def test_sem_auth_retorna_401(client: AsyncClient, engine: AsyncEngine) -> None:
    r = await client.get("/dominios")
    assert r.status_code == 401


async def test_lista_dominios_autenticado(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    dominio_router._dominio_cache.clear()
    await _login(client, db, "dom_list@test.com")
    r = await client.get("/dominios")
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    assert len(items) > 0
    assert "tipo" in items[0]
    assert "codigo" in items[0]
    assert "descricao" in items[0]


async def test_filtro_por_tipo(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    dominio_router._dominio_cache.clear()
    await _login(client, db, "dom_tipo@test.com")
    r = await client.get("/dominios?tipo=profissao")
    assert r.status_code == 200
    items = r.json()
    assert all(i["tipo"] == "profissao" for i in items)


async def test_cache_retorna_mesmo_resultado(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    dominio_router._dominio_cache.clear()
    await _login(client, db, "dom_cache@test.com")
    r1 = await client.get("/dominios?tipo=estado_civil")
    r2 = await client.get("/dominios?tipo=estado_civil")
    assert r1.status_code == 200
    assert r1.json() == r2.json()
    assert ("estado_civil", None) in dominio_router._dominio_cache


def test_todo_tipo_usado_pelo_formulario_tem_opcao_semeada() -> None:
    """Tipo sem linha semeada vira select vazio e trava o passo.

    Aconteceu com profissao, tipo_imovel e tipo_construcao: entraram no _SEED
    depois que a 001 já havia povoado a tabela, e seed_if_empty só popula
    tabela vazia — então nunca chegaram a banco nenhum. A 018 completa o que
    falta; esta lista impede que o próximo campo repita o percurso.
    """
    from app.infra.seed import dominio_rows

    usados = {
        "estado_civil",
        "profissao",
        "tipo_imovel",
        "tipo_construcao",
        "plano_pagamento",
        "sexo",
        "parentesco",
        "bonus",
        "categoria_moto",
        "finalidade_auto",
        "finalidade_moto",
    }
    semeados = {row["tipo"] for row in dominio_rows()}
    assert not usados - semeados, f"sem opção semeada: {sorted(usados - semeados)}"


def test_opcoes_de_dominio_nao_tem_codigo_repetido_no_mesmo_tipo() -> None:
    from app.infra.seed import dominio_rows

    chaves = [(row["tipo"], row["codigo"]) for row in dominio_rows()]
    assert len(chaves) == len(set(chaves))
