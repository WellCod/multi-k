"""Regression coverage for partial results and encrypted, owned drafts."""
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.comparativo_router import _build_itens, _comparison_coverages, _coverage_options
from app.domain.auth import Papel
from app.infra.models import Cotacao, CotacaoJob
from app.infra.worker import processar_job
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario


@pytest.mark.parametrize("states", [
    ["sucesso"],
    ["sucesso", "restricao", "erro", "processando"],
    ["erro", "erro", "erro", "erro"],
    ["sucesso", "erro", "erro", "erro"],
])
def test_every_carrier_survives_partial_and_failed_results(states: list[str]) -> None:
    jobs = [CotacaoJob(cia=f"test-{i}", status="processando" if state == "processando" else "concluido",
            status_resultado=None if state == "processando" else state,
            criado_em=datetime.now(UTC), premio_total=Decimal("1234.56") if state == "sucesso" else None,
            necessita_vistoria=False, restricoes=[], mensagens=[], payload_resposta=None)
            for i, state in enumerate(states)]
    items = _build_itens(Cotacao(), jobs)
    assert [item.status for item in items] == states
    assert len(items) == len(jobs)
    assert all(item.iniciado_em for item in items)


def test_missing_coverage_money_is_not_zero() -> None:
    job = CotacaoJob(cia="test", payload_resposta={
        "coverages_available": {"test": {"name": "Cobertura", "peril_options": [
            {"slug": "selected", "price": "0", "deductible": None},
        ]}},
        "coverages_selected": {"test": "selected"},
    })
    options = _coverage_options(job)
    assert options is not None
    option = options["test"]["peril_options"][0]
    assert option["price"] == "0.00"
    assert option["deductible"] is None
    assert option["coverage_amount"] is None
    assert _comparison_coverages(job)[0]["limite"] is None
    assert _comparison_coverages(job, {}) == []
    assert _comparison_coverages(job, {"test": None}) == []
    assert len(_comparison_coverages(job)) == 1


def test_worker_errors_are_not_hidden() -> None:
    job = CotacaoJob(cia="test", status="erro", status_resultado=None, criado_em=datetime.now(UTC),
                    necessita_vistoria=False, restricoes=[], mensagens=[], payload_resposta=None)
    assert _build_itens(Cotacao(), [job])[0].status == "erro"


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        value._auth = CsrfAuth(value.cookies)
        yield value


async def test_draft_roundtrip_encryption_and_conflict(db: AsyncSession, client: AsyncClient) -> None:
    user = await criar_usuario(db, "draft-ui@test.com", Papel.CORRETOR)
    await db.commit()
    assert (await client.post("/auth/login", json={"email": user.email, "senha": "Senha@123"})).status_code == 200
    body = {"versao": 0, "dados": {"ramo": "auto", "step": 2, "step1": {"nome": "Teste exclusivo do rascunho"}}}
    saved = await client.put("/rascunhos/cotacao", json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["versao"] == 1
    read = await client.get("/rascunhos/cotacao")
    assert read.json()["dados"] == body["dados"]
    assert read.headers["cache-control"] == "no-store"
    stored = (await db.execute(text("SELECT dados FROM rascunhos_cotacao WHERE usuario_id = :id"), {"id": user.id})).scalar_one()
    assert "Teste exclusivo" not in stored
    assert (await client.put("/rascunhos/cotacao", json=body)).status_code == 409
    assert (await client.delete("/rascunhos/cotacao")).status_code == 204
    assert (await client.get("/rascunhos/cotacao")).json()["dados"] is None


async def test_cancelled_job_never_calls_adapter(db: AsyncSession, client: AsyncClient, engine: AsyncEngine) -> None:
    user = await criar_usuario(db, "cancel-ui@test.com", Papel.CORRETOR)
    await db.commit()
    await client.post("/auth/login", json={"email": user.email, "senha": "Senha@123"})
    created = await client.post("/cotacoes", json={"ramo": "auto", "dados": {"codigo_fipe": "test", "finalidade": "pessoal", "cep_pernoite": "00000000"}})
    assert created.status_code == 202, created.text
    quote_id = uuid.UUID(created.json()["id"])
    cancelled = await client.post(f"/cotacoes/{quote_id}/cancelar", json={})
    assert cancelled.status_code == 204, cancelled.text
    jobs = list((await db.execute(select(CotacaoJob).where(CotacaoJob.cotacao_id == quote_id))).scalars())
    factory = async_sessionmaker(engine, expire_on_commit=False)
    with patch("app.infra.worker.get_adapter") as get_adapter:
        for job in jobs:
            await processar_job(job.id, quote_id, factory)
        get_adapter.assert_not_called()
    items = (await client.get(f"/cotacoes/{quote_id}/comparativo")).json()
    assert items and all(item["status"] == "cancelado" for item in items)
