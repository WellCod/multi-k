"""Regressões de segurança com dados sintéticos e sem chamadas a seguradoras."""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.auth import Papel
from app.infra.auth_service import (
    buscar_sessao_valida,
    criar_sessao,
    invalidar_sessoes_usuario,
    prorrogar_sessao,
)
from app.infra.models import Cliente, Cotacao, CotacaoJob, Sessao
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario


async def test_concurrent_finalization_publishes_committed_price_once(
    db: AsyncSession,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.infra import worker

    user = await criar_usuario(db, f"{uuid.uuid4()}@test.com", Papel.CORRETOR)
    quote = Cotacao(
        ramo="auto", status="processando", usuario_id=user.id, dados_risco={}
    )
    db.add(quote)
    await db.flush()
    db.add_all(
        [
            CotacaoJob(
                cotacao_id=quote.id,
                cia=cia,
                status="concluido",
                status_resultado="sucesso",
                premio_total=Decimal("123.45"),
            )
            for cia in ("fake", "synthetic")
        ]
    )
    await db.commit()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    sessions: list[AsyncSession] = []
    notifications: list[dict[str, object]] = []

    def tracked_factory() -> AsyncSession:
        session = factory()
        sessions.append(session)
        return session

    def publish(uid: uuid.UUID, notification: dict[str, object]) -> None:
        assert uid == user.id
        # Outra finalização pode estar em andamento, mas a que publica já encerrou.
        assert any(not session.in_transaction() for session in sessions)
        notifications.append(notification)

    monkeypatch.setattr(worker.events_bus, "publish", publish)
    await asyncio.gather(
        *(
            worker._finalizar_cotacao(quote.id, tracked_factory)  # type: ignore[arg-type]
            for _ in range(2)
        )
    )
    await db.refresh(quote)
    assert quote.status == "sucesso"
    assert quote.premio_total == Decimal("123.45")
    assert len(notifications) == 1
    assert notifications[0]["premio_total"] == "123.45"


async def test_finalization_does_not_publish_when_commit_fails(
    db: AsyncSession,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.infra import worker

    user = await criar_usuario(db, f"{uuid.uuid4()}@test.com", Papel.CORRETOR)
    quote = Cotacao(
        ramo="auto", status="processando", usuario_id=user.id, dados_risco={}
    )
    db.add(quote)
    await db.flush()
    db.add(
        CotacaoJob(
            cotacao_id=quote.id,
            cia="fake",
            status="concluido",
            status_resultado="sucesso",
            premio_total=Decimal("100.00"),
        )
    )
    await db.commit()
    notifications: list[object] = []
    monkeypatch.setattr(
        worker.events_bus, "publish", lambda *args: notifications.append(args)
    )

    def fail_commit(*_: object) -> None:
        raise RuntimeError("synthetic commit failure")

    event.listen(engine.sync_engine, "commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="synthetic commit failure"):
            await worker._finalizar_cotacao(
                quote.id, async_sessionmaker(engine, expire_on_commit=False)
            )
    finally:
        event.remove(engine.sync_engine, "commit", fail_commit)
    assert notifications == []
    await db.refresh(quote)
    assert quote.status == "processando"


async def test_worker_bounds_in_flight_jobs(
    db: AsyncSession,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.infra import worker

    user = await criar_usuario(db, f"{uuid.uuid4()}@test.com", Papel.CORRETOR)
    quote = Cotacao(
        ramo="auto", status="aguardando", usuario_id=user.id, dados_risco={}
    )
    db.add(quote)
    await db.flush()
    db.add_all(
        [
            CotacaoJob(cotacao_id=quote.id, cia="fake", status="pendente")
            for _ in range(8)
        ]
    )
    await db.commit()
    gate, started, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
    active = peak = completed = 0

    async def process(*_: object) -> None:
        nonlocal active, peak, completed
        active += 1
        peak = max(peak, active)
        if active == 5:
            started.set()
        await gate.wait()
        active -= 1
        completed += 1
        if completed == 8:
            finished.set()

    monkeypatch.setattr(worker, "_safe_processar", process)
    monkeypatch.setattr(worker, "_POLL_INTERVAL", 0.001)
    task = worker.start_worker(async_sessionmaker(engine, expire_on_commit=False))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        await asyncio.sleep(0.05)
        assert peak <= 5
        gate.set()
        await asyncio.wait_for(finished.wait(), timeout=5)
        assert completed == 8
    finally:
        gate.set()
        task.cancel()
        await task


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        http._auth = CsrfAuth(http.cookies)  # type: ignore[assignment]
        yield http


@pytest.mark.parametrize("mode", ["warn", "strict"])
async def test_ip_logs_never_contain_credentials_or_addresses(
    db: AsyncSession,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    monkeypatch.setattr("app.infra.auth_service._IP_CHECK_MODE", mode)
    user = await criar_usuario(db, f"{uuid.uuid4()}@test.com", Papel.CORRETOR)
    sid = await criar_sessao(db, user.id, "192.0.2.1")
    result = await buscar_sessao_valida(db, sid, "192.0.2.2")
    assert (result is None) == (mode == "strict")
    assert "session_ip_mismatch" in caplog.text
    for sensitive in (str(sid), "192.0.2.1", "192.0.2.2", user.email):
        assert sensitive not in caplog.text


async def test_revocation_affects_all_sessions_only_for_target(
    db: AsyncSession,
) -> None:
    user = await criar_usuario(db, f"{uuid.uuid4()}@test.com", Papel.CORRETOR)
    other = await criar_usuario(db, f"{uuid.uuid4()}@test.com", Papel.CORRETOR)
    sessions = [await criar_sessao(db, user.id, None) for _ in range(2)]
    other_sid = await criar_sessao(db, other.id, None)
    await invalidar_sessoes_usuario(db, user.id)
    for sid in sessions:
        assert await buscar_sessao_valida(db, sid) is None
        assert not await prorrogar_sessao(db, sid)
    assert await buscar_sessao_valida(db, other_sid) is not None


async def test_refresh_rejects_disabled_user(db: AsyncSession) -> None:
    user = await criar_usuario(db, f"{uuid.uuid4()}@test.com", Papel.CORRETOR)
    sid = await criar_sessao(db, user.id, None)
    user.ativo = False
    await db.flush()
    assert not await prorrogar_sessao(db, sid)


async def test_absolute_session_limit_cannot_be_extended(db: AsyncSession) -> None:
    user = await criar_usuario(db, f"{uuid.uuid4()}@test.com", Papel.CORRETOR)
    sid = await criar_sessao(db, user.id, None)
    session = await db.get(Sessao, sid)
    assert session is not None
    session.criada_em = datetime.now(UTC) - timedelta(hours=7)
    await db.flush()
    assert await prorrogar_sessao(db, sid)
    assert session.expira_em == session.criada_em + timedelta(hours=8)
    session.criada_em = datetime.now(UTC) - timedelta(hours=9)
    session.expira_em = datetime.now(UTC) + timedelta(hours=1)
    await db.flush()
    assert await buscar_sessao_valida(db, sid) is None
    assert not await prorrogar_sessao(db, sid)


def test_coverage_response_is_allowlisted() -> None:
    from app.api.comparativo_router import _coverage_options

    job = CotacaoJob(
        payload_resposta={
            "coverages_available": {
                "collision": {
                    "name": "Colisão",
                    "mandatory": True,
                    "private_context": "do-not-send",
                    "peril_options": [
                        {
                            "slug": "full",
                            "name": "Completa",
                            "price": "12.34",
                            "coverage_amount": "1000",
                            "internal_token": "do-not-send",
                        }
                    ],
                }
            }
        }
    )
    output = _coverage_options(job)
    assert output is not None
    assert "private_context" not in output["collision"]
    option = output["collision"]["peril_options"][0]
    assert "internal_token" not in option
    assert option["price"] == "12.34"
    assert option["coverage_amount"] == "1000.00"


async def test_password_reset_revokes_existing_session(
    db: AsyncSession,
    client: AsyncClient,
) -> None:
    admin = await criar_usuario(db, f"{uuid.uuid4()}@test.com", Papel.ADMIN)
    user = await criar_usuario(db, f"{uuid.uuid4()}@test.com", Papel.CORRETOR)
    sid = await criar_sessao(db, user.id, None)
    await db.commit()
    await client.post("/auth/login", json={"email": admin.email, "senha": "Senha@123"})
    response = await client.post(
        f"/admin/usuarios/{user.id}/reset-senha", json={"nova_senha": "NovaSenha@123"}
    )
    assert response.status_code == 204
    session = await db.get(Sessao, sid, populate_existing=True)
    assert session is not None and session.expira_em <= datetime.now(UTC)


async def test_history_minimizes_risk_and_rejects_foreign_links(
    db: AsyncSession,
    client: AsyncClient,
) -> None:
    user = await criar_usuario(db, f"{uuid.uuid4()}@test.com", Papel.CORRETOR)
    other = await criar_usuario(db, f"{uuid.uuid4()}@test.com", Papel.CORRETOR)
    risk = {
        "codigo_fipe": "synthetic",
        "cep_pernoite": "01001000",
        "finalidade": "particular",
        "proponente": {
            "nome": "Sintético",
            "cpf": "00000000000",
            "email": "synthetic@example.invalid",
        },
    }
    own = Cotacao(
        ramo="auto", status="aguardando", usuario_id=user.id, dados_risco=risk
    )
    foreign = Cotacao(
        ramo="auto", status="aguardando", usuario_id=other.id, dados_risco=risk
    )
    customer = Cliente(nome="Sintético", cpf_idx="synthetic", usuario_id=other.id)
    db.add_all([own, foreign, customer])
    await db.commit()
    await client.post("/auth/login", json={"email": user.email, "senha": "Senha@123"})
    history = await client.get("/cotacoes")
    assert history.status_code == 200
    assert history.headers["cache-control"] == "no-store"
    assert len(history.json()["items"]) == 1
    assert history.json()["items"][0]["dados_risco"] == {
        "proponente": {"nome": "Sintético"}
    }
    detail = await client.get(f"/cotacoes/{own.id}")
    assert detail.status_code == 200
    assert detail.json()["dados_risco"] == risk
    compact = await client.get(f"/cotacoes/{own.id}/status")
    assert compact.status_code == 200
    assert set(compact.json()) == {
        "id",
        "status",
        "premio_total",
        "proposta_id",
        "numero_apolice",
    }
    assert compact.json()["status"] == detail.json()["status"]
    assert compact.headers["cache-control"] == "no-store"
    assert (await client.get(f"/cotacoes/{foreign.id}/status")).status_code == 404
    assert (await client.get(f"/cotacoes/{foreign.id}")).status_code == 404
    for field, value in (
        ("cliente_id", customer.id),
        ("versao_anterior_id", foreign.id),
    ):
        response = await client.post(
            "/cotacoes",
            json={
                "ramo": "auto",
                "dados": risk,
                field: str(value),
            },
        )
        assert response.status_code == 404
