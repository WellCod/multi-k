"""Adapter Yelum (Grupo HDI Seguros) — implementa PortaSeguradora.

Ramo suportado: residencia (produto 11030 — Residência Yelum).
Auto: aguarda documentação do ponto focal (§10 do escopo).

Campos obrigatórios em dados_risco para ramo=residencia:
  - cpf              CPF do proponente (11 dígitos, sem pontuação)
  - nome             Nome completo
  - nascimento       "YYYY-MM-DD"
  - sexo             "M" ou "F"
  - estado_civil     código de domínio Yelum (ex: "1"=Solteiro, "2"=Casado)
  - profissao        código OccupationCode do domínio Yelum
  - email            e-mail do proponente
  - telefone         celular (somente dígitos, com DDD)
  - cep              CEP do imóvel (8 dígitos)
  - tipo_imovel      "casa" | "apartamento" | "condominio"
  - tipo_construcao  código ConstructionType do domínio Yelum (ex: "1"=Alvenaria)
  - valor_imovel     Decimal — LMI do imóvel
  - inicio_vigencia  "YYYY-MM-DD"
  - fim_vigencia     "YYYY-MM-DD"
  - coberturas       lista de CoverageCodes Yelum (ex: ["CBE10", "CBE20"])

Campos opcionais:
  - valor_conteudo   Decimal (default 0)
  - alarme           bool (default False)
  - cerca_eletrica   bool (default False)
  - grades           bool (default False)
  - comissao_pct     int (default 20)

Campos obrigatórios em dados_negocio para transmitir():
  - BrokerCode            código da corretora na Yelum
  - BrokerBranchCode      código da filial
  - broker_proposal_number  BrokerProposalNumber retornado pela cotação
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx

from app.adapters.base import (
    Capacidades,
    MovimentoCanonico,
    PropostaCanonica,
    Restricao,
    ResultadoCotacao,
    ResultadoTransmissao,
    RiscoCanonico,
)
from app.adapters.yelum import client

_PRODUCT_CODE_RESIDENCIA = "11030"


def _bool_yelum(v: bool) -> str:
    """Converte bool para o formato Yelum: "T" ou "F"."""
    return "T" if v else "F"


def _dec(raw: Any) -> Decimal:
    """Normaliza valor monetário da Yelum para Decimal (string ou número)."""
    return Decimal(str(raw)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _sucesso_yelum(resp: dict[str, Any]) -> bool:
    """Yelum usa 'Success' no caminho feliz e 'Sucesso' em erros — aceita ambos."""
    return bool(resp.get("Success") or resp.get("Sucesso"))


def _tipo_imovel_yelum(tipo: str) -> str:
    """Mapeia tipo canônico → PropertyType Yelum. Confirmar códigos com ponto focal."""
    mapa = {
        "casa": "1",
        "apartamento": "2",
        "condominio": "3",
    }
    return mapa.get(tipo.lower(), "1")


def _payload_cotacao(dados: dict[str, Any]) -> dict[str, Any]:
    """Monta o body do POST /quote a partir de dados_risco canônicos.

    Nomes de campo baseados no exemplo da documentação Yelum (§4 do escopo).
    Confirmar nomes exatos com a Collection Postman quando disponível.
    """
    cpf = str(dados.get("cpf") or "")
    nome = str(dados.get("nome") or "")
    nascimento = str(dados.get("nascimento") or dados.get("data_nascimento") or "")
    sexo = str(dados.get("sexo") or "")
    estado_civil = str(dados.get("estado_civil") or "1")
    profissao = str(dados.get("profissao") or "")
    email = str(dados.get("email") or "")
    telefone = str(dados.get("telefone") or "")
    cep = str(dados.get("cep") or "")
    tipo_imovel = str(dados.get("tipo_imovel") or dados.get("tipo") or "casa")
    tipo_construcao = str(dados.get("tipo_construcao") or "1")
    valor_imovel = Decimal(str(dados.get("valor_imovel") or "0"))
    valor_conteudo = Decimal(str(dados.get("valor_conteudo") or "0"))
    alarme = bool(dados.get("alarme", False))
    cerca_eletrica = bool(dados.get("cerca_eletrica", False))
    grades = bool(dados.get("grades", False))
    inicio_vigencia = str(
        dados.get("inicio_vigencia") or dados.get("vigencia_inicio") or ""
    )
    fim_vigencia = str(dados.get("fim_vigencia") or dados.get("vigencia_fim") or "")
    coberturas = list(dados.get("coberturas") or [])
    comissao_pct = int(dados.get("comissao_pct") or 20)

    if not cpf:
        raise ValueError("cpf é obrigatório para cotação Yelum")
    if not cep:
        raise ValueError("cep é obrigatório para cotação Yelum")

    return {
        "CommercialProductCode": _PRODUCT_CODE_RESIDENCIA,
        "Insured": {
            "CpfCnpj": cpf,
            "Name": nome,
            "BirthDate": nascimento,
            "Gender": sexo,
            "MaritalStatus": estado_civil,
            "OccupationCode": profissao,
            "Email": email,
            "Phone": telefone,
        },
        "Risk": {
            "ZipCode": cep,
            "PropertyType": _tipo_imovel_yelum(tipo_imovel),
            "ConstructionType": tipo_construcao,
            "HasAlarm": _bool_yelum(alarme),
            "HasElectricFence": _bool_yelum(cerca_eletrica),
            "HasBars": _bool_yelum(grades),
            "BuildingValue": str(valor_imovel),
            "ContentValue": str(valor_conteudo),
        },
        "Validity": {
            "StartDate": inicio_vigencia,
            "EndDate": fim_vigencia,
        },
        "Coverages": [{"CoverageCode": c} for c in coberturas],
        "CommissionPct": comissao_pct,
    }


def _payload_proposta(
    risco: RiscoCanonico,
    dados_negocio: dict[str, Any],
    broker_proposal_number: str,
) -> dict[str, Any]:
    """Monta o body do POST /proposal."""
    return {
        "BrokerProposalNumber": broker_proposal_number,
        "BrokerCode": str(dados_negocio.get("BrokerCode") or ""),
        "BrokerBranchCode": str(dados_negocio.get("BrokerBranchCode") or ""),
        "CommissionPct": int(dados_negocio.get("CommissionPct") or 20),
        "Risk": _payload_cotacao(dict(risco.dados)).get("Risk", {}),
        "Insured": _payload_cotacao(dict(risco.dados)).get("Insured", {}),
        "Coverages": _payload_cotacao(dict(risco.dados)).get("Coverages", []),
        "Validity": _payload_cotacao(dict(risco.dados)).get("Validity", {}),
    }


class YelumSeguradora:
    """Adapter para a API Yelum — ramo residencia (produto 11030)."""

    def capacidades(self) -> Capacidades:
        return Capacidades(
            ramos=["residencia"],
            coberturas=[
                "CBE10",  # Incêndio, Raio e Explosão (obrigatória)
                "CBE20",  # Danos Elétricos
                "CBE30",  # Roubo e Furto de Bens
                "CBE40",  # Vendaval, Granizo e Queda de Aeronaves
                "CBE50",  # Responsabilidade Civil Familiar
                "CBE60",  # Quebra de Vidros
                "CBE70",  # Aluguel
                "CBE80",  # Desmoronamento
            ],
            franquias=[],
            parcelamentos=["AVISTA", "2X", "3X", "6X", "10X", "12X"],
        )

    async def cotar(self, r: RiscoCanonico) -> ResultadoCotacao:
        if r.ramo != "residencia":
            return ResultadoCotacao(
                sucesso=False,
                cotacao_id=None,
                premio_total=None,
                mensagens=[f"Yelum não suporta ramo '{r.ramo}'."],
            )

        try:
            payload = _payload_cotacao(dict(r.dados))
        except (KeyError, ValueError) as exc:
            return ResultadoCotacao(
                sucesso=False,
                cotacao_id=None,
                premio_total=None,
                mensagens=[f"Dados insuficientes para cotação Yelum: {exc}"],
            )

        try:
            resp = await client.cotar(payload)
        except httpx.HTTPStatusError as exc:
            trecho = exc.response.text[:300]
            return ResultadoCotacao(
                sucesso=False,
                cotacao_id=None,
                premio_total=None,
                mensagens=[f"API Yelum {exc.response.status_code}: {trecho}"],
            )

        if not _sucesso_yelum(resp):
            raw = resp.get("Messages") or resp.get("Mensagens") or []
            msgs = [str(m) for m in raw]
            return ResultadoCotacao(
                sucesso=False,
                cotacao_id=None,
                premio_total=None,
                mensagens=msgs or ["Cotação recusada pela Yelum."],
            )

        broker_proposal_number = str(resp.get("BrokerProposalNumber") or "")
        # TotalPremiumValue é número no topo (não string)
        raw_premio = resp.get("TotalPremiumValue") or 0
        premio_total = _dec(raw_premio)

        restricoes_raw = resp.get("Restricao") or resp.get("Restriction") or []
        restricoes = [
            Restricao(
                codigo=str(ri.get("Code") or ri.get("Codigo") or ""),
                mensagem=str(ri.get("Description") or ri.get("Descricao") or ""),
            )
            for ri in restricoes_raw
        ]

        mensagens_raw = (
            resp.get("MensagemInformativa") or resp.get("InformativeMessage") or []
        )
        mensagens = [str(m) for m in mensagens_raw]

        # NeedInspectionRisk é boolean real (não "T"/"F")
        necessita_vistoria = bool(resp.get("NeedInspectionRisk", False))

        return ResultadoCotacao(
            sucesso=True,
            cotacao_id=broker_proposal_number,
            premio_total=premio_total,
            restricoes=restricoes,
            mensagens=mensagens,
            necessita_vistoria=necessita_vistoria,
            payload_resposta=resp,
        )

    async def recotar(self, id: str, r: RiscoCanonico) -> ResultadoCotacao:
        if r.ramo != "residencia":
            return ResultadoCotacao(
                sucesso=False,
                cotacao_id=None,
                premio_total=None,
                mensagens=[f"Yelum não suporta ramo '{r.ramo}'."],
            )

        try:
            payload = _payload_cotacao(dict(r.dados))
        except (KeyError, ValueError) as exc:
            return ResultadoCotacao(
                sucesso=False,
                cotacao_id=None,
                premio_total=None,
                mensagens=[f"Dados insuficientes para re-cotação Yelum: {exc}"],
            )

        try:
            resp = await client.recotar(id, payload)
        except httpx.HTTPStatusError as exc:
            trecho = exc.response.text[:300]
            return ResultadoCotacao(
                sucesso=False,
                cotacao_id=None,
                premio_total=None,
                mensagens=[f"API Yelum {exc.response.status_code}: {trecho}"],
            )

        if not _sucesso_yelum(resp):
            raw = resp.get("Messages") or resp.get("Mensagens") or []
            msgs = [str(m) for m in raw]
            return ResultadoCotacao(
                sucesso=False,
                cotacao_id=None,
                premio_total=None,
                mensagens=msgs or ["Re-cotação recusada pela Yelum."],
            )

        broker_proposal_number = str(resp.get("BrokerProposalNumber") or "")
        raw_premio = resp.get("TotalPremiumValue") or 0
        premio_total = _dec(raw_premio)
        necessita_vistoria = bool(resp.get("NeedInspectionRisk", False))

        return ResultadoCotacao(
            sucesso=True,
            cotacao_id=broker_proposal_number,
            premio_total=premio_total,
            necessita_vistoria=necessita_vistoria,
            payload_resposta=resp,
        )

    async def transmitir(self, p: PropostaCanonica) -> ResultadoTransmissao:
        dados_negocio = dict(p.dados_negocio)
        broker_proposal_number = str(
            dados_negocio.get("broker_proposal_number")
            or dados_negocio.get("BrokerProposalNumber")
            or p.cotacao_id
        )

        payload = _payload_proposta(p.risco, dados_negocio, broker_proposal_number)

        try:
            resp = await client.propor(payload)
        except httpx.HTTPStatusError as exc:
            trecho = exc.response.text[:300]
            return ResultadoTransmissao(
                sucesso=False,
                protocolo=None,
                mensagens=[f"API Yelum {exc.response.status_code}: {trecho}"],
            )

        if not _sucesso_yelum(resp):
            raw = resp.get("Messages") or resp.get("Mensagens") or []
            msgs = [str(m) for m in raw]
            return ResultadoTransmissao(
                sucesso=False,
                protocolo=None,
                mensagens=msgs or ["Proposta recusada pela Yelum."],
            )

        protocolo = str(
            resp.get("ProposalNumber")
            or resp.get("PolicyNumber")
            or broker_proposal_number
        )
        return ResultadoTransmissao(sucesso=True, protocolo=protocolo)

    async def movimentos(self, desde: date) -> list[MovimentoCanonico]:
        """Placeholder — E-Retorno Yelum implementado na Fase 7."""
        return []
