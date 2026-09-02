"""Rotas de cliente — CRUD com busca por CPF via índice cego."""

import io
import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._utils import get_or_404
from app.api.deps import CurrentUser
from app.infra import audit
from app.infra.cpf import cpf_para_idx
from app.infra.db import get_db
from app.infra.models import Cliente, Cotacao, Imovel, Proposta, Veiculo

router = APIRouter(prefix="/clientes", tags=["clientes"])


# ---------------------------------------------------------------------------
# Schemas de entrada
# ---------------------------------------------------------------------------


class ClienteInput(BaseModel):
    nome: str
    cpf: str = Field(pattern=r"^\d{11}$")  # recebido, nunca armazenado
    email: str | None = None
    telefone: str | None = None
    data_nascimento: date | None = None
    sexo: str | None = Field(default=None, pattern=r"^[MF]$")
    estado_civil: str | None = None
    profissao: str | None = None


class ClientePatch(BaseModel):
    nome: str | None = None
    email: str | None = None
    telefone: str | None = None
    data_nascimento: date | None = None
    sexo: str | None = Field(default=None, pattern=r"^[MF]$")
    estado_civil: str | None = None
    profissao: str | None = None


class VeiculoInput(BaseModel):
    fipe_codigo: str | None = None
    marca: str
    modelo: str
    ano_fabricacao: int
    ano_modelo: int
    placa: str | None = None
    chassi: str | None = None
    combustivel: str
    finalidade: str = "lazer"
    cep_pernoite: str = Field(pattern=r"^\d{8}$")


class ImovelInput(BaseModel):
    cep: str = Field(pattern=r"^\d{8}$")
    logradouro: str | None = None
    numero: str | None = None
    tipo_imovel: str
    tipo_construcao: str


# ---------------------------------------------------------------------------
# Schemas de saída — CPF jamais retornado
# ---------------------------------------------------------------------------


class ClienteOut(BaseModel):
    id: uuid.UUID
    nome: str
    email: str | None
    telefone: str | None
    data_nascimento: date | None
    sexo: str | None
    estado_civil: str | None
    profissao: str | None
    usuario_id: uuid.UUID
    criado_em: str


class VeiculoOut(BaseModel):
    id: uuid.UUID
    cliente_id: uuid.UUID
    fipe_codigo: str | None
    marca: str
    modelo: str
    ano_fabricacao: int
    ano_modelo: int
    placa: str | None
    chassi: str | None
    combustivel: str
    finalidade: str
    cep_pernoite: str


class ClienteListOut(BaseModel):
    items: list["ClienteOut"]
    total: int
    page: int
    page_size: int


class ImovelOut(BaseModel):
    id: uuid.UUID
    cliente_id: uuid.UUID
    cep: str
    logradouro: str | None
    numero: str | None
    tipo_imovel: str
    tipo_construcao: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cliente_out(c: Cliente) -> ClienteOut:
    return ClienteOut(
        id=c.id,
        nome=c.nome,
        email=c.email,
        telefone=c.telefone,
        data_nascimento=c.data_nascimento,
        sexo=c.sexo,
        estado_civil=c.estado_civil,
        profissao=c.profissao,
        usuario_id=c.usuario_id,
        criado_em=c.criado_em.isoformat(),
    )


def _veiculo_out(v: Veiculo) -> VeiculoOut:
    return VeiculoOut(
        id=v.id,
        cliente_id=v.cliente_id,
        fipe_codigo=v.fipe_codigo,
        marca=v.marca,
        modelo=v.modelo,
        ano_fabricacao=v.ano_fabricacao,
        ano_modelo=v.ano_modelo,
        placa=v.placa,
        chassi=v.chassi,
        combustivel=v.combustivel,
        finalidade=v.finalidade,
        cep_pernoite=v.cep_pernoite,
    )


def _imovel_out(i: Imovel) -> ImovelOut:
    return ImovelOut(
        id=i.id,
        cliente_id=i.cliente_id,
        cep=i.cep,
        logradouro=i.logradouro,
        numero=i.numero,
        tipo_imovel=i.tipo_imovel,
        tipo_construcao=i.tipo_construcao,
    )


async def _get_cliente_ou_404(
    cliente_id: uuid.UUID, usuario_id: uuid.UUID, db: AsyncSession
) -> Cliente:
    stmt = (
        select(Cliente)
        .where(Cliente.id == cliente_id)
        .where(Cliente.usuario_id == usuario_id)
    )
    return await get_or_404(stmt, db, "Cliente não encontrado.")


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------


@router.post("", response_model=ClienteOut, status_code=201)
async def criar_cliente(
    body: ClienteInput,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClienteOut:
    cliente = Cliente(
        id=uuid.uuid4(),
        nome=body.nome,
        cpf_idx=cpf_para_idx(body.cpf),
        email=body.email,
        telefone=body.telefone,
        data_nascimento=body.data_nascimento,
        sexo=body.sexo,
        estado_civil=body.estado_civil,
        profissao=body.profissao,
        usuario_id=usuario.id,
    )
    db.add(cliente)
    await audit.registrar(
        db,
        tipo="cliente.criado",
        dados={"cliente_id": str(cliente.id)},
        usuario_id=usuario.id,
    )
    await db.commit()
    await db.refresh(cliente)
    return _cliente_out(cliente)


class BuscaCpfInput(BaseModel):
    cpf: str = Field(pattern=r"^\d{11}$")


@router.post("/busca", response_model=list[ClienteOut])
async def buscar_por_cpf(
    body: BuscaCpfInput,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ClienteOut]:
    """Busca por CPF via índice cego — CPF recebido no body, nunca em query string."""
    idx = cpf_para_idx(body.cpf)
    result = await db.execute(
        select(Cliente)
        .where(Cliente.cpf_idx == idx)
        .where(Cliente.usuario_id == usuario.id)
    )
    return [_cliente_out(c) for c in result.scalars().all()]


@router.get("", response_model=ClienteListOut)
async def listar_clientes(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, description="Busca por nome ou e-mail"),
) -> ClienteListOut:
    base = (
        select(Cliente)
        .where(Cliente.usuario_id == usuario.id)
        .where(Cliente.ativo.is_(True))
    )
    if q:
        term = f"%{q}%"
        base = base.where(
            Cliente.nome.ilike(term)
            | Cliente.email.ilike(term)
            | Cliente.telefone.ilike(term)
        )

    total_r = await db.execute(select(func.count()).select_from(base.subquery()))
    total = int(total_r.scalar_one())

    result = await db.execute(
        base.order_by(Cliente.criado_em.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return ClienteListOut(
        items=[_cliente_out(c) for c in result.scalars().all()],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{cliente_id}", response_model=ClienteOut)
async def obter_cliente(
    cliente_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClienteOut:
    return _cliente_out(await _get_cliente_ou_404(cliente_id, usuario.id, db))


@router.delete("/{cliente_id}", status_code=204)
async def arquivar_cliente(
    cliente_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    c = await _get_cliente_ou_404(cliente_id, usuario.id, db)
    c.ativo = False
    await audit.registrar(
        db,
        tipo="cliente.arquivado",
        dados={"cliente_id": str(cliente_id)},
        usuario_id=usuario.id,
    )
    await db.commit()


@router.patch("/{cliente_id}", response_model=ClienteOut)
async def atualizar_cliente(
    cliente_id: uuid.UUID,
    body: ClientePatch,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClienteOut:
    c = await _get_cliente_ou_404(cliente_id, usuario.id, db)
    update_data: dict[str, Any] = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(c, field, value)
    await db.commit()
    await db.refresh(c)
    return _cliente_out(c)


@router.get("/{cliente_id}/veiculos", response_model=list[VeiculoOut])
async def listar_veiculos(
    cliente_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[VeiculoOut]:
    await _get_cliente_ou_404(cliente_id, usuario.id, db)
    result = await db.execute(select(Veiculo).where(Veiculo.cliente_id == cliente_id))
    return [_veiculo_out(v) for v in result.scalars().all()]


@router.post("/{cliente_id}/veiculos", response_model=VeiculoOut, status_code=201)
async def adicionar_veiculo(
    cliente_id: uuid.UUID,
    body: VeiculoInput,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VeiculoOut:
    await _get_cliente_ou_404(cliente_id, usuario.id, db)
    v = Veiculo(
        id=uuid.uuid4(),
        cliente_id=cliente_id,
        fipe_codigo=body.fipe_codigo,
        marca=body.marca,
        modelo=body.modelo,
        ano_fabricacao=body.ano_fabricacao,
        ano_modelo=body.ano_modelo,
        placa=body.placa,
        chassi=body.chassi,
        combustivel=body.combustivel,
        finalidade=body.finalidade,
        cep_pernoite=body.cep_pernoite,
    )
    db.add(v)
    await audit.registrar(
        db,
        tipo="veiculo.adicionado",
        dados={"cliente_id": str(cliente_id)},
        usuario_id=usuario.id,
    )
    await db.commit()
    await db.refresh(v)
    return _veiculo_out(v)


@router.get("/{cliente_id}/imoveis", response_model=list[ImovelOut])
async def listar_imoveis(
    cliente_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ImovelOut]:
    await _get_cliente_ou_404(cliente_id, usuario.id, db)
    result = await db.execute(select(Imovel).where(Imovel.cliente_id == cliente_id))
    return [_imovel_out(i) for i in result.scalars().all()]


@router.post("/{cliente_id}/imoveis", response_model=ImovelOut, status_code=201)
async def adicionar_imovel(
    cliente_id: uuid.UUID,
    body: ImovelInput,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImovelOut:
    await _get_cliente_ou_404(cliente_id, usuario.id, db)
    i = Imovel(
        id=uuid.uuid4(),
        cliente_id=cliente_id,
        cep=body.cep,
        logradouro=body.logradouro,
        numero=body.numero,
        tipo_imovel=body.tipo_imovel,
        tipo_construcao=body.tipo_construcao,
    )
    db.add(i)
    await audit.registrar(
        db,
        tipo="imovel.adicionado",
        dados={"cliente_id": str(cliente_id)},
        usuario_id=usuario.id,
    )
    await db.commit()
    await db.refresh(i)
    return _imovel_out(i)


class TimelineItem(BaseModel):
    tipo: str
    data: str
    dados: dict[str, Any]


@router.get("/{cliente_id}/timeline", response_model=list[TimelineItem])
async def timeline_cliente(
    cliente_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TimelineItem]:
    """Linha do tempo do cliente: criação, cotações e propostas ordenadas."""
    cliente = await _get_cliente_ou_404(cliente_id, usuario.id, db)

    items: list[TimelineItem] = [
        TimelineItem(
            tipo="cliente.criado",
            data=cliente.criado_em.isoformat(),
            dados={"nome": cliente.nome},
        )
    ]

    cotacoes_r = await db.execute(
        select(Cotacao)
        .where(Cotacao.cliente_id == cliente_id)
        .order_by(Cotacao.criado_em)
    )
    cotacoes = cotacoes_r.scalars().all()

    # 1 query para todas as propostas — evita N+1
    cotacao_ids = [c.id for c in cotacoes]
    propostas_por_cotacao: dict[uuid.UUID, list[Proposta]] = {}
    if cotacao_ids:
        props_r = await db.execute(
            select(Proposta)
            .where(Proposta.cotacao_id.in_(cotacao_ids))
            .order_by(Proposta.transmitida_em)
        )
        for p in props_r.scalars().all():
            propostas_por_cotacao.setdefault(p.cotacao_id, []).append(p)

    for cotacao in cotacoes:
        items.append(
            TimelineItem(
                tipo="cotacao.criada",
                data=cotacao.criado_em.isoformat(),
                dados={
                    "id": str(cotacao.id),
                    "ramo": cotacao.ramo,
                    "status": cotacao.status,
                    "premio_total": (
                        str(cotacao.premio_total) if cotacao.premio_total else None
                    ),
                },
            )
        )
        for proposta in propostas_por_cotacao.get(cotacao.id, []):
            items.append(
                TimelineItem(
                    tipo="proposta.transmitida",
                    data=proposta.transmitida_em.isoformat(),
                    dados={
                        "id": str(proposta.id),
                        "protocolo": proposta.protocolo,
                        "n_parcelas": proposta.n_parcelas,
                        "valor_parcela": str(proposta.valor_parcela),
                    },
                )
            )

    items.sort(key=lambda x: x.data)
    return items


# ---------------------------------------------------------------------------
# Ficha do cliente em PDF
# ---------------------------------------------------------------------------


def _gerar_ficha_pdf(
    cliente: Cliente, veiculos: list[Any], imoveis: list[Any]
) -> bytes:
    from reportlab.lib import colors  # noqa: PLC0415
    from reportlab.lib.pagesizes import A4  # noqa: PLC0415
    from reportlab.lib.styles import getSampleStyleSheet  # noqa: PLC0415
    from reportlab.lib.units import cm  # noqa: PLC0415
    from reportlab.platypus import (  # noqa: PLC0415
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    story: list[Any] = []

    story.append(Paragraph("Ficha do Cliente", styles["Title"]))
    story.append(Spacer(1, 0.4 * cm))
    gerado_em = datetime.now(UTC).strftime("%d/%m/%Y %H:%M UTC")
    story.append(Paragraph(f"Gerado em: {gerado_em}", styles["Normal"]))
    story.append(Spacer(1, 0.6 * cm))

    def _row(label: str, value: object) -> list[str]:
        return [label, str(value) if value is not None else "—"]

    dados: list[list[str]] = [
        _row("Nome", cliente.nome),
        _row("E-mail", cliente.email),
        _row("Telefone", cliente.telefone),
        _row("Data de nascimento", cliente.data_nascimento),
        _row("Sexo", cliente.sexo),
        _row("Estado civil", cliente.estado_civil),
        _row("Profissão", cliente.profissao),
    ]
    t = Table(dados, colWidths=[5 * cm, 10 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [colors.white, colors.HexColor("#F5F5F5")]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    if veiculos:
        story.append(Spacer(1, 0.6 * cm))
        story.append(Paragraph("Veículos", styles["Heading2"]))
        vrows = [["Marca", "Modelo", "Ano", "Placa", "CEP pernoite"]]
        for v in veiculos:
            vrows.append([
                v.marca, v.modelo, str(v.ano_modelo), v.placa or "—", v.cep_pernoite,
            ])
        vt = Table(vrows, colWidths=[3.5 * cm, 4 * cm, 2 * cm, 2.5 * cm, 3 * cm])
        vt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F5F5F5")]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(vt)

    if imoveis:
        story.append(Spacer(1, 0.6 * cm))
        story.append(Paragraph("Imóveis", styles["Heading2"]))
        irows = [["CEP", "Logradouro", "Número", "Tipo", "Construção"]]
        for im in imoveis:
            irows.append([
                im.cep, im.logradouro or "—", im.numero or "—",
                im.tipo_imovel, im.tipo_construcao,
            ])
        it = Table(irows, colWidths=[2.5 * cm, 5 * cm, 2 * cm, 3 * cm, 2.5 * cm])
        it.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F5F5F5")]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(it)

    doc.build(story)
    return buf.getvalue()


@router.get("/clientes/{cliente_id}/ficha.pdf")
async def ficha_pdf(
    cliente_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Exporta ficha do cliente em PDF."""
    cliente = await get_or_404(
        select(Cliente)
        .where(Cliente.id == cliente_id)
        .where(Cliente.usuario_id == usuario.id)
        .where(Cliente.ativo.is_(True)),
        db,
        "Cliente não encontrado.",
    )
    veiculos_r = await db.execute(
        select(Veiculo).where(Veiculo.cliente_id == cliente_id)
    )
    imoveis_r = await db.execute(
        select(Imovel).where(Imovel.cliente_id == cliente_id)
    )
    pdf_bytes = _gerar_ficha_pdf(
        cliente, list(veiculos_r.scalars().all()), list(imoveis_r.scalars().all())
    )
    filename = f"ficha_{cliente.nome.replace(' ', '_')}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
