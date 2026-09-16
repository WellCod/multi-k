"""Adapter Justos — implementa PortaSeguradora para a API Justos.

Ramo suportado: auto (veículos).

Campos obrigatórios em dados_risco para ramo=auto:
  - cpf / proponente.cpf          CPF (11) ou CNPJ (14) do segurado, sem
                                  pontuação. PJ dispensa sexo e nascimento.
  - nome / proponente.nome        Nome completo ou razão social do segurado
  - sexo / proponente.sexo        "M" ou "F" — só PF
  - data_nascimento / proponente.data_nascimento  "YYYY-MM-DD" — só PF
  - cep_pernoite   CEP de pernoite do veículo (8 dígitos)
  - codigo_fipe    Código FIPE do veículo (ex: "023108-8")
  - ano_modelo     Ano modelo do veículo (int ou string)
  - finalidade     Uso do veículo; enum fechado da Justos (vehicle_use)

Aceita tanto chaves planas quanto aninhadas sob 'proponente' (formato frontend).

Campos opcionais:
  - placa, chassi, zero_km, ja_segurado, bonus_anterior (0-10),
    condutor_menor_24, finalidade, condutor_cpf, condutor_nome, condutor_sexo,
    condutor_nascimento, condutor_parentesco, insurer_code
  - cep_segurado    CEP do segurado, distinto do pernoite. Ausente, repete o
                    CEP de pernoite (compatibilidade com cotações antigas).
  - nome_social     Nome social do segurado. Nunca inferido do nome legal.
  - condutor_nome_social  Nome social do condutor principal.
  - leilao          Veículo de leilão (is_auction).
  - comissao_pct    Fração (0.10–0.25); default 0.15. Entra no preço da
                    seguradora, então a transmissão exige o mesmo valor.
  - tipo_negocio    "novo" (default) ou "renovacao". Declarado, nunca
                    inferido do bônus.
  - ci_code         Código CI da apólice anterior; obrigatório quando
                    tipo_negocio = "renovacao".

Campos obrigatórios em dados_negocio para transmitir():
  - email              E-mail do segurado
  - telefone           Celular do segurado (ou via proponente.telefone)
  - coverages_selected  Dict peril→peril_option (do payload_resposta da cotação)
  - policy_type        "monthly" ou "annual" (default: "monthly")

Campos opcionais em dados_negocio:
  - ci_code           Sobrepõe o ci_code declarado no risco; consta no PDF
                      da apólice, não é retornado pelo /policy/export
  - installments      Número de parcelas (obrigatório para annual)
  - scheduling_date   Data de início de vigência futura
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.adapters.base import (
    Capacidades,
    MovimentoCanonico,
    PreparacaoTransmissao,
    PropostaCanonica,
    ResultadoCotacao,
    ResultadoTransmissao,
    RiscoCanonico,
    SeguradoraAnterior,
    SelecaoTransmissao,
)
from app.adapters.justos import client
from app.adapters.justos.payment import (
    payment_options,
    prepare_transmission,
    to_decimal,
)

_log = logging.getLogger(__name__)


def _total(pricing: dict[str, Any], periodo: str) -> Decimal | None:
    """Total explícito do período; resposta incompleta não vira prêmio zero."""
    secao = pricing.get(periodo)
    return to_decimal(secao.get("total")) if isinstance(secao, dict) else None


# Perils considerados obrigatórios/core quando a API staging retorna mandatory=False
# para todos (quirk do ambiente de testes). Em produção os flags mandatory corretos
# chegam da API e esse conjunto é ignorado.
_PERILS_CORE = {
    "colisao-e-desastres-naturais",
    "roubo-e-furto",
    "incendio",
    "danos-materiais",
    "danos-corporais",
}


def _selecionar_coberturas(
    coverages_available: dict[str, Any],
) -> dict[str, str | None]:
    """Monta coverages_selected seguindo as regras da API Justos:

    - peril mandatory → opção mais barata
    - peril optional + há mandatory → null
    - staging quirk (nenhum mandatory): seleciona mais barato só para _PERILS_CORE;
      demais ficam null (evita inflar o prêmio com add-ons opcionais)
    - peril sem opções → omitido
    """
    perils_com_opcoes = {
        slug: peril
        for slug, peril in coverages_available.items()
        if peril.get("peril_options")
    }
    tem_mandatory = any(p.get("mandatory") for p in perils_com_opcoes.values())

    selected: dict[str, str | None] = {}
    for slug, peril in perils_com_opcoes.items():
        options: list[dict[str, Any]] = peril["peril_options"]
        is_core = slug in _PERILS_CORE
        if peril.get("mandatory") or (not tem_mandatory and is_core):
            # Opção sem preço não é opção grátis: fica de fora da comparação.
            precificadas = [
                (preco, o) for o in options if (preco := to_decimal(o.get("price")))
            ]
            if not precificadas:
                raise ValueError(f"Justos não informou preço para a cobertura {slug}")
            selected[slug] = str(min(precificadas, key=lambda par: par[0])[1]["slug"])
        else:
            selected[slug] = None
    return selected


_TIPOS_NEGOCIO = ("novo", "renovacao")


def _tipo_negocio(dados: dict[str, Any]) -> str:
    """Natureza declarada do negócio; ausência é negócio novo, lixo é erro."""
    bruto = str(dados.get("tipo_negocio") or "novo").strip().lower()
    if bruto not in _TIPOS_NEGOCIO:
        raise ValueError(f"tipo_negocio inválido: {bruto!r}")
    return bruto


# J2 §4: vehicle_use e relationship são enums fechados. Valor fora da lista
# muda o risco precificado, então vira erro em vez de default silencioso.
_FINALIDADES = {
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

_PARENTESCOS = {
    "conjuge": "spouse",
    "spouse": "spouse",
    "pai": "parent",
    "mae": "parent",
    "parent": "parent",
    "filho": "child",
    "filha": "child",
    "child": "child",
    "irmao": "sibling",
    "irma": "sibling",
    "sibling": "sibling",
    "empregado": "employee",
    "employee": "employee",
    "socio": "business_partner",
    "business_partner": "business_partner",
    "outro": "other",
    "other": "other",
}


def _mapear_finalidade(finalidade: str) -> str:
    chave = finalidade.strip().lower()
    if chave not in _FINALIDADES:
        raise ValueError(f"finalidade fora do enum da Justos: {finalidade!r}")
    return _FINALIDADES[chave]


def _mapear_parentesco(parentesco: str) -> str:
    chave = parentesco.strip().lower()
    if chave not in _PARENTESCOS:
        raise ValueError(f"condutor_parentesco fora do enum da Justos: {parentesco!r}")
    return _PARENTESCOS[chave]


def _validar_contato(email: str, telefone: str) -> str | None:
    """Devolve a pendência de contato, ou None quando está tudo presente."""
    if "@" not in email.strip("@ "):
        return "E-mail do segurado é obrigatório para formalizar a proposta."
    if len([c for c in telefone if c.isdigit()]) < 10:
        return (
            "Telefone do segurado é obrigatório para formalizar a proposta "
            "(DDD e número)."
        )
    return None


def _documento(valor: str) -> str:
    """CPF (11) ou CNPJ (14) — J2 §4 aceita ambos em insured.cpf_cnpj."""
    digitos = "".join(c for c in valor if c.isdigit())
    if len(digitos) not in (11, 14):
        raise ValueError("documento do segurado deve ter 11 dígitos (CPF) ou 14 (CNPJ)")
    return digitos


# J1/J2 §4: broker_commission_percentage é inteiro, de 10 a 25.
_COMISSAO_MIN = 10
_COMISSAO_MAX = 25
_COMISSAO_PADRAO = 15


def _comissao_cotada(dados: dict[str, Any]) -> int:
    """Percentual inteiro enviado na cotação, a partir da fração canônica.

    A comissão entra no preço da seguradora. Fora da faixa é erro, não
    arredondamento silencioso: senão o prêmio cotado e a comissão registrada
    localmente passam a contar histórias diferentes.
    """
    bruto = dados.get("comissao_pct")
    if bruto is None or bruto == "":
        return _COMISSAO_PADRAO
    try:
        pct = Decimal(str(bruto)) * 100
    except InvalidOperation as exc:
        raise ValueError(f"comissao_pct inválida: {bruto!r}") from exc
    if pct != pct.to_integral_value():
        raise ValueError(f"comissao_pct deve ser percentual inteiro; recebido {pct}%.")
    valor = int(pct)
    if not _COMISSAO_MIN <= valor <= _COMISSAO_MAX:
        raise ValueError(
            "comissao_pct fora da faixa aceita pela Justos "
            f"({_COMISSAO_MIN}%–{_COMISSAO_MAX}%): {valor}%."
        )
    return valor


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
    cep_pernoite = str(dados.get("cep_pernoite") or dados.get("cep") or "")
    # J2 §4: o CEP do segurado é distinto do pernoite. Cotações antigas só
    # trazem um CEP — repeti-lo preserva o dado em vez de esvaziá-lo.
    cep_segurado = (
        str(dados.get("cep_segurado") or prop.get("cep") or "") or cep_pernoite
    )
    codigo_fipe = str(dados.get("codigo_fipe") or dados.get("fipe_codigo") or "")
    ano_modelo = str(dados.get("ano_modelo") or "")

    if not cpf:
        raise ValueError("cpf é obrigatório para cotação Justos")
    if not codigo_fipe:
        raise ValueError("codigo_fipe é obrigatório para cotação Justos")
    if not ano_modelo:
        raise ValueError("ano_modelo é obrigatório para cotação Justos")

    documento = _documento(cpf)
    insured: dict[str, Any] = {
        "cpf_cnpj": documento,
        "legal_name": nome,
        "cep": cep_segurado,
    }
    # Nome social é declarado pelo segurado; deduzi-lo do nome legal é inventar.
    nome_social = str(dados.get("nome_social") or prop.get("nome_social") or "").strip()
    if nome_social:
        insured["social_name"] = nome_social
    # J2 §4: gênero e nascimento só se aplicam quando o segurado é PF.
    if len(documento) == 11:
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
        "vehicle_overnight_cep": cep_pernoite,
        "vehicle_use": _mapear_finalidade(str(dados.get("finalidade") or "")),
        "is_zero_km": bool(dados.get("zero_km", False)),
        "under_24": bool(dados.get("condutor_menor_24", False)),
        "is_insured": bool(dados.get("ja_segurado", False)),
        "is_auction": bool(dados.get("leilao", dados.get("is_auction", False))),
        "previous_bonus": str(dados.get("bonus_anterior") or "0"),
        "broker_commission_percentage": _comissao_cotada(dados),
    }

    condutor_cpf = "".join(
        c for c in str(dados.get("condutor_cpf") or "") if c.isdigit()
    )
    if condutor_cpf:
        # J2 §4: o bloco main_driver é omitido quando o segurado dirige. Uma vez
        # presente, os campos deixam de ser opcionais — enviar vazio é pior que
        # não enviar, porque a seguradora precifica com o que recebe.
        if len(condutor_cpf) != 11:
            raise ValueError("condutor_cpf deve ter 11 dígitos")
        obrigatorios = {
            "condutor_nome": str(dados.get("condutor_nome") or "").strip(),
            "condutor_sexo": str(dados.get("condutor_sexo") or "").strip(),
            "condutor_nascimento": str(dados.get("condutor_nascimento") or "").strip(),
        }
        faltando = sorted(campo for campo, valor in obrigatorios.items() if not valor)
        if faltando:
            raise ValueError(
                "condutor principal informado exige " + ", ".join(faltando)
            )
        condutor: dict[str, Any] = {
            "cpf": condutor_cpf,
            "legal_name": obrigatorios["condutor_nome"],
            "gender": obrigatorios["condutor_sexo"],
            "birth_date": obrigatorios["condutor_nascimento"],
            "relationship": _mapear_parentesco(
                str(dados.get("condutor_parentesco") or "outro")
            ),
        }
        condutor_social = str(dados.get("condutor_nome_social") or "").strip()
        if condutor_social:
            condutor["social_name"] = condutor_social
        payload["main_driver"] = condutor

    # J2 §4.2: o código da seguradora anterior só existe em renovação.
    insurer_code = dados.get("insurer_code")
    if insurer_code is not None and str(insurer_code).strip() != "":
        if _tipo_negocio(dados) != "renovacao":
            raise ValueError("insurer_code só se aplica a renovação")
        payload["insurer_code"] = int(insurer_code)

    return payload


class JustosSeguradora:
    """Adapter para a API Justos — somente ramo auto."""

    def preparar_transmissao(
        self, payload: dict[str, object], selecao: SelecaoTransmissao
    ) -> PreparacaoTransmissao:
        return prepare_transmission(payload, selecao)

    async def seguradoras_anteriores(self) -> list[SeguradoraAnterior]:
        """Catálogo para renovação; entrada sem código utilizável é descartada."""
        catalogo: list[SeguradoraAnterior] = []
        for item in await client.listar_seguradoras():
            codigo = item.get("code")
            nome = str(item.get("name") or "").strip()
            if not isinstance(codigo, int) or isinstance(codigo, bool) or not nome:
                continue
            catalogo.append(SeguradoraAnterior(codigo=codigo, nome=nome))
        return sorted(catalogo, key=lambda s: s.nome)

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
            comissao_min=_COMISSAO_MIN,
            comissao_max=_COMISSAO_MAX,
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
            _log.info(
                "justos.pricing quote_id=%s available_keys=%s selected=%s",
                quote_id,
                list(coverages_available.keys()),
                coverages_selected,
            )
            pricing_resp = await client.calcular_preco(quote_id, coverages_selected)
            await client.selecionar_coberturas(quote_id, coverages_selected)
        except httpx.HTTPStatusError as exc:
            return ResultadoCotacao(
                sucesso=False,
                cotacao_id=None,
                premio_total=None,
                mensagens=[
                    f"Justos não concluiu a cotação (HTTP {exc.response.status_code}). "
                    "Revise os dados ou tente novamente mais tarde."
                ],
            )
        except ValueError as exc:
            return ResultadoCotacao(
                sucesso=False,
                cotacao_id=None,
                premio_total=None,
                mensagens=[f"Resposta da Justos incompleta: {exc}"],
            )

        monthly_total = _total(pricing_resp, "monthly")
        annual_total = _total(pricing_resp, "annual")
        if monthly_total is None:
            return ResultadoCotacao(
                sucesso=False,
                cotacao_id=None,
                premio_total=None,
                mensagens=[
                    "Justos não informou o prêmio mensal. "
                    "Recalcule antes de comparar ou transmitir."
                ],
            )
        # J4: info é texto informativo da seguradora. Não vira mensagem do
        # sistema nem fonte de preço — segue em campo próprio.
        info_text = str(pricing_resp.get("info") or "")

        return ResultadoCotacao(
            sucesso=True,
            cotacao_id=quote_id,
            premio_total=monthly_total,
            mensagens=[],
            payload_resposta={
                "quote_id": quote_id,
                "coverages_selected": coverages_selected,
                # Comissão de fato cotada: a transmissão não pode divergir dela.
                "comissao_pct_cotada": str(
                    Decimal(payload["broker_commission_percentage"]) / 100
                ),
                "coverages_available": coverages_available,
                "monthly_total": str(monthly_total),
                "annual_total": str(annual_total) if annual_total is not None else None,
                "condicoes_pagamento": [
                    p.model_dump() for p in payment_options(pricing_resp)
                ],
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
        ci_bruto = dados.get("ci_code") or risco_dados.get("ci_code")
        ci_code: str | None = str(ci_bruto) if ci_bruto else None
        coverages_selected: dict[str, Any] = dict(dados.get("coverages_selected") or {})

        try:
            tipo_negocio = _tipo_negocio(risco_dados)
        except ValueError as exc:
            return ResultadoTransmissao(
                sucesso=False, protocolo=None, mensagens=[str(exc)]
            )

        # J2 §7: renovação exige o CI da apólice anterior. Bônus não indica
        # renovação — a natureza do negócio vem declarada, nunca inferida.
        if tipo_negocio == "renovacao" and not ci_code:
            return ResultadoTransmissao(
                sucesso=False,
                protocolo=None,
                mensagens=[
                    "Renovação exige o código CI da apólice anterior, "
                    "que consta no PDF da apólice."
                ],
            )

        # J2 §7: e-mail e telefone vão na formalização; validar antes evita
        # queimar a tentativa de transmissão com dado obviamente ausente.
        contato = _validar_contato(email, telefone)
        if contato is not None:
            return ResultadoTransmissao(
                sucesso=False, protocolo=None, mensagens=[contato]
            )

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
            return ResultadoTransmissao(
                sucesso=False,
                protocolo=None,
                mensagens=[
                    "Justos não confirmou a transmissão "
                    f"(HTTP {exc.response.status_code}). "
                    "Verifique a situação na seguradora antes de repetir o envio."
                ],
            )

        # J2 §8: o identificador estável é a cotação formalizada. O link de
        # checkout é volátil, não cabe na coluna de protocolo e não significa
        # apólice emitida — segue à parte, para o corretor enviar quando quiser.
        return ResultadoTransmissao(
            sucesso=True,
            protocolo=quote_id,
            dados={
                chave: str(links[chave])
                for chave in ("checkout_url", "app_download_url")
                if links.get(chave)
            },
        )

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
            valor = to_decimal(premium_data.get("totalPremium"))

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
