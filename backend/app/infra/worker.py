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
from app.infra.models import ComissaoConfig, Cotacao, CotacaoJob

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
        if job.status_resultado == "cancelado":
            return
        ramo = cotacao.ramo
        dados_risco: dict[str, Any] = dict(cotacao.dados_risco)
        cia = job.cia
        # A comissão configurada entra no preço da seguradora; sem ela a
        # transmissão registraria um percentual que nunca foi cotado.
        if "comissao_pct" not in dados_risco:
            cfg = await db.get(ComissaoConfig, (cia, ramo))
            if cfg is not None:
                dados_risco["comissao_pct"] = str(cfg.pct_padrao)

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
                await db.execute(
                    select(CotacaoJob).where(CotacaoJob.id == job_id).with_for_update()
                )
            ).scalar_one()
            if jb.status_resultado == "cancelado":
                return
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

    except Exception:
        logger.error("worker_job_failed")
        async with factory() as db, db.begin():
            err_jb = (
                await db.execute(
                    select(CotacaoJob).where(CotacaoJob.id == job_id).with_for_update()
                )
            ).scalar_one_or_none()
            if err_jb is not None:
                if err_jb.status_resultado == "cancelado":
                    return
                err_jb.status = "erro"
                err_jb.processado_em = _utcnow()

    await _finalizar_cotacao(cotacao_id, factory)


async def _finalizar_cotacao(
    cotacao_id: uuid.UUID,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """Agrega resultados já gravados e notifica somente depois do commit."""
    async with factory() as db, db.begin():
        cot = (
            await db.execute(
                select(Cotacao).where(Cotacao.id == cotacao_id).with_for_update()
            )
        ).scalar_one_or_none()
        if cot is None:
            return
        jobs = list(
            (
                await db.execute(
                    select(CotacaoJob)
                    .where(CotacaoJob.cotacao_id == cotacao_id)
                    .order_by(CotacaoJob.criado_em, CotacaoJob.id)
                )
            ).scalars()
        )
        if not jobs or any(j.status not in ("concluido", "erro") for j in jobs):
            return
        states = {j.status_resultado for j in jobs if j.status == "concluido"}
        final_status = (
            "sucesso"
            if "sucesso" in states
            else "restricao"
            if "restricao" in states
            else "erro"
        )
        previous = (cot.status, cot.premio_total, cot.cotacao_id_cia)
        cot.status = final_status
        # Mantém a projeção legada, sem comparar prêmios de periodicidades distintas.
        representative = next(
            (j for j in jobs if j.status_resultado == final_status), None
        )
        if representative is not None:
            cot.cotacao_id_cia = representative.cotacao_id_cia
            cot.premio_total = representative.premio_total
            cot.restricoes = representative.restricoes
            cot.mensagens = representative.mensagens
            cot.necessita_vistoria = representative.necessita_vistoria
        if previous == (cot.status, cot.premio_total, cot.cotacao_id_cia):
            return
        uid = cot.usuario_id
        notification = {
            "tipo": "cotacao.pronta",
            "cotacao_id": str(cot.id),
            "status": cot.status,
            "premio_total": str(cot.premio_total)
            if cot.premio_total is not None
            else None,
        }
    events_bus.publish(uid, notification)


async def _safe_processar(
    job_id: uuid.UUID,
    cotacao_id: uuid.UUID,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        await processar_job(job_id, cotacao_id, factory)
    except Exception:
        logger.error("worker_job_unhandled_failure")


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
                        select(Cotacao).where(Cotacao.id.in_(cotacao_ids_a_processar))
                    )
                    for cot in cots_r.scalars().all():
                        if cot.status == "aguardando":
                            cot.status = "processando"

            if not jobs_batch:
                await asyncio.sleep(_POLL_INTERVAL)
                continue

            # Não reservar outro lote enquanto este ainda consome conexões externas.
            await asyncio.gather(
                *(
                    _safe_processar(job_id, cotacao_id, factory)
                    for job_id, cotacao_id in jobs_batch
                )
            )

        except asyncio.CancelledError:
            break
        except Exception:
            logger.error("worker_loop_failed")
            await asyncio.sleep(_POLL_INTERVAL)


def start_worker(factory: async_sessionmaker[AsyncSession]) -> "asyncio.Task[None]":
    return asyncio.create_task(_worker_loop(factory))
