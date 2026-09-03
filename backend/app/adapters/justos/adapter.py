"""Adapter Justos — implementa PortaSeguradora para a API Justos.

Ramo suportado: auto (veículos).

Campos obrigatórios em dados_risco para ramo=auto:
  - cpf / proponente.cpf          CPF do segurado (11 dígitos, sem pontuação)
  - nome / proponente.nome        Nome completo do segurado
  - sexo / proponente.sexo        "M" ou "F"
  - data_nascimento / proponente.data_nascimento  "YYYY-MM-DD"
  - cep_pernoite   CEP de pernoite do veículo (8 dígitos)
  - codigo_fipe    Código FIPE do veículo (ex: "023108-8")
  - ano_modelo     Ano modelo do veículo (int ou string)

Aceita tanto chaves planas quanto aninhadas sob 'proponente' (formato frontend).

Campos opcionais:
  - placa, chassi, zero_km, ja_segurado, bonus_anterior (0-10),
    condutor_menor_24, finalidade, comissao_pct,
    condutor_cpf, condutor_nome, condutor_sexo,
    condutor_nascimento, condutor_parentesco, insurer_code

Campos obrigatórios em dados_negocio para transmitir():
  - email              E-mail do segurado
  - telefone           Celular do segurado (ou via proponente.telefone)
  - coverages_selected  Dict peril→peril_option (do payload_resposta da cotação)
  - policy_type        "monthly" ou "annual" (default: "monthly")

Campos opcionais em dados_negocio:
  - ci_code           Código CI da apólice anterior (obrigatório quando bonus_anterior > 0;
                      consta no PDF da apólice — não é retornado pelo /policy/export)
  - installments      Número de parcelas (obrigatório para annual)
  - scheduling_date   Data de início de vigência futura
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx

from app.adapters.base import (
    Capacidades,
    MovimentoCanonico,
    PropostaCanonica,
    ResultadoCotacao,
    ResultadoTransmissao,
    RiscoCanonico,
)
from app.adapters.justos import client


def _dec(valor: float) -> Decimal:
    return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _selecionar_coberturas(
    coverages_available: dict[str, Any],
) -> dict[str, str | None]:
    """Para perils obrigatórios escolhe a opção mais barata; opcional → null."""
    selected: dict[str, str | None] = {}
    for slug, peril in coverages_available.items():
        options: list[dict[str, Any]] = peril.get("peril_options", [])
        if not options:
            selected[slug] = None
            continue
        if peril.get("mandatory"):
            cheapest = min(options, key=lambda o: float(o.get("price", 0)))
            selected[slug] = str(cheapest["slug"])
        else:
            selected[slug] = None
    return selected


def _mapear_finalidade(finalidade: str) -> str:
    mapa: dict[str, str] = {
        "lazer": "personal",
        "pessoal": "personal",
        "personal": "personal",
        "comercial": "commercial",
        "commercial": "commercial",
        "app": "app_driver",
        "app_driver": "app_driver",
        "uber": "app_driver",
        "taxi": "taxi",
    }
    return mapa.get(finalidade.lower(), "personal")


def _nome_social(nome_completo: str) -> str:
    partes = nome_completo.strip().split()
    return partes[0] if partes else nome_completo


def _payload_cotacao(dados: dict[str, Any]) -> dict[str, Any]:
    """Mapeia dados_risco canônicos → payload da API Justos v2.

    Aceita chaves planas ou aninhadas sob 'proponente' (formato do frontend).
    Chaves planas têm precedência para compatibilidade retroativa.
    """
    prop: dict[str, Any] = dados.get("proponente") or {}
    cpf = str(dados.get("cpf") or prop.get("cpf") or "")
    nome = str(dados.get("nome") or prop.get("nome") or "")
    sexo = str(dados.get("sexo") or prop.get("sexo") or "")
    nascimento = str(
        dados.get("data_nascimento")
        or prop.get("data_nascimento")
        or dados.get("nascimento")
        or prop.get("nascimento")
        or ""
    )
    cep = str(dados.get("cep_pernoite") or dados.get("cep") or "")
    codigo_fipe = str(dados.get("codigo_fipe") or dados.get("fipe_codigo") or "")
    ano_modelo = str(dados.get("ano_modelo") or "")

    if not cpf:
        raise ValueError("cpf é obrigatório para cotação Justos")
    if not codigo_fipe:
        raise ValueError("codigo_fipe é obrigatório para cotação Justos")
    if not ano_modelo:
        raise ValueError("ano_modelo é obrigatório para cotação Justos")

    insured: dict[str, Any] = {
        "cpf_cnpj": cpf,
        "legal_name": nome,
        "social_name": _nome_social(nome),
        "cep": cep,
    }
    if sexo:
        insured["gender"] = sexo
    if nascimento:
        insured["birth_date"] = nascimento

    payload: dict[str, Any] = {
        "plate": str(dados.get("placa") or ""),
        "chassis": str(dados.get("chassi") or ""),
        "insured": insured,
        "vehicle_fipe_code": codigo_fipe,
        "vehicle_model_year": ano_modelo,
        "vehicle_overnight_cep": cep,
        "vehicle_use": _mapear_finalidade(str(dados.get("finalidade") or "pessoal")),
        "is_zero_km": bool(dados.get("zero_km", False)),
        "under_24": bool(dados.get("condutor_menor_24", False)),
        "is_insured": bool(dados.get("ja_segurado", False)),
        "previous_bonus": str(dados.get("bonus_anterior") or "0"),
        "broker_commission_percentage": int(dados.get("comissao_pct") or 15),  # faixa 0–25; omitido → default do corretor (15)
    }

    condutor_cpf = str(dados.get("condutor_cpf") or "")
    if condutor_cpf:
        condutor_nome = str(dados.get("condutor_nome") or "")
        payload["main_driver"] = {
            "cpf": condutor_cpf,
            "legal_name": condutor_nome,
            "social_name": _nome_social(condutor_nome),
            "gender": str(dados.get("condutor_sexo") or ""),
            "birth_date": str(dados.get("condutor_nascimento") or ""),
            "relationship": str(dados.get("condutor_parentesco") or "other"),
        }

    insurer_code = dados.get("insurer_code")
    if insurer_code is not None:
        payload["insurer_code"] = int(insurer_code)

    return payload


class JustosSeguradora:
    """Adapter para a API Justos — somente ramo auto."""

    def capacidades(self) -> Capacidades:
        return Capacidades(
            ramos=["auto"],
            coberturas=[
                "colisao-e-desastres-naturais",
                "roubo-e-furto",
                "incendio",
                "danos-materiais",
                "danos-corporais",
                "assistencia-24h",
                "morte-e-invalidez",
                "backup-car",
                "assistencia-vidros",
                "danos-morais",
            ],
            franquias=["franquia-5", "franquia-15", "franquia-25"],
            parcelamentos=["AVISTA", "2X", "3X", "6X", "10X", "12X"],
        )

    async def cotar(self, r: RiscoCanonico) -> ResultadoCotacao:
        if r.ramo != "auto":
            return ResultadoCotacao(
                sucesso=False,
                cotacao_id=None,
                premio_total=None,
                mensagens=[f"Justos não suporta ramo '{r.ramo}'."],
            )

        try:
            payload = _payload_cotacao(dict(r.dados))
        except (KeyError, ValueError) as exc:
            return ResultadoCotacao(
                sucesso=False,
                cotacao_id=None,
                premio_total=None,
                mensagens=[f"Dados insuficientes para cotação Justos: {exc}"],
            )

        try:
            cotacao_resp = await client.criar_cotacao(payload)
            quote_id = str(cotacao_resp["quote_id"])
            coverages_available: dict[str, Any] = cotacao_resp.get(
                "coverages_available", {}
            )
            coverages_selected = _selecionar_coberturas(coverages_available)
            pricing_resp = await client.calcular_preco(quote_id, coverages_selected)
        except httpx.HTTPStatusError as exc:
            trecho = exc.response.text[:300]
            return ResultadoCotacao(
                sucesso=False,
                cotacao_id=None,
                premio_total=None,
                mensagens=[f"API Justos {exc.response.status_code}: {trecho}"],
            )

        monthly_total: float = pricing_resp.get("monthly", {}).get("total", 0.0)
        annual_total: float = pricing_resp.get("annual", {}).get("total", 0.0)
        info_text: str = pricing_resp.get("info", "")

        mensagens: list[str] = []
        if info_text:
            mensagens.append(info_text)

        return ResultadoCotacao(
            sucesso=True,
            cotacao_id=quote_id,
            premio_total=_dec(monthly_total),
            mensagens=mensagens,
            payload_resposta={
                "quote_id": quote_id,
                "coverages_selected": coverages_selected,
                "coverages_available": coverages_available,
                "monthly_total": monthly_total,
                "annual_total": annual_total,
                "info": info_text,
                # Campos extras do retorno da cotação (úteis para a UI)
                "fipe_price_percentage_covered": cotacao_resp.get(
                    "fipe_price_percentage_covered"
                ),
                "commission": cotacao_resp.get("commission"),
                "plans": cotacao_resp.get("plans", []),
            },
        )

    async def recotar(self, id: str, r: RiscoCanonico) -> ResultadoCotacao:
        # Justos não tem re-cotação a partir de ID; cria nova cotação
        return await self.cotar(r)

    async def transmitir(self, p: PropostaCanonica) -> ResultadoTransmissao:
        """Seleciona coberturas, formaliza proposta e retorna link de checkout."""
        quote_id = p.cotacao_id
        dados: dict[str, Any] = dict(p.dados_negocio)
        risco_dados: dict[str, Any] = dict(p.risco.dados)
        prop: dict[str, Any] = risco_dados.get("proponente") or {}

        # Preferência: dados_negocio; fallback: dados_risco.proponente
        email = str(
            dados.get("email") or prop.get("email") or risco_dados.get("email") or ""
        )
        telefone = str(
            dados.get("telefone")
            or prop.get("telefone")
            or risco_dados.get("telefone")
            or ""
        )
        policy_type = str(dados.get("policy_type") or "monthly")
        installments_raw = dados.get("installments")
        installments: int | None = int(installments_raw) if installments_raw else None
        scheduling_date_raw = dados.get("scheduling_date")
        scheduling_date: str | None = (
            str(scheduling_date_raw) if scheduling_date_raw else None
        )
        ci_code: str | None = str(dados["ci_code"]) if dados.get("ci_code") else None
        coverages_selected: dict[str, Any] = dict(dados.get("coverages_selected") or {})

        if not coverages_selected:
            return ResultadoTransmissao(
                sucesso=False,
                protocolo=None,
                mensagens=["coverages_selected obrigatório em dados_negocio."],
            )

        try:
            await client.selecionar_coberturas(
                quote_id, coverages_selected, policy_type
            )
            await client.converter_proposta(
                quote_id,
                email=email,
                telefone=telefone,
                policy_type=policy_type,
                installments=installments,
                scheduling_date=scheduling_date,
                ci_code=ci_code,
            )
            links = await client.obter_checkout_link(quote_id)
        except httpx.HTTPStatusError as exc:
            trecho = exc.response.text[:300]
            return ResultadoTransmissao(
                sucesso=False,
                protocolo=None,
                mensagens=[f"API Justos {exc.response.status_code}: {trecho}"],
            )

        protocolo = str(
            links.get("app_download_url") or links.get("checkout_url") or quote_id
        )
        return ResultadoTransmissao(sucesso=True, protocolo=protocolo)

    async def movimentos(self, desde: date) -> list[MovimentoCanonico]:
        """Busca apólices vendidas desde `desde` via paginação."""
        desde_dt = datetime(desde.year, desde.month, desde.day, tzinfo=UTC)
        all_policies: list[dict[str, Any]] = []
        skip = 0
        take = 100

        while True:
            try:
                resp = await client.exportar_apolices(desde_dt, skip=skip, take=take)
            except httpx.HTTPStatusError:
                break
            data: list[dict[str, Any]] = resp.get("data", [])
            all_policies.extend(data)
            if len(data) < take:
                break
            skip += take

        result: list[MovimentoCanonico] = []
        for policy in all_policies:
            policy_id = str(policy.get("policyId") or "")
            if not policy_id:
                continue

            updated_at_str = str(policy.get("updatedAt") or "")
            try:
                updated_at = datetime.fromisoformat(
                    updated_at_str.replace("Z", "+00:00")
                )
                data_evento = updated_at.date()
            except ValueError:
                data_evento = desde

            status = str(policy.get("status") or "")
            tipo = "cancelamento" if status == "INACTIVE" else "emissao"

            premium_data: dict[str, Any] = policy.get("premium") or {}
            total_premium = premium_data.get("totalPremium")
            valor = _dec(float(total_premium)) if total_premium is not None else None

            result.append(
                MovimentoCanonico(
                    id_movimento=policy_id,
                    tipo=tipo,
                    data=data_evento,
                    valor=valor,
                    dados={
                        "status": status,
                        "policy_type": str(policy.get("policyType") or ""),
                        "valid_from": str(policy.get("validFrom") or ""),
                        "valid_until": str(policy.get("validUntil") or ""),
                        "insurer_policy_number": str(
                            policy.get("insurerPolicyNumber") or ""
                        ),
                        "commission": policy.get("commission") or {},
                        "vehicle": policy.get("vehicle") or {},
                    },
                )
            )

        return result
