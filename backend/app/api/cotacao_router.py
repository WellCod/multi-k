"""Rotas de cotação — fila assíncrona com SKIP LOCKED."""

import csv
import io
import uuid
from collections.abc import Callable
from decimal import Decimal
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response as HttpResponse
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, nullsfirst, nullslast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import cias_para_ramo
from app.api._utils import get_or_404
from app.api.deps import CurrentUser
from app.infra import audit
from app.infra.db import get_db
from app.infra.models import Cotacao, CotacaoJob, EventoDB, Proposta

router = APIRouter(prefix="/cotacoes", tags=["cotacoes"])


# ---------------------------------------------------------------------------
# Schemas de validação de dados_risco por ramo
# ---------------------------------------------------------------------------


class _RiscoAutoInput(BaseModel):
    model_config = {"extra": "allow"}
    codigo_fipe: str = Field(min_length=1)
    cep_pernoite: str = Field(min_length=8, max_length=9)
    finalidade: str = Field(min_length=1)


class _RiscoMotoInput(BaseModel):
    model_config = {"extra": "allow"}
    codigo_fipe: str = Field(min_length=1)
    cep_pernoite: str = Field(min_length=8, max_length=9)
    cilindrada: int = Field(gt=0, le=2500)
    categoria: str = Field(min_length=1)
    finalidade: str = Field(min_length=1)


class _RiscoImovelInput(BaseModel):
    model_config = {"extra": "allow"}
    cep: str = Field(min_length=8, max_length=9)
    tipo_imovel: str = Field(min_length=1)
    tipo_construcao: str = Field(min_length=1)


_RISCO_SCHEMAS: dict[str, type[BaseModel]] = {
    "auto": _RiscoAutoInput,
    "moto": _RiscoMotoInput,
    "imovel": _RiscoImovelInput,
}


class CriarCotacaoInput(BaseModel):
    ramo: Literal["auto", "moto", "imovel"]
    dados: dict[str, Any]
    cliente_id: uuid.UUID | None = None
    versao_anterior_id: uuid.UUID | None = None
    cias: list[str] | None = None

    @model_validator(mode="after")
    def _validar_dados_risco(self) -> "CriarCotacaoInput":
        schema = _RISCO_SCHEMAS.get(self.ramo)
        if schema:
            schema.model_validate(self.dados)
        inicio = self.dados.get("inicio_vigencia")
        fim = self.dados.get("fim_vigencia")
        if (
            inicio
            and fim
            and isinstance(inicio, str)
            and isinstance(fim, str)
            and fim <= inicio
        ):
            raise ValueError("fim_vigencia deve ser posterior a inicio_vigencia")
        return self


class CotacaoCriadaOut(BaseModel):
    id: uuid.UUID
    status: str
    ramo: str


class CotacaoOut(BaseModel):
    id: uuid.UUID
    status: str
    ramo: str
    cliente_id: uuid.UUID | None
    cotacao_id_cia: str | None
    premio_total: Decimal | None
    restricoes: list[dict[str, str]]
    mensagens: list[str]
    necessita_vistoria: bool
    versao_anterior_id: uuid.UUID | None
    criado_em: str
    dados_risco: dict[str, Any]
    proposta_id: uuid.UUID | None = None
    numero_apolice: str | None = None


def _cotacao_out(
    c: Cotacao,
    proposta_id: uuid.UUID | None = None,
    numero_apolice: str | None = None,
) -> CotacaoOut:
    restricoes: list[dict[str, str]] = [
        {"codigo": r["codigo"], "mensagem": r.get("mensagem") or r.get("descricao", "")}
        for r in (c.restricoes or [])
    ]
    mensagens: list[str] = [str(m) for m in (c.mensagens or [])]
    return CotacaoOut(
        id=c.id,
        status=c.status,
        ramo=c.ramo,
        cliente_id=c.cliente_id,
        cotacao_id_cia=c.cotacao_id_cia,
        premio_total=c.premio_total,
        restricoes=restricoes,
        mensagens=mensagens,
        necessita_vistoria=c.necessita_vistoria,
        versao_anterior_id=c.versao_anterior_id,
        criado_em=c.criado_em.isoformat(),
        dados_risco=c.dados_risco,
        proposta_id=proposta_id,
        numero_apolice=numero_apolice,
    )


async def _get_cotacao_ou_404(
    cotacao_id: uuid.UUID, usuario_id: uuid.UUID, db: AsyncSession
) -> Cotacao:
    stmt = (
        select(Cotacao)
        .where(Cotacao.id == cotacao_id)
        .where(Cotacao.usuario_id == usuario_id)
    )
    return await get_or_404(stmt, db, "Cotação não encontrada.")


@router.post("", response_model=CotacaoCriadaOut, status_code=202)
async def criar_cotacao(
    body: CriarCotacaoInput,
    request: Request,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CotacaoCriadaOut:
    available = cias_para_ramo(body.ramo)
    selected = list(dict.fromkeys(body.cias)) if body.cias is not None else available
    if not selected or any(cia not in available for cia in selected):
        raise HTTPException(422, "Selecione uma seguradora disponível para o ramo.")
    cotacao = Cotacao(
        id=uuid.uuid4(),
        cliente_id=body.cliente_id,
        ramo=body.ramo,
        status="aguardando",
        dados_risco=body.dados,
        versao_anterior_id=body.versao_anterior_id,
        usuario_id=usuario.id,
    )
    db.add(cotacao)
    await db.flush()

    for cia in selected:
        db.add(
            CotacaoJob(
                id=uuid.uuid4(),
                cotacao_id=cotacao.id,
                cia=cia,
                status="pendente",
            )
        )

    db.add(
        EventoDB(
            id=uuid.uuid4(),
            tipo="cotacao.criada",
            payload={"ramo": body.ramo, "cotacao_id": str(cotacao.id)},
            usuario_id=usuario.id,
        )
    )

    ip = request.client.host if request.client else None
    await audit.registrar(
        db,
        "cotacao.criada",
        {"ramo": body.ramo},
        usuario_id=usuario.id,
        ip_origem=ip,
    )

    await db.commit()

    return CotacaoCriadaOut(id=cotacao.id, status=cotacao.status, ramo=cotacao.ramo)


@router.get("/{cotacao_id}", response_model=CotacaoOut)
async def obter_cotacao(
    cotacao_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CotacaoOut:
    c = await _get_cotacao_ou_404(cotacao_id, usuario.id, db)
    p_row = await db.execute(
        select(Proposta.id, Proposta.numero_apolice)
        .where(Proposta.cotacao_id == cotacao_id)
        .order_by(Proposta.transmitida_em.desc())
        .limit(1)
    )
    p_tuple = p_row.first()
    proposta_id: uuid.UUID | None = p_tuple[0] if p_tuple else None
    numero_apolice: str | None = p_tuple[1] if p_tuple else None
    return _cotacao_out(c, proposta_id, numero_apolice)


class PaginatedCotacoes(BaseModel):
    items: list[CotacaoOut]
    total: int
    page: int
    page_size: int
    pages: int


_ORDER_COLS: dict[str, Callable[[], Any]] = {
    "data_asc": lambda: Cotacao.criado_em.asc(),
    "premio_desc": lambda: cast(Any, nullslast)(Cotacao.premio_total.desc()),
    "premio_asc": lambda: cast(Any, nullsfirst)(Cotacao.premio_total.asc()),
}


@router.get("", response_model=PaginatedCotacoes)
async def listar_cotacoes(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    ramo: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    dias: int | None = Query(default=None, ge=1, le=365),
    cia: Annotated[str | None, Query(max_length=50)] = None,
    order_by: Annotated[
        str | None, Query(pattern="^(data_asc|premio_desc|premio_asc)$")
    ] = None,
) -> PaginatedCotacoes:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import or_

    base_where = Cotacao.usuario_id == usuario.id
    if ramo:
        base_where = base_where & (Cotacao.ramo == ramo)
    if status:
        base_where = base_where & (Cotacao.status == status)
    if dias:
        corte = datetime.now(UTC) - timedelta(days=dias)
        base_where = base_where & (Cotacao.criado_em >= corte)
    if cia:
        base_where = base_where & Cotacao.id.in_(
            select(CotacaoJob.cotacao_id).where(CotacaoJob.cia == cia)
        )
    if q:
        # dados_risco["proponente"]["nome"].astext acessa o JSONB aninhado como texto
        nome_match = Cotacao.dados_risco["proponente"]["nome"].astext.ilike(f"%{q}%")
        base_where = base_where & or_(
            nome_match,
            Cotacao.cotacao_id_cia.ilike(f"%{q}%"),
        )

    total_row = await db.execute(
        select(func.count()).select_from(Cotacao).where(base_where)
    )
    total: int = total_row.scalar_one()

    order_col: Any = (
        _ORDER_COLS[order_by]() if order_by in _ORDER_COLS else Cotacao.criado_em.desc()
    )
    result = await db.execute(
        select(Cotacao)
        .where(base_where)
        .order_by(order_col)
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    cotacoes = list(result.scalars().all())

    proposta_map: dict[uuid.UUID, tuple[uuid.UUID, str | None]] = {}
    if cotacoes:
        ids = [c.id for c in cotacoes]
        p_rows = await db.execute(
            select(Proposta.cotacao_id, Proposta.id, Proposta.numero_apolice)
            .where(Proposta.cotacao_id.in_(ids))
            .distinct(Proposta.cotacao_id)
            .order_by(Proposta.cotacao_id, Proposta.transmitida_em.desc())
        )
        proposta_map = {row[0]: (row[1], row[2]) for row in p_rows}

    pages = max(1, -(-total // page_size))  # ceiling division
    return PaginatedCotacoes(
        items=[
            _cotacao_out(c, *proposta_map.get(c.id, (None, None))) for c in cotacoes
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/export/csv")
async def exportar_historico_csv(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    fmt: Literal["csv"] = Query("csv"),
) -> StreamingResponse:
    """Exporta o histórico de cotações do corretor em CSV."""
    result = await db.execute(
        select(Cotacao)
        .where(Cotacao.usuario_id == usuario.id)
        .order_by(Cotacao.criado_em.desc())
    )
    cotacoes = list(result.scalars().all())

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["id", "ramo", "status", "premio_total", "cotacao_id_cia", "criado_em"]
    )
    for c in cotacoes:
        writer.writerow(
            [
                str(c.id),
                c.ramo,
                c.status,
                str(c.premio_total) if c.premio_total else "",
                c.cotacao_id_cia or "",
                c.criado_em.isoformat(),
            ]
        )
    buf.seek(0)
    _ = fmt  # kept for future xlsx branch
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=historico.csv"},
    )


@router.get("/{cotacao_id}/pdf")
async def baixar_pdf_cotacao(
    cotacao_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    tipo: Literal["cotacao", "proposta"] = Query(default="cotacao"),
) -> HttpResponse:
    """Retorna PDF de cotação ou proposta gerado pela Justos (GCF)."""
    from app.adapters.justos import client as justos_client

    c = await _get_cotacao_ou_404(cotacao_id, usuario.id, db)

    job_r = await db.execute(
        select(CotacaoJob)
        .where(CotacaoJob.cotacao_id == cotacao_id)
        .where(CotacaoJob.cia == "justos")
        .where(CotacaoJob.status == "concluido")
    )
    job = job_r.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Cotação Justos não encontrada ou pendente.",
        )

    quote_id = str(job.cotacao_id_cia or c.cotacao_id_cia or "")
    if not quote_id:
        raise HTTPException(
            status_code=404,
            detail="ID da cotação na seguradora não disponível.",
        )

    try:
        if tipo == "proposta":
            pdf_bytes = await justos_client.gerar_pdf_proposta(quote_id)
        else:
            pdf_bytes = await justos_client.gerar_pdf_cotacao(quote_id)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Erro ao gerar PDF na Justos: {exc}",
        ) from exc

    filename = f"{tipo}-{cotacao_id}.pdf"
    return HttpResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


class RecotarLoteInput(BaseModel):
    cotacao_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)


@router.post("/recotar-lote", response_model=list[CotacaoCriadaOut], status_code=202)
async def recotar_em_lote(
    body: RecotarLoteInput,
    request: Request,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CotacaoCriadaOut]:
    """Cria novas versões para uma lista de cotações (máximo 20)."""
    originais_r = await db.execute(
        select(Cotacao)
        .where(Cotacao.id.in_(body.cotacao_ids))
        .where(Cotacao.usuario_id == usuario.id)
    )
    originais = {c.id: c for c in originais_r.scalars().all()}

    ip = request.client.host if request.client else None
    novas: list[CotacaoCriadaOut] = []
    for cid in body.cotacao_ids:
        original = originais.get(cid)
        if original is None:
            continue
        nova = Cotacao(
            id=uuid.uuid4(),
            cliente_id=original.cliente_id,
            ramo=original.ramo,
            status="aguardando",
            dados_risco=dict(original.dados_risco),
            versao_anterior_id=cid,
            usuario_id=usuario.id,
        )
        db.add(nova)
        await db.flush()
        for cia in cias_para_ramo(nova.ramo):
            db.add(
                CotacaoJob(
                    id=uuid.uuid4(), cotacao_id=nova.id, cia=cia, status="pendente"
                )
            )
        await audit.registrar(
            db,
            "cotacao.recotada",
            {"cotacao_anterior": str(cid), "nova_cotacao": str(nova.id)},
            usuario_id=usuario.id,
            ip_origem=ip,
        )
        novas.append(CotacaoCriadaOut(id=nova.id, status=nova.status, ramo=nova.ramo))

    await db.commit()
    return novas


@router.post("/{cotacao_id}/recotar", response_model=CotacaoCriadaOut, status_code=202)
async def recotar(
    cotacao_id: uuid.UUID,
    request: Request,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CotacaoCriadaOut:
    """Cria nova versão a partir de cotação existente, pré-preenchida."""
    original = await _get_cotacao_ou_404(cotacao_id, usuario.id, db)

    nova = Cotacao(
        id=uuid.uuid4(),
        cliente_id=original.cliente_id,
        ramo=original.ramo,
        status="aguardando",
        dados_risco=dict(original.dados_risco),
        versao_anterior_id=cotacao_id,
        usuario_id=usuario.id,
    )
    db.add(nova)
    await db.flush()

    for cia in cias_para_ramo(nova.ramo):
        db.add(
            CotacaoJob(
                id=uuid.uuid4(),
                cotacao_id=nova.id,
                cia=cia,
                status="pendente",
            )
        )

    ip = request.client.host if request.client else None
    await audit.registrar(
        db,
        "cotacao.recotada",
        {"cotacao_anterior": str(cotacao_id), "nova_cotacao": str(nova.id)},
        usuario_id=usuario.id,
        ip_origem=ip,
    )

    await db.commit()

    return CotacaoCriadaOut(id=nova.id, status=nova.status, ramo=nova.ramo)


class CancelarInput(BaseModel):
    cia: str | None = None


@router.post("/{cotacao_id}/cancelar", status_code=204)
async def cancelar_consulta(
    cotacao_id: uuid.UUID,
    body: CancelarInput,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    cotacao = await _get_cotacao_ou_404(cotacao_id, usuario.id, db)
    jobs = list(
        (
            await db.execute(
                select(CotacaoJob)
                .where(CotacaoJob.cotacao_id == cotacao_id)
                .order_by(CotacaoJob.id)
                .with_for_update()
            )
        ).scalars()
    )
    for job in jobs:
        if job.status in ("pendente", "processando") and (
            body.cia is None or body.cia == job.cia
        ):
            job.status = "erro"
            job.status_resultado = "cancelado"
            job.mensagens = [
                "Consulta cancelada no multi-K. Uma solicitação já enviada pode continuar na seguradora; seu retorno será descartado."
            ]
    if all(job.status in ("concluido", "erro") for job in jobs):
        states = {job.status_resultado for job in jobs}
        cotacao.status = (
            "sucesso"
            if "sucesso" in states
            else "restricao"
            if "restricao" in states
            else "erro"
        )
    await db.commit()


class VersaoPremioOut(BaseModel):
    id: uuid.UUID
    criado_em: str
    premio_total: Decimal | None
    ramo: str


@router.get("/{cotacao_id}/versoes", response_model=list[VersaoPremioOut])
async def historico_versoes(
    cotacao_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[VersaoPremioOut]:
    """Retorna a cadeia de recotações a partir de qualquer versão (até 20)."""
    versoes: list[VersaoPremioOut] = []
    atual_id: uuid.UUID | None = cotacao_id
    visitados: set[uuid.UUID] = set()

    while atual_id is not None and len(versoes) < 20:
        if atual_id in visitados:
            break
        visitados.add(atual_id)
        stmt = (
            select(Cotacao)
            .where(Cotacao.id == atual_id)
            .where(Cotacao.usuario_id == usuario.id)
        )
        cot = (await db.execute(stmt)).scalar_one_or_none()
        if cot is None:
            break
        versoes.append(
            VersaoPremioOut(
                id=cot.id,
                criado_em=cot.criado_em.isoformat(),
                premio_total=cot.premio_total,
                ramo=cot.ramo,
            )
        )
        atual_id = cot.versao_anterior_id

    versoes.reverse()
    return versoes
