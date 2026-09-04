"""Testes de CRUD de usuários — rotas /admin/usuarios (apenas admins)."""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.domain.auth import Papel
from app.infra.models import Base
from app.main import app
from tests.conftest import _RLS_STMTS, CsrfAuth, criar_usuario


@pytest_asyncio.fixture(scope="module")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Engine isolado para test_admin — não faz drop_all no teardown para evitar
    race condition com outros módulos no event loop de sessão compartilhado."""
    import os

    url = os.environ["DATABASE_URL"]
    e = create_async_engine(url)
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        for stmt in _RLS_STMTS:
            await conn.execute(text(stmt))
    yield e
    # Sem drop_all: o próximo módulo fará o drop na sua própria fixture de engine.
    await e.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        c._auth = CsrfAuth(c.cookies)  # type: ignore[assignment]
        yield c


async def _login(
    client: AsyncClient, db: AsyncSession, papel: Papel, email: str
) -> None:
    await criar_usuario(db, email, papel)
    await db.commit()
    r = await client.post("/auth/login", json={"email": email, "senha": "Senha@123"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Autenticação e autorização
# ---------------------------------------------------------------------------


async def test_listar_sem_auth_retorna_401(client: AsyncClient) -> None:
    r = await client.get("/admin/usuarios")
    assert r.status_code == 401


async def test_listar_corretor_retorna_403(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, Papel.CORRETOR, "admin_corretor@test.com")
    r = await client.get("/admin/usuarios")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /admin/usuarios
# ---------------------------------------------------------------------------


async def test_listar_usuarios_como_admin(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, Papel.ADMIN, "admin_list@test.com")
    r = await client.get("/admin/usuarios")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert all(
        k in data[0] for k in ("id", "email", "nome", "papel", "ativo", "criado_em")
    )


# ---------------------------------------------------------------------------
# POST /admin/usuarios
# ---------------------------------------------------------------------------


async def test_criar_usuario_retorna_201(db: AsyncSession, client: AsyncClient) -> None:
    await _login(client, db, Papel.ADMIN, "admin_criar@test.com")
    r = await client.post(
        "/admin/usuarios",
        json={
            "email": "novo_user_crud@test.com",
            "nome": "Novo User",
            "papel": "corretor",
            "senha": "Senha@123",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "novo_user_crud@test.com"
    assert body["papel"] == "corretor"
    assert body["ativo"] is True


async def test_criar_usuario_email_duplicado_retorna_409(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, Papel.ADMIN, "admin_dup@test.com")
    payload = {
        "email": "duplicado_admin@test.com",
        "nome": "Dup",
        "papel": "corretor",
        "senha": "Senha@123",
    }
    r1 = await client.post("/admin/usuarios", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/admin/usuarios", json=payload)
    assert r2.status_code == 409


async def test_criar_usuario_nome_curto_retorna_422(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, Papel.ADMIN, "admin_nome_curto@test.com")
    r = await client.post(
        "/admin/usuarios",
        json={
            "email": "x@test.com",
            "nome": "A",
            "papel": "corretor",
            "senha": "Senha@123",
        },
    )
    assert r.status_code == 422


async def test_criar_usuario_senha_curta_retorna_422(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, Papel.ADMIN, "admin_senha_curta@test.com")
    r = await client.post(
        "/admin/usuarios",
        json={
            "email": "y@test.com",
            "nome": "Valido",
            "papel": "corretor",
            "senha": "curta",
        },
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /admin/usuarios/{id}
# ---------------------------------------------------------------------------


async def test_atualizar_nome_retorna_200(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, Papel.ADMIN, "admin_patch@test.com")
    alvo = await criar_usuario(db, "alvo_patch@test.com", Papel.CORRETOR)
    await db.commit()
    r = await client.patch(
        f"/admin/usuarios/{alvo.id}",
        json={"nome": "Nome Atualizado"},
    )
    assert r.status_code == 200
    assert r.json()["nome"] == "Nome Atualizado"


async def test_atualizar_papel_para_admin(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, Papel.ADMIN, "admin_patch2@test.com")
    alvo = await criar_usuario(db, "alvo_papel@test.com", Papel.CORRETOR)
    await db.commit()
    r = await client.patch(
        f"/admin/usuarios/{alvo.id}",
        json={"papel": "admin"},
    )
    assert r.status_code == 200
    assert r.json()["papel"] == "admin"


async def test_desativar_outro_usuario(db: AsyncSession, client: AsyncClient) -> None:
    await _login(client, db, Papel.ADMIN, "admin_desat@test.com")
    alvo = await criar_usuario(db, "alvo_desat@test.com", Papel.CORRETOR)
    await db.commit()
    r = await client.patch(
        f"/admin/usuarios/{alvo.id}",
        json={"ativo": False},
    )
    assert r.status_code == 200
    assert r.json()["ativo"] is False


async def test_nao_pode_desativar_propria_conta(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, Papel.ADMIN, "admin_self@test.com")
    # Descobre o próprio ID
    lista = await client.get("/admin/usuarios")
    usuarios = lista.json()
    meu_id = next(u["id"] for u in usuarios if u["email"] == "admin_self@test.com")
    r = await client.patch(f"/admin/usuarios/{meu_id}", json={"ativo": False})
    assert r.status_code == 400


async def test_atualizar_usuario_inexistente_retorna_404(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, Papel.ADMIN, "admin_404patch@test.com")
    import uuid

    r = await client.patch(
        f"/admin/usuarios/{uuid.uuid4()}",
        json={"nome": "Fantasma"},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /admin/usuarios/{id}/reset-senha
# ---------------------------------------------------------------------------


async def test_reset_senha_retorna_204(db: AsyncSession, client: AsyncClient) -> None:
    await _login(client, db, Papel.ADMIN, "admin_reset@test.com")
    alvo = await criar_usuario(db, "alvo_reset@test.com", Papel.CORRETOR)
    await db.commit()
    r = await client.post(
        f"/admin/usuarios/{alvo.id}/reset-senha",
        json={"nova_senha": "NovaSenha@456"},
    )
    assert r.status_code == 204


async def test_reset_senha_usuario_inexistente_retorna_404(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, Papel.ADMIN, "admin_reset404@test.com")
    import uuid

    r = await client.post(
        f"/admin/usuarios/{uuid.uuid4()}/reset-senha",
        json={"nova_senha": "NovaSenha@456"},
    )
    assert r.status_code == 404


async def test_reset_senha_curta_retorna_422(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, Papel.ADMIN, "admin_resetsz@test.com")
    alvo = await criar_usuario(db, "alvo_resetsz@test.com", Papel.CORRETOR)
    await db.commit()
    r = await client.post(
        f"/admin/usuarios/{alvo.id}/reset-senha",
        json={"nova_senha": "curta"},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Testes diretos (sem ASGI) — cobrem linhas após await que ASGI não rastreia
# ---------------------------------------------------------------------------


async def test_direct_listar_usuarios(db: AsyncSession) -> None:
    """Chama listar_usuarios diretamente para cobrir o return após await."""
    from app.api.admin_router import listar_usuarios

    admin = await criar_usuario(db, "direct_admin_list@test.com", Papel.ADMIN)
    await db.commit()
    result = await listar_usuarios(_usuario=admin, db=db)
    assert isinstance(result, list)
    assert any(u.email == "direct_admin_list@test.com" for u in result)


async def test_direct_criar_usuario(db: AsyncSession) -> None:
    """Chama criar_usuario diretamente — cobre o corpo após await."""
    import pytest
    from fastapi import HTTPException

    from app.api.admin_router import UsuarioCriar
    from app.api.admin_router import criar_usuario as _criar

    admin = await criar_usuario(db, "direct_admin_criar@test.com", Papel.ADMIN)
    await db.commit()

    body = UsuarioCriar(
        email="novo_direto@test.com",
        nome="Novo Direto",
        papel="corretor",
        senha="Senha@123",
    )
    novo = await _criar(_usuario=admin, db=db, body=body)
    assert novo.email == "novo_direto@test.com"

    with pytest.raises(HTTPException) as exc:
        await _criar(_usuario=admin, db=db, body=body)
    assert exc.value.status_code == 409


async def test_direct_atualizar_usuario(db: AsyncSession) -> None:
    """Chama atualizar_usuario diretamente — cobre corpo após await."""
    import uuid

    import pytest
    from fastapi import HTTPException
    from pydantic import ValidationError

    from app.api.admin_router import UsuarioAtualizar
    from app.api.admin_router import atualizar_usuario as _atualizar

    admin = await criar_usuario(db, "direct_admin_patch@test.com", Papel.ADMIN)
    alvo = await criar_usuario(db, "direct_alvo_patch@test.com", Papel.CORRETOR)
    await db.commit()

    resultado = await _atualizar(
        usuario_id=alvo.id,
        _usuario=admin,
        db=db,
        body=UsuarioAtualizar(nome="Novo Nome"),
    )
    assert resultado.nome == "Novo Nome"

    resultado2 = await _atualizar(
        usuario_id=alvo.id,
        _usuario=admin,
        db=db,
        body=UsuarioAtualizar(papel="admin"),
    )
    assert resultado2.papel == "admin"

    resultado3 = await _atualizar(
        usuario_id=alvo.id,
        _usuario=admin,
        db=db,
        body=UsuarioAtualizar(ativo=False),
    )
    assert resultado3.ativo is False

    with pytest.raises(HTTPException) as exc:
        await _atualizar(
            usuario_id=uuid.uuid4(),
            _usuario=admin,
            db=db,
            body=UsuarioAtualizar(nome="X" * 5),
        )
    assert exc.value.status_code == 404

    with pytest.raises(ValidationError):
        UsuarioAtualizar(nome="X")


async def test_direct_reset_senha(db: AsyncSession) -> None:
    """Chama reset_senha diretamente — cobre corpo após await."""
    import uuid

    import pytest
    from fastapi import HTTPException

    from app.api.admin_router import ResetSenhaInput
    from app.api.admin_router import reset_senha as _reset

    admin = await criar_usuario(db, "direct_admin_reset@test.com", Papel.ADMIN)
    alvo = await criar_usuario(db, "direct_alvo_reset@test.com", Papel.CORRETOR)
    await db.commit()

    body = ResetSenhaInput(nova_senha="NovaSenha@456")
    await _reset(usuario_id=alvo.id, _usuario=admin, db=db, body=body)

    with pytest.raises(HTTPException) as exc:
        await _reset(usuario_id=uuid.uuid4(), _usuario=admin, db=db, body=body)
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Gestão de Comissão por CIA — /admin/comissoes
# ---------------------------------------------------------------------------


async def test_listar_comissoes_admin(db: AsyncSession, client: AsyncClient) -> None:
    await _login(client, db, Papel.ADMIN, "admin_comissao_list@test.com")
    r = await client.get("/admin/comissoes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_upsert_comissao_cria(db: AsyncSession, client: AsyncClient) -> None:
    await _login(client, db, Papel.ADMIN, "admin_comissao_cria@test.com")
    r = await client.put(
        "/admin/comissoes/justos/auto",
        json={"pct_padrao": "0.0500"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["cia"] == "justos"
    assert body["ramo"] == "auto"
    assert body["pct_padrao"] == "0.0500"


async def test_upsert_comissao_atualiza(db: AsyncSession, client: AsyncClient) -> None:
    await _login(client, db, Papel.ADMIN, "admin_comissao_atualiza@test.com")
    # Garante existência
    await client.put(
        "/admin/comissoes/yelum/imovel",
        json={"pct_padrao": "0.0300"},
    )
    # Atualiza
    r = await client.put(
        "/admin/comissoes/yelum/imovel",
        json={"pct_padrao": "0.0600"},
    )
    assert r.status_code == 200
    assert r.json()["pct_padrao"] == "0.0600"


async def test_delete_comissao(db: AsyncSession, client: AsyncClient) -> None:
    await _login(client, db, Papel.ADMIN, "admin_comissao_del@test.com")
    await client.put(
        "/admin/comissoes/fake/auto",
        json={"pct_padrao": "0.1000"},
    )
    r = await client.delete("/admin/comissoes/fake/auto")
    assert r.status_code == 204


async def test_get_comissao_por_cia_ramo(db: AsyncSession, client: AsyncClient) -> None:
    await _login(client, db, Papel.ADMIN, "admin_comissao_get@test.com")
    await client.put(
        "/admin/comissoes/justos/vida",
        json={"pct_padrao": "0.0800"},
    )
    r = await client.get("/admin/comissoes/justos/vida")
    assert r.status_code == 200
    body = r.json()
    assert body["cia"] == "justos"
    assert body["ramo"] == "vida"


async def test_get_comissao_inexistente_retorna_404(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, Papel.ADMIN, "admin_comissao_404@test.com")
    r = await client.get("/admin/comissoes/inexistente/ramo")
    assert r.status_code == 404


async def test_upsert_comissao_pct_invalido_retorna_422(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, Papel.ADMIN, "admin_comissao_inv@test.com")
    r = await client.put(
        "/admin/comissoes/justos/auto",
        json={"pct_padrao": "0.9999"},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Testes diretos — cobrem corpos dos handlers sem depender de HTTP/auth
# ---------------------------------------------------------------------------


async def test_direct_listar_comissoes(db: AsyncSession) -> None:
    import pytest
    from fastapi import HTTPException

    from app.api.admin_router import ComissaoConfigIn
    from app.api.admin_router import delete_comissao as _delete
    from app.api.admin_router import get_comissao as _get
    from app.api.admin_router import listar_comissoes as _list
    from app.api.admin_router import upsert_comissao as _upsert

    admin = await criar_usuario(db, "direct_comissao@test.com", Papel.ADMIN)
    await db.commit()

    # listar (vazia ou não — cobre linha 232)
    result = await _list(_usuario=admin, db=db)
    assert isinstance(result, list)

    # upsert cria — cobre linhas 260-268 (branch else)
    body = ComissaoConfigIn(pct_padrao="0.1500")
    cfg = await _upsert(cia="direct_cia", ramo="auto", _usuario=admin, db=db, body=body)
    assert cfg.cia == "direct_cia"
    assert str(cfg.pct_padrao) == "0.1500"

    # upsert atualiza — cobre linhas 260-268 (branch if)
    body2 = ComissaoConfigIn(pct_padrao="0.2000")
    cfg2 = await _upsert(
        cia="direct_cia", ramo="auto", _usuario=admin, db=db, body=body2
    )
    assert str(cfg2.pct_padrao) == "0.2000"

    # get existente — cobre linha 248
    found = await _get(cia="direct_cia", ramo="auto", _usuario=admin, db=db)
    assert found.cia == "direct_cia"

    # get inexistente — cobre linhas 243-247
    with pytest.raises(HTTPException) as exc:
        await _get(cia="nao_existe", ramo="auto", _usuario=admin, db=db)
    assert exc.value.status_code == 404

    # delete existente — cobre linhas 282-288
    await _delete(cia="direct_cia", ramo="auto", _usuario=admin, db=db)

    # delete inexistente — cobre linhas 282-285
    with pytest.raises(HTTPException) as exc2:
        await _delete(cia="nao_existe", ramo="auto", _usuario=admin, db=db)
    assert exc2.value.status_code == 404
