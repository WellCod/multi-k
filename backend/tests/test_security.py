"""Testes de segurança: CSRF middleware, validadores M4 e rate-limit FIPE."""

from collections.abc import AsyncGenerator
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.proposta_router import TransmitirInput
from app.domain.auth import Papel
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        c._auth = CsrfAuth(c.cookies)  # type: ignore[assignment]
        yield c


@pytest_asyncio.fixture
async def plain_client() -> AsyncGenerator[AsyncClient, None]:
    """Cliente sem CsrfAuth — para testar que a proteção CSRF está ativa."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _login_plain(
    client: AsyncClient,
    db: AsyncSession,
    email: str,
) -> None:
    """Faz login via plain_client (rota /auth/login é isenta de CSRF)."""
    await criar_usuario(db, email, Papel.CORRETOR)
    await db.commit()
    r = await client.post("/auth/login", json={"email": email, "senha": "Senha@123"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Testes CSRF
# ---------------------------------------------------------------------------


async def test_csrf_post_sem_token_retorna_403(
    db: AsyncSession, plain_client: AsyncClient
) -> None:
    """POST autenticado sem X-CSRF-Token deve retornar 403."""
    await _login_plain(plain_client, db, "csrf_notoken@test.com")
    # sid cookie presente; sem o header CSRF
    r = await plain_client.post(
        "/cotacoes",
        json={
            "ramo": "auto",
            "dados": {
                "codigo_fipe": "001004-9",
                "finalidade": "pessoal",
                "cep_pernoite": "13010001",
            },
        },
    )
    assert r.status_code == 403


async def test_csrf_post_token_errado_retorna_403(
    db: AsyncSession, plain_client: AsyncClient
) -> None:
    """POST autenticado com X-CSRF-Token errado deve retornar 403."""
    await _login_plain(plain_client, db, "csrf_wrongtoken@test.com")
    r = await plain_client.post(
        "/cotacoes",
        json={"ramo": "auto", "dados": {}},
        headers={"X-CSRF-Token": "token-invalido"},
    )
    assert r.status_code == 403


async def test_csrf_login_isento(plain_client: AsyncClient) -> None:
    """/auth/login é isento de CSRF — não deve retornar 403."""
    r = await plain_client.post(
        "/auth/login",
        json={"email": "naoexiste@test.com", "senha": "qualquer"},
    )
    assert r.status_code != 403


async def test_csrf_get_isento(db: AsyncSession, client: AsyncClient) -> None:
    """GET (método seguro) não exige CSRF — deve retornar 200 ou 401, não 403."""
    r = await client.get("/cotacoes")
    assert r.status_code != 403


# ---------------------------------------------------------------------------
# Testes M4 — validador dados_negocio
# ---------------------------------------------------------------------------


def test_m4_dados_negocio_mais_de_50_chaves_levanta_validation_error() -> None:
    """TransmitirInput com >50 chaves em dados_negocio deve levantar ValidationError."""
    dados_grandes = {str(i): i for i in range(51)}
    with pytest.raises(ValidationError, match="50 chaves"):
        TransmitirInput(
            plano_pagamento="mensal",
            n_parcelas=1,
            comissao_pct=Decimal("0.05"),
            dados_negocio=dados_grandes,
        )


def test_m4_dados_negocio_acima_de_10kb_levanta_validation_error() -> None:
    """TransmitirInput com valor >10 KB em dados_negocio levanta ValidationError."""
    dados_grandes = {"chave": "x" * 10_001}
    with pytest.raises(ValidationError, match="10 KB"):
        TransmitirInput(
            plano_pagamento="mensal",
            n_parcelas=1,
            comissao_pct=Decimal("0.05"),
            dados_negocio=dados_grandes,
        )


# ---------------------------------------------------------------------------
# Teste rate-limit FIPE
# ---------------------------------------------------------------------------


async def test_fipe_rate_limit_retorna_429(plain_client: AsyncClient) -> None:
    """Quando rate_limit.allow retorna False, GET /fipe/marcas deve retornar 429."""
    with patch(
        "app.api.fipe_router.rate_limit.allow",
        new=AsyncMock(return_value=False),
    ):
        r = await plain_client.get("/fipe/marcas")
    assert r.status_code == 429
