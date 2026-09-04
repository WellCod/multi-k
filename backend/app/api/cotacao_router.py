"""Rotas de cotação — fila assíncrona com SKIP LOCKED."""

import csv
import io
import uuid
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
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


def _cotacao_out(c: Cotacao, proposta_id: uuid.UUID | None = None) -> CotacaoOut:
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

    for cia in cias_para_ramo(body.ramo):
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
        select(Proposta.id)
        .where(Proposta.cotacao_id == cotacao_id)
        .order_by(Proposta.transmitida_em.desc())
        .limit(1)
    )
    proposta_id: uuid.UUID | None = p_row.scalar_one_or_none()
    return _cotacao_out(c, proposta_id)


class PaginatedCotacoes(BaseModel):
    items: list[CotacaoOut]
    total: int
    page: int
    page_size: int
    pages: int


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

    result = await db.execute(
        select(Cotacao)
        .where(base_where)
        .order_by(Cotacao.criado_em.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    cotacoes = list(result.scalars().all())

    proposta_map: dict[uuid.UUID, uuid.UUID] = {}
    if cotacoes:
        ids = [c.id for c in cotacoes]
        p_rows = await db.execute(
            select(Proposta.cotacao_id, Proposta.id)
            .where(Proposta.cotacao_id.in_(ids))
            .distinct(Proposta.cotacao_id)
            .order_by(Proposta.cotacao_id, Proposta.transmitida_em.desc())
        )
        proposta_map = {row[0]: row[1] for row in p_rows}

    pages = max(1, -(-total // page_size))  # ceiling division
    return PaginatedCotacoes(
        items=[_cotacao_out(c, proposta_map.get(c.id)) for c in cotacoes],
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
