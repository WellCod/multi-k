"""Rotas de comparativo — JSON e PDF via reportlab."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Annotated, Any
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.justos import client as justos_client
from app.adapters.justos.payment import PaymentOption, payment_options
from app.api.deps import CurrentUser
from app.infra import audit, transmission_control
from app.infra.db import get_db
from app.infra.models import Cotacao, CotacaoJob, Proposta
from app.infra.quote_revision import quote_revision as _revision

router = APIRouter(tags=["comparativo"])


class ItemComparativoOut(BaseModel):
    cia: str
    revisao_base: str
    condicoes_pagamento: list[PaymentOption] = []
    comissao_pct_cotada: Decimal | None = None
    # J4: observação da seguradora, separada das mensagens do sistema.
    info: str | None = None
    nome: str | None = None
    iniciado_em: str | None = None
    cotacao_id_cia: str | None
    premio_total: Decimal | None
    annual_total: Decimal | None
    restricoes: list[dict[str, str]]
    mensagens: list[str]
    necessita_vistoria: bool
    status: str
    coverages_available: dict[str, Any] | None = None
    coverages_selected: dict[str, str | None] | None = None
    coberturas_comparaveis: list[dict[str, str | None]] = []


class RepricingInput(BaseModel):
    cia: str
    coverages_selected: dict[str, str | None]
    aplicar: bool = False
    revisao_base: str | None = Field(default=None, min_length=64, max_length=64)
    monthly_confirmado: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    annual_confirmado: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def require_confirmation(self) -> "RepricingInput":
        if self.aplicar and (
            self.revisao_base is None
            or self.monthly_confirmado is None
            or self.annual_confirmado is None
        ):
            raise ValueError("Recalcule e confirme os valores antes de aplicar.")
        return self


class RepricingOutput(BaseModel):
    revisao_base: str
    condicoes_pagamento: list[PaymentOption] = []
    monthly_total: Decimal
    annual_total: Decimal
    info: str
    coverages_selected: dict[str, str | None]
    coberturas_comparaveis: list[dict[str, str | None]]


def _confirmed_price(pricing: dict[str, Any], period: str) -> Decimal:
    """Ausência ou resposta inválida não equivale a prêmio zero."""
    section = pricing.get(period)
    raw = section.get("total") if isinstance(section, dict) else None
    if raw is not None and not isinstance(raw, (bool, dict, list)):
        try:
            value = Decimal(str(raw))
            if value.is_finite() and value >= 0:
                return value.quantize(Decimal("0.01"))
        except InvalidOperation:
            pass
    raise HTTPException(
        502,
        "A seguradora não confirmou os valores do recálculo. "
        "Revise antes de continuar.",
    )


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


def _coverage_options(job: CotacaoJob) -> dict[str, Any] | None:
    source = (job.payload_resposta or {}).get("coverages_available")
    if not isinstance(source, dict):
        return None
    output: dict[str, dict[str, Any]] = {}
    for code, coverage in source.items():
        if not isinstance(coverage, dict):
            continue
        options = []
        raw_options = coverage.get("peril_options", [])
        for option in raw_options if isinstance(raw_options, list) else []:
            if not isinstance(option, dict):
                continue
            normalized: dict[str, Any] = {
                key: value
                for key in ("slug", "name", "description")
                if isinstance(value := option.get(key), str)
            }
            normalized["used_parts"] = option.get("used_parts") is True
            for field in ("price", "deductible", "coverage_amount"):
                raw = option.get(field)
                normalized[field] = None
                if raw is not None and not isinstance(raw, (bool, dict, list)):
                    try:
                        value_decimal = Decimal(str(raw))
                        if value_decimal.is_finite():
                            normalized[field] = str(
                                value_decimal.quantize(Decimal("0.01"))
                            )
                    except InvalidOperation:
                        pass
            options.append(normalized)
        output[code] = {
            key: value
            for key in ("name", "description", "conceito_id", "nome_canonico")
            if isinstance(value := coverage.get(key), str)
        }
        output[code].update(
            mandatory=coverage.get("mandatory") is True, peril_options=options
        )
    return output


def _fipe_integral(raw: object) -> bool:
    """J1/J2 §4.4: coverage_amount zerado é 100% da FIPE, não cobertura nula."""
    if raw is None or isinstance(raw, (bool, dict, list)):
        return False
    try:
        return Decimal(str(raw)) == 0
    except InvalidOperation:
        return False


def _comparison_coverages(
    job: CotacaoJob, selected: dict[str, str | None] | None = None
) -> list[dict[str, str | None]]:
    available = _coverage_options(job) or {}
    if selected is None:
        selected = (job.payload_resposta or {}).get("coverages_selected") or {}
    rows = []
    for code, coverage in available.items():
        option = next(
            (
                o
                for o in coverage["peril_options"]
                if o.get("slug") == selected.get(code)
            ),
            None,
        )
        if option is None:
            continue
        integral = _fipe_integral(option.get("coverage_amount"))
        rows.append(
            {
                "conceito_id": str(coverage.get("conceito_id") or f"{job.cia}:{code}"),
                "nome_canonico": str(
                    coverage.get("nome_canonico") or coverage.get("name") or code
                ),
                "nome_original": str(coverage.get("name") or code),
                # Sem inventar o valor FIPE: o percentual fica como texto.
                "limite": None if integral else option.get("coverage_amount"),
                "limite_descricao": "100% da tabela FIPE" if integral else None,
            }
        )
    return rows


def _validate_selection(job: CotacaoJob, selected: dict[str, str | None]) -> None:
    available = _coverage_options(job)
    if not available:
        raise HTTPException(409, "Coberturas indisponíveis. Atualize a cotação.")
    if any(code not in available for code in selected):
        raise HTTPException(422, "A seleção contém uma cobertura não disponível.")
    for code, coverage in available.items():
        choice = selected.get(code)
        if choice is None:
            if coverage["mandatory"]:
                raise HTTPException(422, "Selecione todas as coberturas obrigatórias.")
            continue
        if not any(
            option.get("slug") == choice for option in coverage["peril_options"]
        ):
            raise HTTPException(422, "A opção selecionada não pertence à cobertura.")


def _build_itens(cotacao: Cotacao, jobs: list[CotacaoJob]) -> list[ItemComparativoOut]:
    """Monta a lista de resultados por cia para o comparativo."""
    return [
        ItemComparativoOut(
            cia=j.cia,
            revisao_base=_revision(j),
            condicoes_pagamento=(j.payload_resposta or {}).get(
                "condicoes_pagamento", []
            ),
            comissao_pct_cotada=(j.payload_resposta or {}).get("comissao_pct_cotada"),
            info=(j.payload_resposta or {}).get("info") or None,
            iniciado_em=j.criado_em.isoformat() if j.criado_em else None,
            cotacao_id_cia=j.cotacao_id_cia,
            premio_total=j.premio_total,
            annual_total=_annual_total(j),
            restricoes=[
                {"codigo": r["codigo"], "mensagem": r["mensagem"]}
                for r in (j.restricoes or [])
            ],
            mensagens=[str(m) for m in (j.mensagens or [])],
            necessita_vistoria=j.necessita_vistoria,
            status=(j.status_resultado or "erro")
            if j.status in ("concluido", "erro")
            else j.status,
            coverages_available=_coverage_options(j),
            coverages_selected=(j.payload_resposta or {}).get("coverages_selected"),
            coberturas_comparaveis=_comparison_coverages(j),
        )
        for j in jobs
    ]


def _observacoes(itens: list[ItemComparativoOut]) -> list[str]:
    """J4: observação informativa da seguradora, fora da tabela de valores.

    O texto vem do provedor, então é escapado antes de virar markup do PDF.
    """
    return [
        f"<b>{escape(item.cia.upper())}</b>: {escape(item.info)}"
        for item in itens
        if item.info
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

        observacoes = _observacoes(itens)
        if observacoes:
            story.append(Spacer(1, 0.6 * cm))
            story.append(Paragraph("Observações das seguradoras", styles["Heading3"]))
            for linha in observacoes:
                story.append(Paragraph(linha, styles["Normal"]))

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
    cotacao = await _get_cotacao_ou_404(cotacao_id, usuario.id, db)

    # Este endpoint ainda não possui implementação de recálculo para outras CIAs.
    if body.cia != "justos":
        raise HTTPException(422, "Recálculo não disponível para esta seguradora.")

    if body.aplicar:
        actor = transmission_control.Actor(usuario.id, usuario.tenant_id, usuario.papel)
        cotacao = await transmission_control.quote_for_user(
            db, cotacao_id, actor, lock=True
        )
        previous = await transmission_control.latest(db, cotacao)
        proposal = (
            await db.execute(
                select(Proposta.id)
                .where(
                    Proposta.cotacao_id == cotacao_id,
                    Proposta.tenant_id == actor.tenant_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if proposal or (previous and previous.tipo != "transmissao.liberada"):
            raise HTTPException(
                409,
                "Há uma transmissão registrada. Confira antes de alterar coberturas.",
            )

    result = await db.execute(
        select(CotacaoJob)
        .where(CotacaoJob.cotacao_id == cotacao_id, CotacaoJob.cia == body.cia)
        .order_by(CotacaoJob.criado_em.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if not job or not job.payload_resposta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado."
        )

    if job.status != "concluido" or job.status_resultado not in (
        "sucesso",
        "restricao",
    ):
        raise HTTPException(409, "Aguarde um resultado válido antes de recalcular.")
    _validate_selection(job, body.coverages_selected)
    revision = _revision(job)
    if body.aplicar and body.revisao_base != revision:
        raise HTTPException(
            409, "A cotação mudou em outra operação. Atualize e recalcule."
        )

    quote_id: str | None = job.payload_resposta.get("quote_id")
    if not quote_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="quote_id não disponível.",
        )

    pricing = await justos_client.calcular_preco(quote_id, body.coverages_selected)
    monthly = _confirmed_price(pricing, "monthly")
    annual = _confirmed_price(pricing, "annual")

    if body.aplicar:
        if monthly != body.monthly_confirmado or annual != body.annual_confirmado:
            raise HTTPException(
                409,
                "A seguradora alterou o preço. Recalcule e confira os novos valores.",
            )
        job.payload_resposta = {
            **job.payload_resposta,
            "coverages_selected": dict(body.coverages_selected),
            "monthly_total": str(monthly),
            "annual_total": str(annual),
            "condicoes_pagamento": [p.model_dump() for p in payment_options(pricing)],
            "info": pricing.get("info", ""),
            "revisao_id": str(uuid.uuid4()),
        }
        job.premio_total = monthly
        job.mensagens = [pricing["info"]] if pricing.get("info") else []
        # Preserve a escolha legada do representante; não compare periodicidades.
        representative = (
            await db.execute(
                select(CotacaoJob)
                .where(
                    CotacaoJob.cotacao_id == cotacao_id,
                    CotacaoJob.status_resultado == cotacao.status,
                )
                .order_by(CotacaoJob.criado_em, CotacaoJob.id)
                .limit(1)
            )
        ).scalar_one_or_none()
        if representative and representative.id == job.id:
            cotacao.premio_total = monthly
            cotacao.mensagens = job.mensagens
        await audit.registrar(
            db,
            "cotacao.coberturas_revisadas",
            {
                "cotacao_id": str(cotacao_id),
                "cia": body.cia,
                "revisao_anterior": revision,
                "revisao_atual": _revision(job),
                "monthly_total": str(monthly),
                "annual_total": str(annual),
                "coverages_selected": dict(body.coverages_selected),
            },
            usuario_id=usuario.id,
            tenant_id=usuario.tenant_id,
        )
        await db.commit()

    return RepricingOutput(
        revisao_base=_revision(job),
        condicoes_pagamento=payment_options(pricing),
        monthly_total=monthly,
        annual_total=annual,
        info=pricing.get("info", ""),
        coverages_selected=body.coverages_selected,
        coberturas_comparaveis=_comparison_coverages(job, body.coverages_selected),
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
