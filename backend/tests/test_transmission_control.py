"""Transmissões simuladas: deduplicação, auditoria, concorrência e autorização."""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.adapters.base import ResultadoTransmissao
from app.adapters.justos.adapter import JustosSeguradora
from app.api.proposta_router import _adapter_dep
from app.domain.auth import Papel
from app.infra import transmission_control as control
from app.infra.db import get_db
from app.infra.models import Auditoria, Cotacao, CotacaoJob, Proposta, Usuario
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario


@pytest.fixture
def adapter() -> AsyncMock:
    mocked = AsyncMock()
    mocked.transmitir.return_value = ResultadoTransmissao(True, "SYNTHETIC-ACCEPTED")
    return mocked


def as_justos(mocked: AsyncMock) -> AsyncMock:
    """Só a rede é simulada: as regras de preparação da Justos seguem reais.

    O atributo precisa ser real — PreparadorTransmissao é verificado sem
    disparar o __getattr__ do mock.
    """
    mocked.preparar_transmissao = JustosSeguradora().preparar_transmissao
    return mocked


@pytest.fixture
async def client(adapter: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[_adapter_dep] = lambda: adapter
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http:
            http._auth = CsrfAuth(http.cookies)  # type: ignore[assignment]
            yield http
    finally:
        app.dependency_overrides.pop(_adapter_dep, None)


async def setup(db: AsyncSession, client: AsyncClient) -> tuple[Usuario, Cotacao]:
    owner = await criar_usuario(db, f"{uuid.uuid4()}@test.com", Papel.CORRETOR)
    quote = Cotacao(
        usuario_id=owner.id,
        ramo="auto",
        status="sucesso",
        premio_total=Decimal("100.00"),
        cotacao_id_cia="SYNTHETIC",
        dados_risco={"private_field": "synthetic-risk-not-for-audit"},
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
            cotacao_id_cia="SYNTHETIC",
            payload_resposta={
                "comissao_pct_cotada": "0.15",
                "condicoes_pagamento": [
                    {
                        "periodicidade": "monthly",
                        "parcelas": 1,
                        "valor_parcela": "100.00",
                        "valor_total": "100.00",
                    }
                ],
            },
        )
    )
    await db.commit()
    await login(client, owner)
    return owner, quote


async def login(client: AsyncClient, user: Usuario) -> None:
    response = await client.post(
        "/auth/login", json={"email": user.email, "senha": "Senha@123"}
    )
    assert response.status_code == 200


@pytest.mark.parametrize("scenario", ["annual", "unknown", "count", "missing"])
async def test_confirmed_payment_controls_transmission(
    db: AsyncSession,
    client: AsyncClient,
    adapter: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    _, quote = await setup(db, client)
    job = (
        await db.execute(select(CotacaoJob).where(CotacaoJob.cotacao_id == quote.id))
    ).scalar_one()
    job.cia = "justos"
    job.payload_resposta = {
        "comissao_pct_cotada": "0.15",
        "condicoes_pagamento": [
            {
                "periodicidade": "annual",
                "parcelas": 2,
                "valor_parcela": None if scenario == "unknown" else "450.00",
                "valor_total": "900.00",
            }
        ],
    }
    await db.commit()
    revision = (await client.get(f"/cotacoes/{quote.id}/comparativo")).json()[0][
        "revisao_base"
    ]
    data = {
        **body(),
        "cia": "justos",
        "revisao_base": revision,
        "n_parcelas": 3 if scenario == "count" else 2,
        "dados_negocio": {"policy_type": "monthly", "installments": 12},
    }
    if scenario == "missing":
        data.pop("opcao_pagamento")
    monkeypatch.setattr(
        "app.api.proposta_router.get_adapter", lambda _: as_justos(adapter)
    )
    response = await client.post(f"/cotacoes/{quote.id}/transmitir", json=data)
    if scenario == "annual":
        assert response.status_code == 201
        assert Decimal(response.json()["valor_parcela"]) == Decimal("450.00")
        assert response.json()["plano_pagamento"] == "ANUAL_2X"
        sent = adapter.transmitir.call_args.args[0].dados_negocio
        assert sent["policy_type"] == "annual" and sent["installments"] == 2
        entry = (
            await db.execute(
                select(Auditoria).where(
                    Auditoria.tipo == "proposta.transmitida",
                    Auditoria.dados["cotacao_id"].astext == str(quote.id),
                )
            )
        ).scalar_one()
        assert entry.dados["condicao_pagamento"]["valor_total"] == "900.00"
    else:
        assert response.status_code == 409
        adapter.transmitir.assert_not_awaited()


@pytest.mark.parametrize("change", ["price", "coverage", "missing", "valid", "other"])
async def test_transmission_checks_displayed_revision(
    db: AsyncSession,
    client: AsyncClient,
    adapter: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    _, quote = await setup(db, client)
    job = (
        await db.execute(select(CotacaoJob).where(CotacaoJob.cotacao_id == quote.id))
    ).scalar_one()
    job.cia = "justos"
    await db.commit()
    displayed = (await client.get(f"/cotacoes/{quote.id}/comparativo")).json()[0]
    request_body = {
        **body(),
        "cia": "justos",
        "revisao_base": displayed["revisao_base"],
        "inicio_vigencia": "2027-01-20",
        "dados_negocio": {"scheduling_date": "2027-02-20"},
    }
    if change == "price":
        job.premio_total = Decimal("101.00")
    elif change == "coverage":
        job.payload_resposta = {"coverages_selected": {"synthetic": "changed"}}
    elif change == "missing":
        request_body.pop("revisao_base")
    elif change == "other":
        db.add(
            CotacaoJob(
                cotacao_id=quote.id,
                cia="other",
                status="concluido",
                status_resultado="sucesso",
                premio_total=Decimal("99.00"),
            )
        )
    await db.commit()
    monkeypatch.setattr(
        "app.api.proposta_router.get_adapter", lambda _: as_justos(adapter)
    )
    response = await client.post(f"/cotacoes/{quote.id}/transmitir", json=request_body)
    if change in ("valid", "other"):
        assert response.status_code == 201
        assert (
            adapter.transmitir.call_args.args[0].dados_negocio["scheduling_date"]
            == "2027-01-20"
        )
        adapter.transmitir.assert_awaited_once()
        replay = await client.post(
            f"/cotacoes/{quote.id}/transmitir", json=request_body
        )
        assert replay.status_code == 201
        adapter.transmitir.assert_awaited_once()
    else:
        assert response.status_code == 409
        adapter.transmitir.assert_not_awaited()
        state = (await client.get(f"/transmissoes/cotacoes/{quote.id}")).json()
        assert state["estado"] == "sem_tentativa"


@pytest.mark.parametrize("scenario", ["save", "price_changed", "stale", "blocked"])
async def test_apply_coverage_review(
    db: AsyncSession,
    client: AsyncClient,
    adapter: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    from tests.test_repricing_validation import coverage_job

    owner, quote = await setup(db, client)
    job = (
        await db.execute(select(CotacaoJob).where(CotacaoJob.cotacao_id == quote.id))
    ).scalar_one()
    job.cia = "justos"
    job.payload_resposta = coverage_job().payload_resposta
    await db.commit()
    provider = AsyncMock(
        return_value={
            "monthly": {
                "total": "250.00",
                "installments": [
                    {"months": 1, "amount": "250.00", "total_amount": "250.00"}
                ],
            },
            "annual": {"total": "2700.00"},
            "info": "Synthetic",
        }
    )
    monkeypatch.setattr(
        "app.api.comparativo_router.justos_client.calcular_preco", provider
    )
    url = f"/cotacoes/{quote.id}/repricing"
    selection = {"required": "required-option", "optional": None}
    preview = await client.post(
        url, json={"cia": "justos", "coverages_selected": selection}
    )
    assert preview.status_code == 200
    await db.refresh(job)
    assert job.premio_total == Decimal("100.00")
    assert "revisao_id" not in job.payload_resposta
    confirmation = preview.json()
    if scenario == "price_changed":
        provider.return_value["monthly"]["total"] = "251.00"
    elif scenario == "stale":
        job.payload_resposta = {**job.payload_resposta, "revisao_id": "other-operation"}
        await db.commit()
    elif scenario == "blocked":
        await control.record(
            db,
            quote,
            control.Actor(owner.id, owner.tenant_id, owner.papel),
            "transmissao.iniciada",
            uuid.uuid4(),
            "justos",
        )
        await db.commit()
    applied = await client.post(
        url,
        json={
            "cia": "justos",
            "coverages_selected": selection,
            "aplicar": True,
            "revisao_base": confirmation["revisao_base"],
            "monthly_confirmado": confirmation["monthly_total"],
            "annual_confirmado": confirmation["annual_total"],
        },
    )
    assert applied.status_code == (200 if scenario == "save" else 409)
    await db.refresh(job)
    entries = (
        (
            await db.execute(
                select(Auditoria).where(
                    Auditoria.tipo == "cotacao.coberturas_revisadas",
                    Auditoria.dados["cotacao_id"].astext == str(quote.id),
                )
            )
        )
        .scalars()
        .all()
    )
    if scenario == "save":
        assert job.premio_total == Decimal("250.00")
        assert job.payload_resposta["coverages_selected"] == selection
        assert job.payload_resposta["annual_total"] == "2700.00"
        assert (
            job.payload_resposta["condicoes_pagamento"]
            == applied.json()["condicoes_pagamento"]
        )
        assert len(entries) == 1 and entries[0].usuario_id == owner.id
        assert "private_field" not in json.dumps(entries[0].dados)
        comparison = await client.get(f"/cotacoes/{quote.id}/comparativo")
        assert comparison.json()[0]["coverages_selected"] == selection
        repeated = await client.post(
            url,
            json={
                "cia": "justos",
                "coverages_selected": selection,
                "aplicar": True,
                "revisao_base": confirmation["revisao_base"],
                "monthly_confirmado": "250.00",
                "annual_confirmado": "2700.00",
            },
        )
        assert repeated.status_code == 409
        adapter.transmitir.assert_not_awaited()
        monkeypatch.setattr(
            "app.api.proposta_router.get_adapter", lambda _: as_justos(adapter)
        )
        rejected = await client.post(
            f"/cotacoes/{quote.id}/transmitir",
            json={
                **body(),
                "cia": "justos",
                "revisao_base": applied.json()["revisao_base"],
                "dados_negocio": {"coverages_selected": {}},
            },
        )
        assert rejected.status_code == 409
        adapter.transmitir.assert_not_awaited()
        sent = await client.post(
            f"/cotacoes/{quote.id}/transmitir",
            json={
                **body(),
                "cia": "justos",
                "revisao_base": applied.json()["revisao_base"],
            },
        )
        assert sent.status_code == 201
        assert (
            adapter.transmitir.call_args.args[0].dados_negocio["coverages_selected"]
            == selection
        )
        assert Decimal(sent.json()["valor_parcela"]) == Decimal("250.00")
        adapter.transmitir.assert_awaited_once()
    else:
        assert job.premio_total == Decimal("100.00")
        assert not entries
        adapter.transmitir.assert_not_awaited()


async def test_transmission_uses_selected_insurer_price(
    db: AsyncSession, client: AsyncClient, adapter: AsyncMock
) -> None:
    _, quote = await setup(db, client)
    job = (
        await db.execute(select(CotacaoJob).where(CotacaoJob.cotacao_id == quote.id))
    ).scalar_one()
    job.premio_total = Decimal("275.40")
    db.add(
        CotacaoJob(
            cotacao_id=quote.id,
            cia="another-carrier",
            status="concluido",
            status_resultado="sucesso",
            premio_total=Decimal("100.00"),
            cotacao_id_cia="OTHER-SYNTHETIC",
        )
    )
    await db.commit()
    response = await client.post(f"/cotacoes/{quote.id}/transmitir", json=body())
    assert response.status_code == 201
    assert Decimal(response.json()["valor_parcela"]) == Decimal("275.40")
    assert Decimal(response.json()["comissao_parcela"]) == Decimal("41.31")
    adapter.transmitir.assert_awaited_once()
    assert adapter.transmitir.call_args.args[0].cotacao_id == "SYNTHETIC"


@pytest.mark.parametrize("invalid", ["missing", "recusada", "identifier", "price"])
async def test_selected_insurer_requires_own_valid_result(
    db: AsyncSession, client: AsyncClient, adapter: AsyncMock, invalid: str
) -> None:
    _, quote = await setup(db, client)
    job = (
        await db.execute(select(CotacaoJob).where(CotacaoJob.cotacao_id == quote.id))
    ).scalar_one()
    if invalid == "missing":
        job.cia = "another-carrier"
    elif invalid == "recusada":
        job.status_resultado = "recusada"
    elif invalid == "identifier":
        job.cotacao_id_cia = None
    else:
        job.premio_total = None
    await db.commit()
    response = await client.post(f"/cotacoes/{quote.id}/transmitir", json=body())
    assert response.status_code == 409
    adapter.transmitir.assert_not_awaited()
    state = await client.get(f"/transmissoes/cotacoes/{quote.id}")
    assert state.json()["estado"] == "sem_tentativa"


async def test_comissao_acima_do_teto_configuravel_e_recusada(
    db: AsyncSession, client: AsyncClient, adapter: AsyncMock
) -> None:
    _, quote = await setup(db, client)
    response = await client.post(
        f"/cotacoes/{quote.id}/transmitir",
        json={**body(), "comissao_pct": "0.35"},
    )
    assert response.status_code == 422
    adapter.transmitir.assert_not_awaited()


async def test_protocolo_longo_demais_nao_e_truncado(
    db: AsyncSession, client: AsyncClient, adapter: AsyncMock
) -> None:
    _, quote = await setup(db, client)
    adapter.transmitir.return_value = ResultadoTransmissao(True, "P" * 101)
    response = await client.post(f"/cotacoes/{quote.id}/transmitir", json=body())
    assert response.status_code == 502
    assert (
        await db.execute(
            select(func.count()).select_from(
                select(Proposta).where(Proposta.cotacao_id == quote.id).subquery()
            )
        )
    ).scalar_one() == 0


async def test_link_de_checkout_volta_sem_ser_persistido(
    db: AsyncSession, client: AsyncClient, adapter: AsyncMock
) -> None:
    _, quote = await setup(db, client)
    adapter.transmitir.return_value = ResultadoTransmissao(
        True, "Q-001", dados={"checkout_url": "https://app.justos.com.br/checkout/x"}
    )
    response = await client.post(f"/cotacoes/{quote.id}/transmitir", json=body())
    assert response.status_code == 201
    assert response.json()["link_checkout"] == "https://app.justos.com.br/checkout/x"
    proposta = (
        await db.execute(select(Proposta).where(Proposta.cotacao_id == quote.id))
    ).scalar_one()
    assert proposta.protocolo == "Q-001"
    assert "checkout" not in json.dumps(
        {c.name: str(getattr(proposta, c.name)) for c in Proposta.__table__.columns}
    )


def body() -> dict[str, object]:
    return {
        "opcao_pagamento": 0,
        "cia": "fake",
        "plano_pagamento": "AVISTA",
        "n_parcelas": 1,
        "comissao_pct": "0.15",
        "chave_idempotencia": str(uuid.uuid4()),
    }


async def uncertain(client: AsyncClient, quote: Cotacao, adapter: AsyncMock) -> dict:
    adapter.transmitir.side_effect = TimeoutError("synthetic-sensitive-provider-body")
    response = await client.post(f"/cotacoes/{quote.id}/transmitir", json=body())
    assert response.status_code == 502
    assert "synthetic-sensitive-provider-body" not in response.text
    state = await client.get(f"/transmissoes/cotacoes/{quote.id}")
    assert state.json()["estado"] == "incerta"
    return state.json()


def decision(state: dict, result: str = "nao_aceita") -> dict:
    return {
        "tentativa_id": state["tentativa_id"],
        "versao": state["versao"],
        "resultado": result,
        "conferido_na_seguradora": True,
        "justificativa": "Conferido no portal com dados sintéticos.",
        **({"referencia": "SYNTHETIC-REFERENCE"} if result == "aceita" else {}),
    }


async def test_same_key_replays_result_without_second_external_call(
    db: AsyncSession,
    client: AsyncClient,
    adapter: AsyncMock,
) -> None:
    _, quote = await setup(db, client)
    payload = body()
    first = await client.post(f"/cotacoes/{quote.id}/transmitir", json=payload)
    second = await client.post(f"/cotacoes/{quote.id}/transmitir", json=payload)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    changed = await client.post(
        f"/cotacoes/{quote.id}/transmitir", json={**payload, "n_parcelas": 2}
    )
    assert changed.status_code == 409
    new_key = await client.post(f"/cotacoes/{quote.id}/transmitir", json=body())
    assert new_key.status_code == 409
    assert adapter.transmitir.await_count == 1
    entries = list(
        (
            await db.execute(
                select(Auditoria)
                .where(
                    Auditoria.dados["cotacao_id"].astext == str(quote.id),
                    Auditoria.tipo.in_(control.TYPES),
                )
                .order_by(Auditoria.id)
            )
        ).scalars()
    )
    assert [entry.tipo for entry in entries] == [
        "transmissao.iniciada",
        "transmissao.concluida",
    ]
    assert "synthetic-risk-not-for-audit" not in json.dumps([e.dados for e in entries])


@pytest.mark.parametrize("profile", ["owner", "admin", "other", "foreign_admin"])
async def test_review_permissions_and_audit(
    db: AsyncSession,
    client: AsyncClient,
    adapter: AsyncMock,
    profile: str,
) -> None:
    owner, quote = await setup(db, client)
    state = await uncertain(client, quote, adapter)
    reviewer = owner
    if profile != "owner":
        reviewer = await criar_usuario(
            db,
            f"{uuid.uuid4()}@test.com",
            Papel.ADMIN if "admin" in profile else Papel.CORRETOR,
        )
        if profile == "foreign_admin":
            reviewer.tenant_id = uuid.uuid4()
        await db.commit()
        await login(client, reviewer)
    allowed = profile in ("owner", "admin")
    pending = await client.get("/transmissoes/pendentes")
    ids = [item["cotacao_id"] for item in pending.json()["items"]]
    assert (str(quote.id) in ids) == allowed
    response = await client.post(
        f"/transmissoes/cotacoes/{quote.id}/conferir", json=decision(state)
    )
    assert response.status_code == (200 if allowed else 404)
    entries = list(
        (
            await db.execute(
                select(Auditoria).where(
                    Auditoria.tipo == "transmissao.liberada",
                    Auditoria.dados["cotacao_id"].astext == str(quote.id),
                )
            )
        ).scalars()
    )
    assert len(entries) == (1 if allowed else 0)
    if allowed:
        assert entries[0].usuario_id == reviewer.id
        assert entries[0].tenant_id == quote.tenant_id
        assert entries[0].dados["justificativa"] == decision(state)["justificativa"]
    assert adapter.transmitir.await_count == 1  # Conferir nunca transmite.


async def test_release_requires_new_key_and_rejects_stale_decision(
    db: AsyncSession,
    client: AsyncClient,
    adapter: AsyncMock,
) -> None:
    _, quote = await setup(db, client)
    payload = body()
    adapter.transmitir.side_effect = TimeoutError("synthetic timeout")
    assert (
        await client.post(f"/cotacoes/{quote.id}/transmitir", json=payload)
    ).status_code == 502
    state = (await client.get(f"/transmissoes/cotacoes/{quote.id}")).json()
    review_url = f"/transmissoes/cotacoes/{quote.id}/conferir"
    assert (await client.post(review_url, json=decision(state))).status_code == 200
    assert (
        await client.post(review_url, json=decision(state, "aceita"))
    ).status_code == 409
    assert (
        await client.post(f"/cotacoes/{quote.id}/transmitir", json=payload)
    ).status_code == 409
    adapter.transmitir.side_effect = None
    assert (
        await client.post(f"/cotacoes/{quote.id}/transmitir", json=body())
    ).status_code == 201
    assert adapter.transmitir.await_count == 2


async def test_accepted_confirmation_blocks_retry_without_inventing_financial_record(
    db: AsyncSession,
    client: AsyncClient,
    adapter: AsyncMock,
) -> None:
    _, quote = await setup(db, client)
    state = await uncertain(client, quote, adapter)
    response = await client.post(
        f"/transmissoes/cotacoes/{quote.id}/conferir", json=decision(state, "aceita")
    )
    assert response.status_code == 200
    assert response.json()["estado"] == "confirmada"
    assert response.json()["bloqueada"] is True
    assert (
        await client.post(f"/cotacoes/{quote.id}/transmitir", json=body())
    ).status_code == 409
    count = (
        await db.execute(
            select(func.count())
            .select_from(Proposta)
            .where(Proposta.cotacao_id == quote.id)
        )
    ).scalar_one()
    assert count == 0
    assert adapter.transmitir.await_count == 1


async def test_in_flight_send_cannot_be_released_or_duplicated(
    db: AsyncSession,
    client: AsyncClient,
    adapter: AsyncMock,
) -> None:
    _, quote = await setup(db, client)
    started, release = asyncio.Event(), asyncio.Event()

    async def send(*_: object) -> ResultadoTransmissao:
        started.set()
        await release.wait()
        return ResultadoTransmissao(True, "SYNTHETIC-CONCURRENT")

    adapter.transmitir.side_effect = send
    task = asyncio.create_task(
        client.post(f"/cotacoes/{quote.id}/transmitir", json=body())
    )
    try:
        await asyncio.wait_for(started.wait(), 5)
        state = (await client.get(f"/transmissoes/cotacoes/{quote.id}")).json()
        assert state["estado"] == "iniciada"
        assert (
            await client.post(f"/cotacoes/{quote.id}/transmitir", json=body())
        ).status_code == 409
        result = await client.post(
            f"/transmissoes/cotacoes/{quote.id}/conferir", json=decision(state)
        )
        assert result.status_code == 409
    finally:
        release.set()
        response = await asyncio.wait_for(task, 5)
    assert response.status_code == 201
    assert adapter.transmitir.await_count == 1


async def test_completed_external_call_with_failed_persistence_stays_blocked(
    db: AsyncSession,
    client: AsyncClient,
    adapter: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, quote = await setup(db, client)
    original = control.record

    async def fail_final_record(*args: object, **kwargs: object) -> None:
        if args[3] == "transmissao.concluida":
            raise RuntimeError("synthetic persistence failure")
        await original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(control, "record", fail_final_record)
    response = await client.post(f"/cotacoes/{quote.id}/transmitir", json=body())
    assert response.status_code == 502
    assert (await client.get(f"/transmissoes/cotacoes/{quote.id}")).json()[
        "estado"
    ] == "incerta"
    assert (
        await client.post(f"/cotacoes/{quote.id}/transmitir", json=body())
    ).status_code == 409
    count = (
        await db.execute(
            select(func.count())
            .select_from(Proposta)
            .where(Proposta.cotacao_id == quote.id)
        )
    ).scalar_one()
    assert count == 0
    assert adapter.transmitir.await_count == 1


async def test_initial_audit_failure_prevents_external_call(
    db: AsyncSession,
    client: AsyncClient,
    adapter: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, quote = await setup(db, client)
    monkeypatch.setattr(
        control,
        "record",
        AsyncMock(side_effect=RuntimeError("synthetic audit failure")),
    )
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        await client.post(f"/cotacoes/{quote.id}/transmitir", json=body())
    assert adapter.transmitir.await_count == 0


async def test_transmission_restores_rls_context_after_initial_commit(
    db: AsyncSession,
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    _, quote = await setup(db, client)

    async def restricted_db() -> AsyncGenerator[AsyncSession, None]:
        async with engine.connect() as conn:
            await conn.execute(text("SET ROLE multik_app"))
            await conn.commit()
            try:
                async with AsyncSession(bind=conn, expire_on_commit=False) as session:
                    yield session
            finally:
                await conn.rollback()
                await conn.execute(text("RESET ROLE"))
                await conn.commit()

    app.dependency_overrides[get_db] = restricted_db
    try:
        response = await client.post(f"/cotacoes/{quote.id}/transmitir", json=body())
        assert response.status_code == 201
    finally:
        app.dependency_overrides.pop(get_db, None)
