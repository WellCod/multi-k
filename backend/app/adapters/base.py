"""
Porta de seguradora — interface canônica entre o domínio e qualquer seguradora.

Regra dura: nenhum tipo, campo ou código específico de seguradora (ex: Yelum)
atravessa este módulo. O teste de arquitetura no CI garante isso.

Adicionar uma nova seguradora = implementar PortaSeguradora. Zero mudança aqui.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Tipos canônicos de fronteira
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Capacidades:
    """O que uma seguradora suporta — usado para montar a UI sem if/else por cia."""

    ramos: list[str]          # ["auto", "residencia"]
    coberturas: list[str]     # códigos canônicos (não os da seguradora)
    franquias: list[str]
    parcelamentos: list[str]


@dataclass(frozen=True)
class RiscoCanonico:
    """
    Risco agnóstico de seguradora.

    `ramo` é "auto" ou "residencia". `dados` é um dict validado pelo domínio
    (RiscoAuto ou RiscoResidencia) antes de chegar aqui.
    """

    ramo: str
    dados: dict[str, object]


@dataclass(frozen=True)
class Restricao:
    codigo: str
    mensagem: str


@dataclass(frozen=True)
class ResultadoCotacao:
    """
    Três estados possíveis: sucesso, restrição (cotou com ressalvas), erro.

    Restrição não é falha — a cotação existe mas com condicionantes.
    NeedInspectionRisk muda o prazo que o corretor promete ao cliente.
    """

    sucesso: bool
    cotacao_id: str | None
    premio_total: Decimal | None
    restricoes: list[Restricao] = field(default_factory=list)
    mensagens: list[str] = field(default_factory=list)
    necessita_vistoria: bool = False
    # Payload bruto do adapter — cifrado na persistência, nunca logado
    payload_resposta: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class PropostaCanonica:
    """
    Dados suficientes para transmitir uma proposta.

    Reenvia o contrato exato da cotação (payloadOriginal) para garantir
    paridade e evitar divergências entre o que foi cotado e o que foi proposto.
    """

    cotacao_id: str
    risco: RiscoCanonico
    # Blob específico da seguradora (BrokerCode, CommissionPct, etc.)
    # Tipado por adapter, deliberadamente não canônico.
    dados_negocio: dict[str, object]


@dataclass(frozen=True)
class ResultadoTransmissao:
    sucesso: bool
    protocolo: str | None
    mensagens: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MovimentoCanonico:
    """Evento imutável vindo do E-Retorno."""

    id_movimento: str
    tipo: str  # "emissao" | "parcela" | "comissao" | "sinistro" | "cancelamento"
    data: date
    valor: Decimal | None
    dados: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Interface da porta
# ---------------------------------------------------------------------------


@runtime_checkable
class PortaSeguradora(Protocol):
    """
    Interface que toda seguradora deve implementar.

    `capacidades()` é síncrono — resposta local, sem IO.
    Os demais métodos são assíncronos pois envolvem rede ou simulação de latência.
    """

    def capacidades(self) -> Capacidades: ...

    async def cotar(self, r: RiscoCanonico) -> ResultadoCotacao: ...

    async def recotar(self, id: str, r: RiscoCanonico) -> ResultadoCotacao: ...

    async def transmitir(self, p: PropostaCanonica) -> ResultadoTransmissao: ...

    async def movimentos(self, desde: date) -> list[MovimentoCanonico]: ...
