"""
Porta de seguradora — interface canônica entre o domínio e qualquer seguradora.

Regra dura: nenhum tipo, campo ou código específico de seguradora (ex: Yelum)
atravessa este módulo. O teste de arquitetura no CI garante isso.

Adicionar uma nova seguradora = implementar PortaSeguradora. Zero mudança aqui.
"""

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

    ramos: list[str]
    coberturas: list[str]
    franquias: list[str]
    parcelamentos: list[str]
    # Faixa de comissão aceita, em pontos percentuais. O padrão é permissivo:
    # só a seguradora que impõe limite precisa declará-lo.
    comissao_min: int = 0
    comissao_max: int = 100


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
    """`protocolo` identifica a proposta de forma estável e durável.

    Links voláteis (checkout, download) vão em `dados` e não são persistidos:
    proposta transmitida não é apólice emitida.
    """

    sucesso: bool
    protocolo: str | None
    mensagens: list[str] = field(default_factory=list)
    dados: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MovimentoCanonico:
    """Evento imutável vindo do E-Retorno."""

    id_movimento: str
    tipo: str  # "emissao"|"parcela"|"comissao"|"sinistro"|"cancelamento"
    data: date
    valor: Decimal | None
    dados: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Interface da porta
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SelecaoTransmissao:
    """O que o usuário escolheu; `comissao_pct` é fração (0–1), não percentual."""

    opcao_pagamento: int | None
    parcelas: int
    inicio_vigencia: date | None
    dados_negocio: dict[str, object]
    comissao_pct: Decimal


@dataclass(frozen=True)
class PreparacaoTransmissao:
    """`comissao_pct` é a comissão que a seguradora confirma, não a digitada."""

    dados_negocio: dict[str, object]
    plano_pagamento: str
    valor_parcela: Decimal
    condicao_pagamento: dict[str, object]
    comissao_pct: Decimal


@dataclass(frozen=True)
class SeguradoraAnterior:
    """Seguradora da apólice anterior, usada só em renovação."""

    codigo: int
    nome: str


class CondicaoTransmissaoError(ValueError):
    """Mensagem segura para revisão pelo usuário, sem resposta bruta do provedor."""


@runtime_checkable
class PreparadorTransmissao(Protocol):
    """Capacidade opcional; adapters legados mantêm seu fluxo de transmissão."""

    def preparar_transmissao(
        self, payload: dict[str, object], selecao: SelecaoTransmissao
    ) -> PreparacaoTransmissao: ...


@runtime_checkable
class CatalogoRenovacao(Protocol):
    """Capacidade opcional: catálogo de seguradoras aceitas na renovação."""

    async def seguradoras_anteriores(self) -> list[SeguradoraAnterior]: ...


@runtime_checkable
class PortaSeguradora(Protocol):
    """
    Interface que toda seguradora deve implementar.

    `capacidades()` é síncrono — resposta local, sem IO.
    Os demais métodos são assíncronos pois envolvem rede ou latência simulada.
    """

    def capacidades(self) -> Capacidades: ...

    async def cotar(self, r: RiscoCanonico) -> ResultadoCotacao: ...

    async def recotar(self, id: str, r: RiscoCanonico) -> ResultadoCotacao: ...

    async def transmitir(self, p: PropostaCanonica) -> ResultadoTransmissao: ...

    async def movimentos(self, desde: date) -> list[MovimentoCanonico]: ...
