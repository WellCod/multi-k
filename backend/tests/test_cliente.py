"""Testes de CRUD de cliente e busca por CPF."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.auth import Papel
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario

_CPF_A = "12345678901"
_CPF_B = "98765432100"


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


async def test_criar_e_obter_cliente(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "cor_cli_create@test.com")
    payload = {
        "nome": "João Silva",
        "cpf": _CPF_A,
        "email": "joao@example.com",
        "estado_civil": "solteiro",
        "profissao": "autonomo",
    }
    r = await client.post("/clientes", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["nome"] == "João Silva"
    assert "cpf" not in body  # CPF nunca retornado

    cliente_id = body["id"]
    r2 = await client.get(f"/clientes/{cliente_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == cliente_id


async def test_busca_por_cpf(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "cor_cli_busca@test.com")
    await client.post(
        "/clientes",
        json={"nome": "Maria Costa", "cpf": _CPF_B},
    )
    r = await client.post("/clientes/busca", json={"cpf": _CPF_B})
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["nome"] == "Maria Costa"


async def test_busca_cpf_nao_encontrado(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "cor_cli_miss@test.com")
    r = await client.post("/clientes/busca", json={"cpf": "00000000000"})
    assert r.status_code == 200
    assert r.json() == []


async def test_sem_auth_retorna_401(client: AsyncClient, engine: AsyncEngine) -> None:
    r = await client.get("/clientes")
    assert r.status_code == 401


async def test_isolamento_entre_corretores(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Corretor A não enxerga clientes do corretor B."""
    await _login(client, db, "cor_cli_a@test.com")
    await client.post("/clientes", json={"nome": "Cliente A", "cpf": "11111111111"})

    # login como corretor B
    await criar_usuario(db, "cor_cli_b@test.com", Papel.CORRETOR)
    await db.commit()
    await client.post(
        "/auth/login", json={"email": "cor_cli_b@test.com", "senha": "Senha@123"}
    )
    r = await client.get("/clientes")
    assert r.status_code == 200
    assert all(c["nome"] != "Cliente A" for c in r.json()["items"])


async def test_adicionar_veiculo(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "cor_cli_vei@test.com")
    r_cli = await client.post(
        "/clientes", json={"nome": "Ana Lima", "cpf": "22222222222"}
    )
    cid = r_cli.json()["id"]

    payload = {
        "marca": "Chevrolet",
        "modelo": "Onix",
        "ano_fabricacao": 2022,
        "ano_modelo": 2023,
        "combustivel": "flex",
        "finalidade": "lazer",
        "cep_pernoite": "13010001",
    }
    r = await client.post(f"/clientes/{cid}/veiculos", json=payload)
    assert r.status_code == 201
    assert r.json()["marca"] == "Chevrolet"

    r2 = await client.get(f"/clientes/{cid}/veiculos")
    assert len(r2.json()) == 1


async def test_adicionar_imovel(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "cor_cli_imo@test.com")
    r_cli = await client.post(
        "/clientes", json={"nome": "Pedro Alves", "cpf": "33333333333"}
    )
    cid = r_cli.json()["id"]

    payload = {
        "cep": "13010001",
        "tipo_imovel": "apartamento",
        "tipo_construcao": "alvenaria",
    }
    r = await client.post(f"/clientes/{cid}/imoveis", json=payload)
    assert r.status_code == 201


async def test_atualizar_cliente(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "cor_cli_upd@test.com")
    r_cli = await client.post(
        "/clientes", json={"nome": "Luiza Braga", "cpf": "44444444444"}
    )
    cid = r_cli.json()["id"]

    r_patch = await client.patch(
        f"/clientes/{cid}",
        json={"nome": "Luiza Braga Lima", "email": "luiza@example.com"},
    )
    assert r_patch.status_code == 200
    body = r_patch.json()
    assert body["nome"] == "Luiza Braga Lima"
    assert body["email"] == "luiza@example.com"


async def test_timeline_cliente(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "cor_cli_tl@test.com")
    r_cli = await client.post(
        "/clientes", json={"nome": "Sandra Melo", "cpf": "55555555555"}
    )
    cid = r_cli.json()["id"]

    r_tl = await client.get(f"/clientes/{cid}/timeline")
    assert r_tl.status_code == 200
    items = r_tl.json()
    assert len(items) >= 1
    assert items[0]["tipo"] == "cliente.criado"
    assert items[0]["dados"]["nome"] == "Sandra Melo"


async def test_arquivar_cliente(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """DELETE /clientes/{id} deve arquivar (ativo=False) e retornar 204."""
    await _login(client, db, "cor_cli_del@test.com")
    r_cli = await client.post(
        "/clientes", json={"nome": "Arquivado Teste", "cpf": "88888888881"}
    )
    assert r_cli.status_code == 201
    cid = r_cli.json()["id"]

    r_del = await client.delete(f"/clientes/{cid}")
    assert r_del.status_code == 204

    # Cliente arquivado não aparece mais no GET (ativo=False)
    r_list = await client.get("/clientes")
    assert all(c["id"] != cid for c in r_list.json()["items"])


async def test_listar_clientes_com_busca_por_nome(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """GET /clientes?q=termo deve filtrar por nome."""
    await _login(client, db, "cor_cli_q@test.com")
    await client.post("/clientes", json={"nome": "Zulmira Busca", "cpf": "88888888882"})
    r = await client.get("/clientes", params={"q": "Zulmira"})
    assert r.status_code == 200
    body = r.json()
    assert any("Zulmira" in c["nome"] for c in body["items"])


async def test_listar_imoveis_cliente(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """GET /clientes/{id}/imoveis deve retornar lista de imóveis."""
    await _login(client, db, "cor_cli_imolst@test.com")
    r_cli = await client.post(
        "/clientes", json={"nome": "Cliente Imovel List", "cpf": "88888888883"}
    )
    cid = r_cli.json()["id"]

    await client.post(
        f"/clientes/{cid}/imoveis",
        json={
            "cep": "13010001",
            "tipo_imovel": "casa",
            "tipo_construcao": "alvenaria",
        },
    )
    r = await client.get(f"/clientes/{cid}/imoveis")
    assert r.status_code == 200
    assert len(r.json()) == 1
