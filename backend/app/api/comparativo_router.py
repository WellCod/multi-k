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
    restricoes: list[dict[str, str]]
    mensagens: list[str]
    necessita_vistoria: bool
    status: str


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


def _build_itens(cotacao: Cotacao, jobs: list[CotacaoJob]) -> list[ItemComparativoOut]:
    """Monta a lista de resultados por cia para o comparativo."""
    cias_processadas = {j.cia for j in jobs if j.status == "concluido"}
    if not cias_processadas:
        return []

    restricoes: list[dict[str, str]] = [
        {"codigo": r["codigo"], "mensagem": r["mensagem"]}
        for r in (cotacao.restricoes or [])
    ]
    return [
        ItemComparativoOut(
            cia=cia,
            cotacao_id_cia=cotacao.cotacao_id_cia,
            premio_total=cotacao.premio_total,
            restricoes=restricoes,
            mensagens=[str(m) for m in (cotacao.mensagens or [])],
            necessita_vistoria=cotacao.necessita_vistoria,
            status=cotacao.status,
        )
        for cia in cias_processadas
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
