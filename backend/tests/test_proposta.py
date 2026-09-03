"""Testes de transmissão de proposta e endpoints relacionados."""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapters.fake.adapter import FakeSeguradora
from app.api.proposta_router import _adapter_dep
from app.domain.auth import Papel
from app.infra.models import CotacaoJob
from app.infra.worker import processar_job
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario

_RISCO_AUTO = {
    "ramo": "auto",
    "dados": {
        "cep_pernoite": "13010001",
        "codigo_fipe": "001004-9",
        "finalidade": "pessoal",
    },
}

_TRANSMITIR_BODY = {
    "plano_pagamento": "AVISTA",
    "n_parcelas": 1,
    "comissao_pct": "0.1500",
    "inicio_vigencia": str(date.today()),
}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    # Substitui o adapter por FakeSeguradora sem latência nos testes
    app.dependency_overrides[_adapter_dep] = lambda: FakeSeguradora(0, 0)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        c._auth = CsrfAuth(c.cookies)  # type: ignore[assignment]
        yield c
    app.dependency_overrides.clear()


async def _login(client: AsyncClient, db: AsyncSession, email: str) -> AsyncClient:
    await criar_usuario(db, email, Papel.CORRETOR)
    await db.commit()
    r = await client.post("/auth/login", json={"email": email, "senha": "Senha@123"})
    assert r.status_code == 200
    return client


async def _processar_jobs(cotacao_id: uuid.UUID, engine: AsyncEngine) -> None:
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as db:
        result = await db.execute(
            select(CotacaoJob).where(CotacaoJob.cotacao_id == cotacao_id)
        )
        job_data = [(j.id, j.cotacao_id) for j in result.scalars().all()]
    for job_id, cot_id in job_data:
        await processar_job(job_id, cot_id, factory)


async def _criar_cotacao_processada(
    client: AsyncClient, db: AsyncSession, engine: AsyncEngine, email: str
) -> uuid.UUID:
    await _login(client, db, email)
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    assert r.status_code == 202
    cotacao_id = uuid.UUID(r.json()["id"])
    await _processar_jobs(cotacao_id, engine)
    return cotacao_id


async def test_transmitir_sucesso(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_tx@test.com"
    )

    r = await client.post(f"/cotacoes/{cotacao_id}/transmitir", json=_TRANSMITIR_BODY)
    assert r.status_code == 201
    body = r.json()
    assert body["protocolo"].startswith("FAKE-")
    assert body["cotacao_id"] == str(cotacao_id)
    assert body["n_parcelas"] == 1
    assert float(body["valor_parcela"]) > 0
    assert float(body["comissao_parcela"]) > 0


async def test_transmitir_cotacao_aguardando_falha(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_txaw@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    cotacao_id = r.json()["id"]
    # Cotação ainda "aguardando" — não pode transmitir
    r2 = await client.post(f"/cotacoes/{cotacao_id}/transmitir", json=_TRANSMITIR_BODY)
    assert r2.status_code == 422


async def test_transmitir_cotacao_outro_usuario(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_owner@test.com"
    )
    # Loga como outro corretor
    await criar_usuario(db, "corretor_intruso@test.com", Papel.CORRETOR)
    await db.commit()
    r = await client.post(
        "/auth/login",
        json={"email": "corretor_intruso@test.com", "senha": "Senha@123"},
    )
    assert r.status_code == 200
    r2 = await client.post(f"/cotacoes/{cotacao_id}/transmitir", json=_TRANSMITIR_BODY)
    assert r2.status_code == 404


async def test_obter_proposta(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_gp@test.com"
    )
    r_tx = await client.post(
        f"/cotacoes/{cotacao_id}/transmitir", json=_TRANSMITIR_BODY
    )
    assert r_tx.status_code == 201
    proposta_id = r_tx.json()["id"]

    r = await client.get(f"/propostas/{proposta_id}")
    assert r.status_code == 200
    assert r.json()["protocolo"] == r_tx.json()["protocolo"]


async def test_parcelas(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_parc@test.com"
    )
    body_3x = {**_TRANSMITIR_BODY, "n_parcelas": 3, "plano_pagamento": "3X"}
    r_tx = await client.post(f"/cotacoes/{cotacao_id}/transmitir", json=body_3x)
    assert r_tx.status_code == 201
    proposta_id = r_tx.json()["id"]

    r = await client.get(f"/propostas/{proposta_id}/parcelas")
    assert r.status_code == 200
    parcelas = r.json()
    assert len(parcelas) == 3
    assert parcelas[0]["numero"] == 1
    assert parcelas[1]["numero"] == 2
    assert parcelas[2]["numero"] == 3
    # Primeira parcela no dia de inicio_vigencia
    assert parcelas[0]["vencimento"] == str(date.today())


async def test_comparativo_json(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_comp@test.com"
    )
    r = await client.get(f"/cotacoes/{cotacao_id}/comparativo")
    assert r.status_code == 200
    itens = r.json()
    assert len(itens) >= 1
    assert "premio_total" in itens[0]
    assert "cia" in itens[0]


async def test_comparativo_estrutura_por_job(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Comparativo retorna resultado por CotacaoJob com todos os campos esperados."""
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_comp2@test.com"
    )
    r = await client.get(f"/cotacoes/{cotacao_id}/comparativo")
    assert r.status_code == 200
    itens = r.json()
    assert len(itens) == 1

    item = itens[0]
    assert item["cia"] == "fake"
    assert item["status"] == "sucesso"
    assert item["premio_total"] == "1950.00"
    assert item["annual_total"] == "21060.00"
    assert item["necessita_vistoria"] is False
    assert item["restricoes"] == []
    assert item["mensagens"] == []
    assert item["cotacao_id_cia"] is not None


async def test_comparativo_pdf(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_pdf@test.com"
    )
    r = await client.get(f"/cotacoes/{cotacao_id}/comparativo/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert len(r.content) > 100


async def test_renovacoes_vazio(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_ren@test.com")
    r = await client.get("/renovacoes")
    assert r.status_code == 200
    assert r.json() == []


async def test_renovacoes_janelas(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Proposta com vigência expirando em ≤30 dias aparece na janela D30."""
    from datetime import timedelta

    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_ren2@test.com"
    )
    # inicio_vigencia 335 dias atrás → fim = hoje + 30 dias → D30
    inicio = date.today() - timedelta(days=335)
    r_tx = await client.post(
        f"/cotacoes/{cotacao_id}/transmitir",
        json={**_TRANSMITIR_BODY, "inicio_vigencia": str(inicio)},
    )
    assert r_tx.status_code == 201

    r = await client.get("/renovacoes")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    item = items[0]
    assert item["janela"] == "D30"
    assert item["dias_para_vencer"] <= 30


async def test_renovacoes_janela_d45(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Proposta com vigência expirando em 31–45 dias aparece na janela D45."""
    from datetime import timedelta

    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_ren3@test.com"
    )
    inicio = date.today() - timedelta(days=322)  # fim = hoje + 43 dias
    r_tx = await client.post(
        f"/cotacoes/{cotacao_id}/transmitir",
        json={**_TRANSMITIR_BODY, "inicio_vigencia": str(inicio)},
    )
    assert r_tx.status_code == 201

    r = await client.get("/renovacoes")
    assert r.status_code == 200
    items = r.json()
    assert any(i["janela"] == "D45" for i in items)


async def test_renovacoes_janela_d60(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Proposta com vigência expirando em 46–60 dias aparece na janela D60."""
    from datetime import timedelta

    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_ren4@test.com"
    )
    inicio = date.today() - timedelta(days=305)  # fim = hoje + 60 dias
    r_tx = await client.post(
        f"/cotacoes/{cotacao_id}/transmitir",
        json={**_TRANSMITIR_BODY, "inicio_vigencia": str(inicio)},
    )
    assert r_tx.status_code == 201

    r = await client.get("/renovacoes")
    assert r.status_code == 200
    items = r.json()
    assert any(i["janela"] == "D60" for i in items)


async def test_cotacao_expoe_proposta_id(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """CotacaoOut.proposta_id é None antes de transmitir e preenchido depois."""
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_pid@test.com"
    )

    r_antes = await client.get(f"/cotacoes/{cotacao_id}")
    assert r_antes.status_code == 200
    assert r_antes.json()["proposta_id"] is None

    r_tx = await client.post(
        f"/cotacoes/{cotacao_id}/transmitir", json=_TRANSMITIR_BODY
    )
    assert r_tx.status_code == 201
    proposta_id = r_tx.json()["id"]

    r_depois = await client.get(f"/cotacoes/{cotacao_id}")
    assert r_depois.status_code == 200
    assert r_depois.json()["proposta_id"] == proposta_id


async def test_listar_cotacoes_proposta_id(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """GET /cotacoes lista também expõe proposta_id por item."""
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_listpid@test.com"
    )

    r_lista = await client.get("/cotacoes")
    assert r_lista.status_code == 200
    item = next(c for c in r_lista.json()["items"] if c["id"] == str(cotacao_id))
    assert item["proposta_id"] is None

    r_tx = await client.post(
        f"/cotacoes/{cotacao_id}/transmitir", json=_TRANSMITIR_BODY
    )
    proposta_id = r_tx.json()["id"]

    r_lista2 = await client.get("/cotacoes")
    item2 = next(c for c in r_lista2.json()["items"] if c["id"] == str(cotacao_id))
    assert item2["proposta_id"] == proposta_id


@pytest.mark.parametrize("sem_auth", [True])
async def test_transmitir_sem_auth(
    client: AsyncClient, engine: AsyncEngine, sem_auth: bool
) -> None:
    r = await client.post(f"/cotacoes/{uuid.uuid4()}/transmitir", json=_TRANSMITIR_BODY)
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# comparativo_router — caminhos não cobertos
# ---------------------------------------------------------------------------


async def test_comparativo_404_cotacao_invalida(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """GET /comparativo com UUID inexistente deve retornar 404."""
    await _login(client, db, "corretor_comp404@test.com")
    r = await client.get(f"/cotacoes/{uuid.uuid4()}/comparativo")
    assert r.status_code == 404


async def test_comparativo_sem_jobs_concluidos_retorna_lista_vazia(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Cotação sem jobs concluídos deve retornar lista vazia."""
    await _login(client, db, "corretor_comp_nojob@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    assert r.status_code == 202
    cotacao_id = r.json()["id"]
    r2 = await client.get(f"/cotacoes/{cotacao_id}/comparativo")
    assert r2.status_code == 200
    assert r2.json() == []


async def test_comparativo_pdf_sem_jobs_retorna_pdf(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """PDF com cotação sem jobs concluídos deve renderizar 'Nenhum resultado'."""
    await _login(client, db, "corretor_pdf_nojob@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    assert r.status_code == 202
    cotacao_id = r.json()["id"]
    r2 = await client.get(f"/cotacoes/{cotacao_id}/comparativo/pdf")
    assert r2.status_code == 200
    assert r2.headers["content-type"] == "application/pdf"


def test_annual_total_none_quando_raw_ausente() -> None:
    """_annual_total deve retornar None quando payload não tem annual_total."""
    from unittest.mock import MagicMock

    from app.api.comparativo_router import _annual_total

    job = MagicMock()
    job.payload_resposta = {}
    assert _annual_total(job) is None


def test_annual_total_none_quando_valor_invalido() -> None:
    """_annual_total deve retornar None quando annual_total não é Decimal."""
    from unittest.mock import MagicMock

    from app.api.comparativo_router import _annual_total

    job = MagicMock()
    job.payload_resposta = {"annual_total": "nao-e-numero"}
    assert _annual_total(job) is None


async def test_transmitir_adapter_retorna_502(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Quando adapter.transmitir retorna sucesso=False, deve retornar 502."""
    from unittest.mock import AsyncMock

    from app.adapters.base import ResultadoTransmissao
    from app.api.proposta_router import _adapter_dep

    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_tx502@test.com"
    )

    fake_fail = AsyncMock()
    fake_fail.transmitir = AsyncMock(
        return_value=ResultadoTransmissao(
            sucesso=False, protocolo=None, mensagens=["Erro simulado"]
        )
    )
    app.dependency_overrides[_adapter_dep] = lambda: fake_fail
    try:
        r = await client.post(
            f"/cotacoes/{cotacao_id}/transmitir", json=_TRANSMITIR_BODY
        )
        assert r.status_code == 502
    finally:
        app.dependency_overrides.clear()


async def test_parcelas_sem_inicio_vigencia_retorna_none(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Proposta sem inicio_vigencia deve ter vencimento=None em cada parcela."""
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_parc_niv@test.com"
    )
    body_sem_inicio = {
        "plano_pagamento": "AVISTA",
        "n_parcelas": 2,
        "comissao_pct": "0.1500",
        # sem inicio_vigencia
    }
    r_tx = await client.post(f"/cotacoes/{cotacao_id}/transmitir", json=body_sem_inicio)
    assert r_tx.status_code == 201
    proposta_id = r_tx.json()["id"]

    r = await client.get(f"/propostas/{proposta_id}/parcelas")
    assert r.status_code == 200
    parcelas = r.json()
    assert len(parcelas) == 2
    for p in parcelas:
        assert p["vencimento"] is None


def test_m4_dados_negocio_nao_serializavel_levanta_validation_error() -> None:
    """dados_negocio com valor não-JSON-serializável deve levantar ValidationError."""
    from decimal import Decimal

    import pytest
    from pydantic import ValidationError

    from app.api.proposta_router import TransmitirInput

    with pytest.raises(ValidationError, match="serializáveis"):
        TransmitirInput(
            plano_pagamento="mensal",
            n_parcelas=1,
            comissao_pct=Decimal("0.05"),
            dados_negocio={"chave": object()},
        )


# ---------------------------------------------------------------------------
# PATCH /propostas/{id}/apolice
# ---------------------------------------------------------------------------


async def test_vincular_apolice(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_apo@test.com"
    )
    r_tx = await client.post(
        f"/cotacoes/{cotacao_id}/transmitir", json=_TRANSMITIR_BODY
    )
    assert r_tx.status_code == 201
    proposta_id = r_tx.json()["id"]

    r = await client.patch(
        f"/propostas/{proposta_id}/apolice",
        json={"numero_apolice": "APOLICE-001"},
    )
    assert r.status_code == 200
    assert r.json()["numero_apolice"] == "APOLICE-001"


async def test_vincular_apolice_ja_existente_retorna_409(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_apo2@test.com"
    )
    r_tx = await client.post(
        f"/cotacoes/{cotacao_id}/transmitir", json=_TRANSMITIR_BODY
    )
    assert r_tx.status_code == 201
    proposta_id = r_tx.json()["id"]

    await client.patch(
        f"/propostas/{proposta_id}/apolice",
        json={"numero_apolice": "APOLICE-001"},
    )
    r = await client.patch(
        f"/propostas/{proposta_id}/apolice",
        json={"numero_apolice": "APOLICE-002"},
    )
    assert r.status_code == 409


async def test_vincular_apolice_proposta_nao_encontrada_retorna_404(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_apo404@test.com")
    r = await client.patch(
        f"/propostas/{uuid.uuid4()}/apolice",
        json={"numero_apolice": "APOLICE-X"},
    )
    assert r.status_code == 404
