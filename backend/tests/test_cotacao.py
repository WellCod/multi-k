"""Testes do endpoint de cotação."""

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.auth import Papel
from app.infra.models import CotacaoJob
from app.infra.worker import processar_job
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario

_DADOS_AUTO_BASE = {"codigo_fipe": "001004-9", "finalidade": "pessoal"}
_RISCO_AUTO = {
    "ramo": "auto",
    "dados": {**_DADOS_AUTO_BASE, "cep_pernoite": "13010001"},
}
_RISCO_AUTO_ERRO = {
    "ramo": "auto",
    "dados": {**_DADOS_AUTO_BASE, "cep_pernoite": "13010099"},
}
_RISCO_AUTO_RESTRICAO = {
    "ramo": "auto",
    "dados": {**_DADOS_AUTO_BASE, "cep_pernoite": "13010088"},
}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        c._auth = CsrfAuth(c.cookies)  # type: ignore[assignment]
        yield c


async def _login(client: AsyncClient, db: AsyncSession, email: str) -> AsyncClient:
    await criar_usuario(db, email, Papel.CORRETOR)
    await db.commit()
    r = await client.post("/auth/login", json={"email": email, "senha": "Senha@123"})
    assert r.status_code == 200
    return client


async def _processar_jobs_da_cotacao(
    cotacao_id: uuid.UUID,
    engine: AsyncEngine,
) -> None:
    """Processa synchronously os jobs pendentes para uma cotação nos testes."""
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as db:
        result = await db.execute(
            select(CotacaoJob).where(CotacaoJob.cotacao_id == cotacao_id)
        )
        jobs = result.scalars().all()
        job_data = [(j.id, j.cotacao_id) for j in jobs]

    for job_id, cot_id in job_data:
        await processar_job(job_id, cot_id, factory)


async def test_cotacao_sucesso(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_cot@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    assert r.status_code == 202
    body = r.json()
    cotacao_id = uuid.UUID(body["id"])
    assert body["status"] == "aguardando"

    await _processar_jobs_da_cotacao(cotacao_id, engine)

    r2 = await client.get(f"/cotacoes/{cotacao_id}")
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["status"] == "sucesso"
    assert body2["premio_total"] is not None
    assert body2["restricoes"] == []
    assert body2["necessita_vistoria"] is False


async def test_cotacao_restricao(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_res@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO_RESTRICAO)
    assert r.status_code == 202
    cotacao_id = uuid.UUID(r.json()["id"])

    await _processar_jobs_da_cotacao(cotacao_id, engine)

    r2 = await client.get(f"/cotacoes/{cotacao_id}")
    body = r2.json()
    assert body["status"] == "restricao"
    assert body["necessita_vistoria"] is True
    assert len(body["restricoes"]) > 0


async def test_cotacao_erro(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_err@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO_ERRO)
    assert r.status_code == 202
    cotacao_id = uuid.UUID(r.json()["id"])

    await _processar_jobs_da_cotacao(cotacao_id, engine)

    r2 = await client.get(f"/cotacoes/{cotacao_id}")
    body = r2.json()
    assert body["status"] == "erro"
    assert body["premio_total"] is None


async def test_cotacao_sem_auth(client: AsyncClient, engine: AsyncEngine) -> None:
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    assert r.status_code == 401


async def test_recotar(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_rec@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    cotacao_id = uuid.UUID(r.json()["id"])
    await _processar_jobs_da_cotacao(cotacao_id, engine)

    r2 = await client.post(f"/cotacoes/{cotacao_id}/recotar")
    assert r2.status_code == 202
    nova_id = uuid.UUID(r2.json()["id"])
    assert nova_id != cotacao_id

    await _processar_jobs_da_cotacao(nova_id, engine)

    r3 = await client.get(f"/cotacoes/{nova_id}")
    body = r3.json()
    assert body["status"] == "sucesso"
    assert body["versao_anterior_id"] == str(cotacao_id)


async def test_listar_cotacoes(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_list@test.com")
    await client.post("/cotacoes", json=_RISCO_AUTO)
    r = await client.get("/cotacoes")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


async def test_dominios_retorna_lista(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_dom@test.com")
    r = await client.get("/dominios")
    assert r.status_code == 200
    items = r.json()
    assert len(items) > 0
    assert all("tipo" in i and "codigo" in i and "descricao" in i for i in items)


async def test_dominios_filtro_tipo(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_domf@test.com")
    r = await client.get("/dominios", params={"tipo": "estado_civil"})
    assert r.status_code == 200
    items = r.json()
    assert len(items) > 0
    assert all(i["tipo"] == "estado_civil" for i in items)


async def test_dominios_sem_auth(client: AsyncClient, engine: AsyncEngine) -> None:
    r = await client.get("/dominios")
    assert r.status_code == 401


async def test_cotacao_preserva_cliente_id(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Cotação criada com cliente_id expõe esse vínculo no GET."""
    await _login(client, db, "corretor_clid@test.com")
    r_cli = await client.post(
        "/clientes", json={"nome": "Teste Vínculo", "cpf": "66666666666"}
    )
    assert r_cli.status_code == 201
    cliente_id = r_cli.json()["id"]

    r = await client.post(
        "/cotacoes",
        json={**_RISCO_AUTO, "cliente_id": cliente_id},
    )
    assert r.status_code == 202
    cotacao_id = r.json()["id"]

    r2 = await client.get(f"/cotacoes/{cotacao_id}")
    assert r2.json()["cliente_id"] == cliente_id


async def test_nova_cotacao_preserva_cliente_e_versao_anterior(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """POST /cotacoes com versao_anterior_id e cliente_id preserva ambos.

    Simula o fluxo do frontend após ?recotar=: o novo objeto tem vínculo ao
    cliente e à cotação original.
    """
    await _login(client, db, "corretor_recotar_cli@test.com")
    r_cli = await client.post(
        "/clientes", json={"nome": "Recotar Cliente", "cpf": "77777777777"}
    )
    cliente_id = r_cli.json()["id"]

    r_orig = await client.post(
        "/cotacoes", json={**_RISCO_AUTO, "cliente_id": cliente_id}
    )
    orig_id = r_orig.json()["id"]

    r_nova = await client.post(
        "/cotacoes",
        json={**_RISCO_AUTO, "cliente_id": cliente_id, "versao_anterior_id": orig_id},
    )
    assert r_nova.status_code == 202
    nova_id = r_nova.json()["id"]

    r3 = await client.get(f"/cotacoes/{nova_id}")
    body = r3.json()
    assert body["cliente_id"] == cliente_id
    assert body["versao_anterior_id"] == orig_id


async def test_cotacao_dados_risco_invalido_retorna_422(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """POST /cotacoes com dados_risco faltando campo obrigatório deve retornar 422."""
    await _login(client, db, "corretor_inv@test.com")
    r = await client.post(
        "/cotacoes",
        json={
            "ramo": "auto",
            "dados": {"cep_pernoite": "13010001"},
        },
    )
    assert r.status_code == 422


async def test_cotacao_ramo_invalido_retorna_422(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """POST /cotacoes com ramo fora do Literal deve retornar 422."""
    await _login(client, db, "corretor_ramo@test.com")
    r = await client.post(
        "/cotacoes",
        json={"ramo": "vida", "dados": {}},
    )
    assert r.status_code == 422


async def test_job_excecao_marca_cotacao_como_erro(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Se adapter.cotar lança exceção, job e cotação ficam com status 'erro'."""
    await _login(client, db, "corretor_exc@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    assert r.status_code == 202
    cotacao_id = uuid.UUID(r.json()["id"])

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as s:
        result = await s.execute(
            select(CotacaoJob).where(CotacaoJob.cotacao_id == cotacao_id)
        )
        job_data = [(j.id, j.cotacao_id) for j in result.scalars().all()]

    mock_adapter = AsyncMock()
    mock_adapter.cotar.side_effect = RuntimeError("adapter explodiu")

    with patch("app.infra.worker.get_adapter", return_value=mock_adapter):
        for job_id, cot_id in job_data:
            await processar_job(job_id, cot_id, factory)

    r2 = await client.get(f"/cotacoes/{cotacao_id}")
    assert r2.json()["status"] == "erro"


async def test_processar_job_inexistente_retorna_silenciosamente(
    engine: AsyncEngine,
) -> None:
    """processar_job com IDs inexistentes deve retornar sem levantar exceção."""
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    await processar_job(uuid.uuid4(), uuid.uuid4(), factory)


async def test_safe_processar_nao_propaga_excecao(engine: AsyncEngine) -> None:
    """_safe_processar não deve propagar exceções lançadas por processar_job."""
    from app.infra.worker import _safe_processar

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    with patch(
        "app.infra.worker.processar_job",
        side_effect=RuntimeError("erro inesperado"),
    ):
        await _safe_processar(uuid.uuid4(), uuid.uuid4(), factory)


async def test_start_worker_retorna_task_e_cancela(engine: AsyncEngine) -> None:
    """start_worker deve retornar asyncio.Task e terminar limpo ao ser cancelado."""
    from app.infra import worker

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    with patch.object(worker, "_POLL_INTERVAL", 0.001):
        task = worker.start_worker(factory)
        assert isinstance(task, asyncio.Task)
        await asyncio.sleep(0.01)
        task.cancel()
        done, _ = await asyncio.wait([task], timeout=2.0)
    assert task in done
    assert not task.cancelled()  # CancelledError capturado internamente pelo break


async def test_worker_loop_sem_jobs_cancela_limpo() -> None:
    """Sem jobs pendentes, _worker_loop dorme e encerra limpo ao ser cancelado."""
    from app.infra import worker

    class _EmptyResult:
        def scalar_one_or_none(self) -> None:
            return None

        def scalars(self) -> "_EmptyResult":
            return self

        def all(self) -> list:
            return []

    class _NullSession:
        async def __aenter__(self) -> "_NullSession":
            return self

        async def __aexit__(self, *_: object) -> bool:
            return False

        def begin(self) -> "_NullSession":
            return self

        async def execute(self, *_: object) -> _EmptyResult:
            return _EmptyResult()

    class _NullFactory:
        def __call__(self) -> _NullSession:
            return _NullSession()

    with patch.object(worker, "_POLL_INTERVAL", 0.001):
        task = asyncio.create_task(
            worker._worker_loop(_NullFactory())  # type: ignore[arg-type]
        )
        await asyncio.sleep(0.01)  # deixa o loop executar ao menos uma iteração
        task.cancel()
        done, _ = await asyncio.wait([task], timeout=2.0)

    assert task in done
    assert not task.cancelled()  # CancelledError capturado pelo break interno


async def test_exportar_historico_csv(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """GET /cotacoes/export/csv deve retornar CSV com header e linhas de dados."""
    await _login(client, db, "corretor_csv_hist@test.com")
    r_cot = await client.post("/cotacoes", json=_RISCO_AUTO)
    assert r_cot.status_code == 202

    r = await client.get("/cotacoes/export/csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    lines = r.text.strip().splitlines()
    assert "id" in lines[0]
    assert "ramo" in lines[0]
    assert len(lines) >= 2  # header + ao menos 1 cotação


async def test_cotacao_ramo_moto_valido(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """POST /cotacoes com ramo moto e dados válidos deve retornar 202."""
    await _login(client, db, "corretor_moto@test.com")
    r = await client.post(
        "/cotacoes",
        json={
            "ramo": "moto",
            "dados": {
                "codigo_fipe": "001004-9",
                "cep_pernoite": "13010001",
                "cilindrada": 250,
                "categoria": "esporte",
                "finalidade": "pessoal",
            },
        },
    )
    assert r.status_code == 202


async def test_cotacao_ramo_imovel_valido(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """POST /cotacoes com ramo imovel e dados válidos deve retornar 202."""
    await _login(client, db, "corretor_imovel@test.com")
    r = await client.post(
        "/cotacoes",
        json={
            "ramo": "imovel",
            "dados": {
                "cep": "13010001",
                "tipo_imovel": "apartamento",
                "tipo_construcao": "alvenaria",
            },
        },
    )
    assert r.status_code == 202


def test_cotacao_fim_vigencia_anterior_a_inicio_retorna_422() -> None:
    """CriarCotacaoInput com fim_vigencia <= inicio_vigencia deve falhar."""
    import pytest
    from pydantic import ValidationError

    from app.api.cotacao_router import CriarCotacaoInput

    with pytest.raises(ValidationError, match="fim_vigencia"):
        CriarCotacaoInput(
            ramo="auto",
            dados={
                "codigo_fipe": "001004-9",
                "cep_pernoite": "13010001",
                "finalidade": "pessoal",
                "inicio_vigencia": "2025-06-01",
                "fim_vigencia": "2025-05-01",
            },
        )


async def test_worker_loop_excecao_interna_capturada() -> None:
    """Exceção no DB é capturada; loop continua e encerra na iteração seguinte."""
    from app.infra import worker

    call_count = 0

    class _FakeCM:
        def __init__(self, exc: BaseException) -> None:
            self._exc = exc

        async def __aenter__(self) -> "_FakeCM":
            raise self._exc

        async def __aexit__(self, *_: object) -> bool:
            return False

    class _FakeFactory:
        def __call__(self) -> _FakeCM:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _FakeCM(RuntimeError("DB falhou"))
            return _FakeCM(asyncio.CancelledError())

    with patch.object(worker, "_POLL_INTERVAL", 0.001):
        task = asyncio.create_task(
            worker._worker_loop(_FakeFactory())  # type: ignore[arg-type]
        )
        done, _ = await asyncio.wait([task], timeout=3.0)

    assert task in done
    assert call_count >= 2
