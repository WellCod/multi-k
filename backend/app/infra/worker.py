"""Orquestrador de cotações — fila SKIP LOCKED no Postgres.

Sem Celery, sem Redis: a fila é a tabela cotacao_jobs.
O worker roda como asyncio.Task no lifespan do FastAPI.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.base import PortaSeguradora, RiscoCanonico
from app.adapters.fake.adapter import FakeSeguradora
from app.infra.models import Cotacao, CotacaoJob

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 1.0


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _get_adapter(cia: str) -> PortaSeguradora:
    # FASE 5: adicionar dispatch por cia aqui (registry de adapters)
    if cia == "fake":
        return FakeSeguradora()
    raise ValueError(f"Adapter desconhecido: {cia}")


async def processar_job(
    job_id: uuid.UUID,
    cotacao_id: uuid.UUID,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """Executa uma cotação: chama o adapter e persiste o resultado."""
    async with factory() as db:
        cot_r = await db.execute(select(Cotacao).where(Cotacao.id == cotacao_id))
        cotacao = cot_r.scalar_one_or_none()
        job_r = await db.execute(select(CotacaoJob).where(CotacaoJob.id == job_id))
        job = job_r.scalar_one_or_none()
        if cotacao is None or job is None:
            return
        ramo = cotacao.ramo
        dados_risco: dict[str, Any] = dict(cotacao.dados_risco)
        cia = job.cia

    adapter = _get_adapter(cia)
    risco = RiscoCanonico(ramo=ramo, dados=dados_risco)

    try:
        resultado = await adapter.cotar(risco)

        if resultado.sucesso and resultado.restricoes:
            status_final = "restricao"
        elif resultado.sucesso:
            status_final = "sucesso"
        else:
            status_final = "erro"

        async with factory() as db, db.begin():
            cot = (
                await db.execute(select(Cotacao).where(Cotacao.id == cotacao_id))
            ).scalar_one()
            cot.status = status_final
            cot.cotacao_id_cia = resultado.cotacao_id
            cot.premio_total = resultado.premio_total
            cot.restricoes = [
                {"codigo": r.codigo, "mensagem": r.mensagem}
                for r in resultado.restricoes
            ]
            cot.mensagens = list(resultado.mensagens)
            cot.necessita_vistoria = resultado.necessita_vistoria
            cot.payload_original = dict(resultado.payload_resposta)

            jb = (
                await db.execute(select(CotacaoJob).where(CotacaoJob.id == job_id))
            ).scalar_one()
            jb.status = "concluido"
            jb.processado_em = _utcnow()

    except Exception:
        logger.exception("Erro ao processar job %s", job_id)
        async with factory() as db, db.begin():
            err_cot = (
                await db.execute(select(Cotacao).where(Cotacao.id == cotacao_id))
            ).scalar_one_or_none()
            if err_cot is not None:
                err_cot.status = "erro"

            err_jb = (
                await db.execute(select(CotacaoJob).where(CotacaoJob.id == job_id))
            ).scalar_one_or_none()
            if err_jb is not None:
                err_jb.status = "erro"
                err_jb.processado_em = _utcnow()


async def _safe_processar(
    job_id: uuid.UUID,
    cotacao_id: uuid.UUID,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        await processar_job(job_id, cotacao_id, factory)
    except Exception:
        logger.exception("Exceção não tratada no job %s", job_id)


async def _worker_loop(factory: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            job_id: uuid.UUID | None = None
            cotacao_id: uuid.UUID | None = None

            async with factory() as db, db.begin():
                result = await db.execute(
                    select(CotacaoJob)
                    .where(CotacaoJob.status == "pendente")
                    .order_by(CotacaoJob.criado_em)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                job = result.scalar_one_or_none()
                if job is not None:
                    job_id = job.id
                    cotacao_id = job.cotacao_id
                    job.status = "processando"
                    job.tentativas += 1

                    cot_r = await db.execute(
                        select(Cotacao).where(Cotacao.id == cotacao_id)
                    )
                    cot = cot_r.scalar_one_or_none()
                    if cot is not None:
                        cot.status = "processando"

            if job_id is None or cotacao_id is None:
                await asyncio.sleep(_POLL_INTERVAL)
                continue

            asyncio.create_task(_safe_processar(job_id, cotacao_id, factory))

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Erro no worker loop")
            await asyncio.sleep(_POLL_INTERVAL)


def start_worker(factory: async_sessionmaker[AsyncSession]) -> "asyncio.Task[None]":
    return asyncio.create_task(_worker_loop(factory))
