"""Rotas de comparativo — JSON e PDF via reportlab."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.infra.db import get_db
from app.infra.models import Cotacao, CotacaoJob

router = APIRouter(tags=["comparativo"])


class ItemComparativoOut(BaseModel):
    cia: str
    cotacao_id_cia: str | None
    premio_total: Decimal | None
    annual_total: Decimal | None
    restricoes: list[dict[str, str]]
    mensagens: list[str]
    necessita_vistoria: bool
    status: str
    coverages_available: dict[str, Any] | None = None
    coverages_selected: dict[str, str | None] | None = None


class RepricingInput(BaseModel):
    cia: str
    coverages_selected: dict[str, str | None]


class RepricingOutput(BaseModel):
    monthly_total: Decimal
    annual_total: Decimal
    info: str
    coverages_selected: dict[str, str | None]


async def _get_cotacao_ou_404(
    cotacao_id: uuid.UUID,
    usuario_id: uuid.UUID,
    db: AsyncSession,
) -> Cotacao:
    result = await db.execute(
        select(Cotacao)
        .where(Cotacao.id == cotacao_id)
        .where(Cotacao.usuario_id == usuario_id)
    )
    c = result.scalar_one_or_none()
    if c is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cotação não encontrada.",
        )
    return c


def _annual_total(job: CotacaoJob) -> Decimal | None:
    """Extrai prêmio anual do payload_resposta do adapter, se disponível."""
    payload = job.payload_resposta or {}
    raw = payload.get("annual_total")
    if raw is None:
        return None
    try:
        return Decimal(str(raw)).quantize(Decimal("0.01"))
    except Exception:
        return None


def _build_itens(cotacao: Cotacao, jobs: list[CotacaoJob]) -> list[ItemComparativoOut]:
    """Monta a lista de resultados por cia para o comparativo."""
    concluidos = [j for j in jobs if j.status == "concluido"]
    if not concluidos:
        return []
    return [
        ItemComparativoOut(
            cia=j.cia,
            cotacao_id_cia=j.cotacao_id_cia,
            premio_total=j.premio_total,
            annual_total=_annual_total(j),
            restricoes=[
                {"codigo": r["codigo"], "mensagem": r["mensagem"]}
                for r in (j.restricoes or [])
            ],
            mensagens=[str(m) for m in (j.mensagens or [])],
            necessita_vistoria=j.necessita_vistoria,
            status=j.status_resultado or "erro",
            coverages_available=(j.payload_resposta or {}).get("coverages_available"),
            coverages_selected=(j.payload_resposta or {}).get("coverages_selected"),
        )
        for j in concluidos
    ]


def _gerar_pdf(cotacao: Cotacao, itens: list[ItemComparativoOut]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    story: list[Any] = []

    story.append(Paragraph("Comparativo de Cotações", styles["Title"]))
    story.append(Spacer(1, 0.4 * cm))

    ramo_label = cotacao.ramo.capitalize()
    gerado_em = datetime.now(UTC).strftime("%d/%m/%Y %H:%M UTC")
    info = f"Ramo: <b>{ramo_label}</b> &nbsp;|&nbsp; Gerado em: {gerado_em}"
    story.append(Paragraph(info, styles["Normal"]))
    story.append(Spacer(1, 0.6 * cm))

    if not itens:
        story.append(Paragraph("Nenhum resultado disponível.", styles["Normal"]))
    else:
        headers = [
            "Seguradora",
            "Prêmio Total (R$)",
            "Restrições",
            "Vistoria",
            "Status",
        ]
        rows: list[list[str]] = [headers]
        for item in itens:
            premio = (
                f"{item.premio_total:,.2f}" if item.premio_total is not None else "—"
            )
            restricoes_txt = "; ".join(r["codigo"] for r in item.restricoes) or "—"
            vistoria = "Sim" if item.necessita_vistoria else "Não"
            rows.append(
                [item.cia.upper(), premio, restricoes_txt, vistoria, item.status]
            )

        col_widths = [4 * cm, 4 * cm, 5 * cm, 2.5 * cm, 3 * cm]
        table = Table(rows, colWidths=col_widths)
        bg_alt = colors.HexColor("#F5F5F5")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, bg_alt]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(table)

    doc.build(story)
    return buf.getvalue()


@router.get(
    "/cotacoes/{cotacao_id}/comparativo",
    response_model=list[ItemComparativoOut],
)
async def comparativo_json(
    cotacao_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ItemComparativoOut]:
    cotacao = await _get_cotacao_ou_404(cotacao_id, usuario.id, db)
    jobs_r = await db.execute(
        select(CotacaoJob).where(CotacaoJob.cotacao_id == cotacao_id)
    )
    jobs = list(jobs_r.scalars().all())
    return _build_itens(cotacao, jobs)


@router.post(
    "/cotacoes/{cotacao_id}/repricing",
    response_model=RepricingOutput,
)
async def repricing(
    cotacao_id: uuid.UUID,
    body: RepricingInput,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RepricingOutput:
    """Recalcula o preço de uma cotação Justos com novas coberturas selecionadas."""
    await _get_cotacao_ou_404(cotacao_id, usuario.id, db)

    result = await db.execute(
        select(CotacaoJob)
        .where(CotacaoJob.cotacao_id == cotacao_id, CotacaoJob.cia == body.cia)
        .order_by(CotacaoJob.criado_em.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if not job or not job.payload_resposta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado.")

    quote_id: str | None = job.payload_resposta.get("quote_id")
    if not quote_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="quote_id não disponível.")

    from app.adapters.justos import client as justos_client

    pricing = await justos_client.calcular_preco(quote_id, body.coverages_selected)
    monthly = Decimal(str(pricing.get("monthly", {}).get("total", 0))).quantize(Decimal("0.01"))
    annual = Decimal(str(pricing.get("annual", {}).get("total", 0))).quantize(Decimal("0.01"))

    return RepricingOutput(
        monthly_total=monthly,
        annual_total=annual,
        info=pricing.get("info", ""),
        coverages_selected=body.coverages_selected,
    )


@router.get("/cotacoes/{cotacao_id}/comparativo/pdf")
async def comparativo_pdf(
    cotacao_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    cotacao = await _get_cotacao_ou_404(cotacao_id, usuario.id, db)
    jobs_r = await db.execute(
        select(CotacaoJob).where(CotacaoJob.cotacao_id == cotacao_id)
    )
    jobs = list(jobs_r.scalars().all())
    itens = _build_itens(cotacao, jobs)
    pdf_bytes = _gerar_pdf(cotacao, itens)
    filename = f"comparativo-{cotacao_id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
