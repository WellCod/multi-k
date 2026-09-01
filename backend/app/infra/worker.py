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

from app.adapters.base import RiscoCanonico
from app.adapters.registry import get_adapter
from app.infra import events_bus
from app.infra.models import Cotacao, CotacaoJob

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 1.0
_BATCH_SIZE = 5


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def processar_job(
    job_id: uuid.UUID,
    cotacao_id: uuid.UUID,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """Executa uma cotação: chama o adapter e persiste o resultado no job."""
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

    adapter = get_adapter(cia)
    risco = RiscoCanonico(ramo=ramo, dados=dados_risco)

    try:
        resultado = await adapter.cotar(risco)

        if resultado.sucesso and resultado.restricoes:
            status_resultado = "restricao"
        elif resultado.sucesso:
            status_resultado = "sucesso"
        else:
            status_resultado = "erro"

        async with factory() as db, db.begin():
            jb = (
                await db.execute(select(CotacaoJob).where(CotacaoJob.id == job_id))
            ).scalar_one()
            jb.status = "concluido"
            jb.processado_em = _utcnow()
            jb.cotacao_id_cia = resultado.cotacao_id
            jb.premio_total = resultado.premio_total
            jb.restricoes = [
                {"codigo": r.codigo, "mensagem": r.mensagem}
                for r in resultado.restricoes[:50]
            ]
            jb.mensagens = list(resultado.mensagens[:50])
            jb.necessita_vistoria = resultado.necessita_vistoria
            jb.status_resultado = status_resultado
            jb.payload_resposta = (
                dict(resultado.payload_resposta) if resultado.payload_resposta else None
            )

            # Check if all jobs for this cotacao are complete
            all_jobs = (
                (
                    await db.execute(
                        select(CotacaoJob).where(CotacaoJob.cotacao_id == cotacao_id)
                    )
                )
                .scalars()
                .all()
            )

            pending = [j for j in all_jobs if j.status not in ("concluido", "erro")]
            if not pending:
                # All done — compute best cotacao status
                resultados = [
                    j.status_resultado for j in all_jobs if j.status == "concluido"
                ]
                if "sucesso" in resultados:
                    cotacao_status = "sucesso"
                elif "restricao" in resultados:
                    cotacao_status = "restricao"
                else:
                    cotacao_status = "erro"

                cot = (
                    await db.execute(select(Cotacao).where(Cotacao.id == cotacao_id))
                ).scalar_one()
                cot.status = cotacao_status
                events_bus.publish(
                    cot.usuario_id,
                    {
                        "tipo": "cotacao.pronta",
                        "cotacao_id": str(cot.id),
                        "status": cotacao_status,
                        "premio_total": str(cot.premio_total) if cot.premio_total else None,
                    },
                )

                # For backwards-compat: store the "best" job's result on cotacao
                best_job = next(
                    (j for j in all_jobs if j.status_resultado == cotacao_status),
                    None,
                )
                if best_job:
                    cot.cotacao_id_cia = best_job.cotacao_id_cia
                    cot.premio_total = best_job.premio_total
                    cot.restricoes = best_job.restricoes
                    cot.mensagens = best_job.mensagens
                    cot.necessita_vistoria = best_job.necessita_vistoria

    except Exception:
        logger.exception("Erro ao processar job %s", job_id)
        async with factory() as db, db.begin():
            err_jb = (
                await db.execute(select(CotacaoJob).where(CotacaoJob.id == job_id))
            ).scalar_one_or_none()
            if err_jb is not None:
                err_jb.status = "erro"
                err_jb.processado_em = _utcnow()

            # Check if all jobs are done after marking this one as erro
            all_jobs_err = (
                (
                    await db.execute(
                        select(CotacaoJob).where(CotacaoJob.cotacao_id == cotacao_id)
                    )
                )
                .scalars()
                .all()
            )

            pending_err = [
                j for j in all_jobs_err if j.status not in ("concluido", "erro")
            ]
            if not pending_err:
                resultados_err = [
                    j.status_resultado for j in all_jobs_err if j.status == "concluido"
                ]
                if "sucesso" in resultados_err:
                    cotacao_status_err = "sucesso"
                elif "restricao" in resultados_err:
                    cotacao_status_err = "restricao"
                else:
                    cotacao_status_err = "erro"

                err_cot = (
                    await db.execute(select(Cotacao).where(Cotacao.id == cotacao_id))
                ).scalar_one_or_none()
                if err_cot is not None:
                    err_cot.status = cotacao_status_err
                    events_bus.publish(
                        err_cot.usuario_id,
                        {
                            "tipo": "cotacao.pronta",
                            "cotacao_id": str(err_cot.id),
                            "status": cotacao_status_err,
                            "premio_total": str(err_cot.premio_total) if err_cot.premio_total else None,
                        },
                    )

                    best_job_err = next(
                        (
                            j
                            for j in all_jobs_err
                            if j.status_resultado == cotacao_status_err
                        ),
                        None,
                    )
                    if best_job_err:
                        err_cot.cotacao_id_cia = best_job_err.cotacao_id_cia
                        err_cot.premio_total = best_job_err.premio_total
                        err_cot.restricoes = best_job_err.restricoes
                        err_cot.mensagens = best_job_err.mensagens
                        err_cot.necessita_vistoria = best_job_err.necessita_vistoria


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
            jobs_batch: list[tuple[uuid.UUID, uuid.UUID]] = []

            async with factory() as db, db.begin():
                result = await db.execute(
                    select(CotacaoJob)
                    .where(CotacaoJob.status == "pendente")
                    .order_by(CotacaoJob.criado_em)
                    .limit(_BATCH_SIZE)
                    .with_for_update(skip_locked=True)
                )
                jobs = result.scalars().all()
                cotacao_ids_a_processar: set[uuid.UUID] = set()
                for job in jobs:
                    job.status = "processando"
                    job.tentativas += 1
                    jobs_batch.append((job.id, job.cotacao_id))
                    cotacao_ids_a_processar.add(job.cotacao_id)

                if cotacao_ids_a_processar:
                    cots_r = await db.execute(
                        select(Cotacao).where(
                            Cotacao.id.in_(cotacao_ids_a_processar)
                        )
                    )
                    for cot in cots_r.scalars().all():
                        if cot.status == "aguardando":
                            cot.status = "processando"

            if not jobs_batch:
                await asyncio.sleep(_POLL_INTERVAL)
                continue

            for job_id, cotacao_id in jobs_batch:
                asyncio.create_task(_safe_processar(job_id, cotacao_id, factory))

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Erro no worker loop")
            await asyncio.sleep(_POLL_INTERVAL)


def start_worker(factory: async_sessionmaker[AsyncSession]) -> "asyncio.Task[None]":
    return asyncio.create_task(_worker_loop(factory))
