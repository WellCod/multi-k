"""Rotas de proposta — transmissão, consulta e parcelas."""

import hashlib
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import (
    CondicaoTransmissaoError,
    PortaSeguradora,
    PreparadorTransmissao,
    PropostaCanonica,
    RiscoCanonico,
    SelecaoTransmissao,
)
from app.adapters.registry import get_adapter
from app.api._utils import get_or_404
from app.api.deps import CurrentUser
from app.infra import audit
from app.infra import transmission_control as transmission
from app.infra.db import get_db
from app.infra.models import Auditoria, CotacaoJob, EventoDB, Proposta
from app.infra.quote_revision import quote_revision

router = APIRouter(tags=["propostas"])


# ---------------------------------------------------------------------------
# Dependência injetável — sobrescrita nos testes com FakeSeguradora(0, 0)
# ---------------------------------------------------------------------------


def _adapter_dep() -> PortaSeguradora:
    return get_adapter("fake")


AdapterDep = Annotated[PortaSeguradora, Depends(_adapter_dep)]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TransmitirInput(BaseModel):
    plano_pagamento: str
    n_parcelas: int = Field(ge=1, le=12)
    # Teto igual ao da configuração de comissão (admin): 30%.
    comissao_pct: Decimal = Field(gt=0, le=Decimal("0.30"))
    inicio_vigencia: date | None = None
    dados_negocio: dict[str, Any] = Field(default_factory=dict)
    cia: str = "fake"
    chave_idempotencia: uuid.UUID = Field(default_factory=uuid.uuid4)
    revisao_base: str | None = Field(default=None, min_length=64, max_length=64)
    opcao_pagamento: int | None = Field(default=None, ge=0, strict=True)

    @field_validator("dados_negocio")
    @classmethod
    def _validar_negocio(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(v) > 50:
            raise ValueError("dados_negocio excede 50 chaves")
        try:
            payload = json.dumps(v)
        except (TypeError, ValueError) as e:
            raise ValueError("dados_negocio contém valores não serializáveis") from e
        if len(payload) > 10_000:
            raise ValueError("dados_negocio excede 10 KB")
        return v


class PropostaOut(BaseModel):
    id: uuid.UUID
    cotacao_id: uuid.UUID
    protocolo: str
    plano_pagamento: str
    n_parcelas: int
    valor_parcela: Decimal
    comissao_parcela: Decimal
    comissao_pct: Decimal
    inicio_vigencia: date | None
    transmitida_em: str
    numero_apolice: str | None = None
    # Link volátil da seguradora: devolvido na transmissão, nunca persistido.
    link_checkout: str | None = None


class ParcelaOut(BaseModel):
    numero: int
    vencimento: date | None
    valor: Decimal
    comissao: Decimal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _proposta_out(p: Proposta, link_checkout: str | None = None) -> PropostaOut:
    return PropostaOut(
        id=p.id,
        cotacao_id=p.cotacao_id,
        protocolo=p.protocolo,
        plano_pagamento=p.plano_pagamento,
        n_parcelas=p.n_parcelas,
        valor_parcela=p.valor_parcela,
        comissao_parcela=p.comissao_parcela,
        comissao_pct=p.comissao_pct,
        inicio_vigencia=p.inicio_vigencia,
        transmitida_em=p.transmitida_em.isoformat(),
        numero_apolice=p.numero_apolice,
        link_checkout=link_checkout,
    )


async def _get_proposta_ou_404(
    proposta_id: uuid.UUID, usuario_id: uuid.UUID, db: AsyncSession
) -> Proposta:
    stmt = (
        select(Proposta)
        .where(Proposta.id == proposta_id)
        .where(Proposta.usuario_id == usuario_id)
    )
    return await get_or_404(stmt, db, "Proposta não encontrada.")


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------


@router.post(
    "/cotacoes/{cotacao_id}/transmitir",
    response_model=PropostaOut,
    status_code=201,
)
async def transmitir(
    cotacao_id: uuid.UUID,
    body: TransmitirInput,
    request: Request,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    _default_adapter: AdapterDep,
) -> PropostaOut:
    """Transmite uma vez; resultado indefinido exige conferência auditada."""
    actor = transmission.Actor(usuario.id, usuario.tenant_id, usuario.papel)
    cotacao = await transmission.quote_for_user(db, cotacao_id, actor, lock=True)
    fingerprint = hashlib.sha256(
        json.dumps(
            body.model_dump(mode="json", exclude={"chave_idempotencia"}), sort_keys=True
        ).encode()
    ).hexdigest()
    previous = await transmission.latest(db, cotacao)
    used_key = (
        await db.execute(
            select(Auditoria)
            .where(
                Auditoria.tipo == "transmissao.iniciada",
                Auditoria.tenant_id == actor.tenant_id,
                Auditoria.dados["cotacao_id"].astext == str(cotacao_id),
                Auditoria.dados["chave_idempotencia"].astext
                == str(body.chave_idempotencia),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    existing = (
        await db.execute(
            select(Proposta)
            .where(
                Proposta.cotacao_id == cotacao_id,
                Proposta.usuario_id == actor.id,
                Proposta.tenant_id == actor.tenant_id,
            )
            .order_by(Proposta.transmitida_em.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if (
        used_key is not None
        and existing is not None
        and previous is not None
        and previous.tipo == "transmissao.concluida"
        and previous.dados.get("tentativa_id") == used_key.dados.get("tentativa_id")
        and used_key.dados.get("fingerprint") == fingerprint
    ):
        return _proposta_out(existing)
    if used_key is not None:
        raise HTTPException(
            409, "Esta tentativa já foi registrada. Atualize a conferência."
        )
    if existing is not None:
        raise HTTPException(
            409, "Já existe uma proposta para esta cotação. Não reenvie."
        )
    if previous is not None and previous.tipo != "transmissao.liberada":
        raise HTTPException(
            409,
            "Transmissão bloqueada. Confira o resultado na seguradora "
            "e registre a decisão antes de uma nova tentativa.",
        )
    if cotacao.status not in ("sucesso", "restricao"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Status '{cotacao.status}' não permite transmissão.",
        )
    if cotacao.premio_total is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cotação sem prêmio calculado.",
        )

    # _default_adapter é usado apenas para "fake" (sobrescrito nos testes).
    # CIAs reais usam get_adapter(cia) e buscam o cotacao_id_cia do job.
    job_r = await db.execute(
        select(CotacaoJob)
        .where(CotacaoJob.cotacao_id == cotacao_id)
        .where(CotacaoJob.cia == body.cia)
        .where(CotacaoJob.status == "concluido")
    )
    job = job_r.scalar_one_or_none()

    # O sucesso de outra CIA não autoriza transmitir a seguradora selecionada.
    if (
        job is None
        or job.status_resultado not in ("sucesso", "restricao")
        or not job.cotacao_id_cia
        or job.premio_total is None
    ):
        raise HTTPException(
            409,
            "A seguradora selecionada não possui resultado válido. Atualize a cotação.",
        )

    # A omissão só permanece compatível com clientes legados do simulador.
    if (body.cia != "fake" or body.revisao_base is not None) and (
        body.revisao_base != quote_revision(job)
    ):
        raise HTTPException(
            409,
            "A revisão da cotação mudou ou não foi informada. "
            "Atualize o comparativo antes de transmitir.",
        )

    adapter: PortaSeguradora = (
        _default_adapter if body.cia == "fake" else get_adapter(body.cia)
    )
    cia_cotacao_id = str(job.cotacao_id_cia)

    risco = RiscoCanonico(ramo=cotacao.ramo, dados=dict(cotacao.dados_risco))
    # Ordem de precedência: payload_original (legado) < job.payload_resposta
    # (por CIA) < body.dados_negocio (overrides explícitos do usuário).
    # A preparação específica permanece dentro do adapter selecionado.
    job_payload = dict(job.payload_resposta) if job and job.payload_resposta else {}
    merged_negocio: dict[str, Any] = {
        **dict(cotacao.payload_original or {}),
        **job_payload,
        **dict(body.dados_negocio),
    }
    parcela_confirmada: Decimal | None = None
    pagamento_confirmado: dict[str, Any] | None = None
    plano_registro = body.plano_pagamento
    comissao_registro = body.comissao_pct
    if isinstance(adapter, PreparadorTransmissao):
        try:
            prepared = adapter.preparar_transmissao(
                job_payload,
                SelecaoTransmissao(
                    opcao_pagamento=body.opcao_pagamento,
                    parcelas=body.n_parcelas,
                    inicio_vigencia=body.inicio_vigencia,
                    dados_negocio=merged_negocio,
                    comissao_pct=body.comissao_pct,
                ),
            )
        except CondicaoTransmissaoError as exc:
            raise HTTPException(409, str(exc)) from exc
        merged_negocio = prepared.dados_negocio
        pagamento_confirmado = prepared.condicao_pagamento
        parcela_confirmada = prepared.valor_parcela
        plano_registro = prepared.plano_pagamento
        # A comissão registrada é a que a seguradora precificou, não a digitada.
        comissao_registro = prepared.comissao_pct
    proposta_canonica = PropostaCanonica(
        cotacao_id=cia_cotacao_id,
        risco=risco,
        dados_negocio=merged_negocio,
    )

    attempt_id = uuid.uuid4()
    # O agregado pode representar outra CIA; registre o preço da selecionada.
    premio_registro = job.premio_total
    ip = request.client.host if request.client else None
    await transmission.record(
        db,
        cotacao,
        actor,
        "transmissao.iniciada",
        attempt_id,
        body.cia,
        ip=ip,
        key=body.chave_idempotencia,
        fingerprint=fingerprint,
    )
    await db.commit()
    await transmission.restore_context(db, actor)
    # O lock permanece durante a chamada: ninguém libera um envio ainda em curso.
    cotacao = await transmission.quote_for_user(db, cotacao_id, actor, lock=True)
    current = await transmission.latest(db, cotacao)
    if (
        current is None
        or current.tipo != "transmissao.iniciada"
        or current.dados.get("tentativa_id") != str(attempt_id)
    ):
        raise HTTPException(409, "A tentativa mudou. Atualize a conferência.")
    try:
        resultado = await adapter.transmitir(proposta_canonica)
        if not resultado.sucesso or resultado.protocolo is None:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="A seguradora não confirmou a transmissão.",
            )
        # Truncar o protocolo perderia a única referência ao envio já feito.
        if len(resultado.protocolo) > 100:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="A seguradora devolveu um protocolo fora do formato "
                "esperado. Confira na seguradora antes de reenviar.",
            )

        valor_parcela = (
            parcela_confirmada
            if parcela_confirmada is not None
            else (premio_registro / body.n_parcelas).quantize(Decimal("0.01"))
        )
        comissao_parcela = (valor_parcela * comissao_registro).quantize(Decimal("0.01"))

        proposta = Proposta(
            id=uuid.uuid4(),
            cotacao_id=cotacao_id,
            protocolo=resultado.protocolo,
            comissao_pct=comissao_registro,
            plano_pagamento=plano_registro,
            n_parcelas=body.n_parcelas,
            valor_parcela=valor_parcela,
            comissao_parcela=comissao_parcela,
            inicio_vigencia=body.inicio_vigencia,
            usuario_id=actor.id,
            tenant_id=actor.tenant_id,
        )
        db.add(proposta)

        db.add(
            EventoDB(
                id=uuid.uuid4(),
                tipo="proposta.transmitida",
                payload={
                    "protocolo": resultado.protocolo,
                    "cotacao_id": str(cotacao_id),
                    "proposta_id": str(proposta.id),
                },
                usuario_id=actor.id,
                tenant_id=actor.tenant_id,
            )
        )

        ip = request.client.host if request.client else None
        await audit.registrar(
            db,
            "proposta.transmitida",
            {
                "protocolo": resultado.protocolo,
                "cotacao_id": str(cotacao_id),
                "condicao_pagamento": pagamento_confirmado,
            },
            usuario_id=actor.id,
            ip_origem=ip,
            tenant_id=actor.tenant_id,
        )

        await transmission.record(
            db, cotacao, actor, "transmissao.concluida", attempt_id, body.cia, ip=ip
        )
        await db.commit()
        link = resultado.dados.get("checkout_url")
        return _proposta_out(proposta, str(link) if link else None)

    except Exception as exc:
        # Mesmo que a gravação de 'incerta' falhe, o início durável bloqueia reenvio.
        try:
            await transmission.mark_uncertain(
                db, cotacao_id, actor, attempt_id, body.cia, ip
            )
        except Exception:
            await db.rollback()
        raise HTTPException(
            502,
            "Não foi possível confirmar a transmissão. Não reenvie: "
            "confira na seguradora e registre o resultado em Conferir transmissões.",
        ) from exc


@router.get("/propostas/{proposta_id}", response_model=PropostaOut)
async def obter_proposta(
    proposta_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PropostaOut:
    return _proposta_out(await _get_proposta_ou_404(proposta_id, usuario.id, db))


@router.get("/propostas/{proposta_id}/parcelas", response_model=list[ParcelaOut])
async def listar_parcelas(
    proposta_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ParcelaOut]:
    p = await _get_proposta_ou_404(proposta_id, usuario.id, db)
    parcelas: list[ParcelaOut] = []
    for i in range(p.n_parcelas):
        vencimento: date | None = None
        if p.inicio_vigencia is not None:
            vencimento = p.inicio_vigencia + timedelta(days=30 * i)
        parcelas.append(
            ParcelaOut(
                numero=i + 1,
                vencimento=vencimento,
                valor=p.valor_parcela,
                comissao=p.comissao_parcela,
            )
        )
    return parcelas


class ApoliceInput(BaseModel):
    numero_apolice: str = Field(min_length=1, max_length=100)


@router.patch("/propostas/{proposta_id}/apolice", response_model=PropostaOut)
async def vincular_apolice(
    proposta_id: uuid.UUID,
    body: ApoliceInput,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PropostaOut:
    """Vincula o número de apólice emitido pela seguradora à proposta."""
    p = await _get_proposta_ou_404(proposta_id, usuario.id, db)
    if p.numero_apolice is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proposta já possui apólice vinculada.",
        )
    p.numero_apolice = body.numero_apolice
    await audit.registrar(
        db,
        "apolice.vinculada",
        {"proposta_id": str(proposta_id), "numero_apolice": body.numero_apolice},
        usuario_id=usuario.id,
    )
    await db.commit()
    await db.refresh(p)
    return _proposta_out(p)
