from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class CotacaoCriada:
    cotacao_id: UUID
    usuario_id: UUID
    cia: str
    risco_json: dict[str, object]
    id: UUID = field(default_factory=uuid4)
    ocorrido_em: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class PropostaTransmitida:
    cotacao_id: UUID
    usuario_id: UUID
    protocolo: str | None
    id: UUID = field(default_factory=uuid4)
    ocorrido_em: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class ApoliceEmitida:
    cotacao_id: UUID
    numero_apolice: str
    cia: str
    id: UUID = field(default_factory=uuid4)
    ocorrido_em: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class EndossoRegistrado:
    apolice_id: UUID
    tipo: str
    descricao: str
    id: UUID = field(default_factory=uuid4)
    ocorrido_em: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class ParcelaGerada:
    apolice_id: UUID
    numero: int
    vencimento: date
    valor: Decimal
    id: UUID = field(default_factory=uuid4)
    ocorrido_em: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class ComissaoRegistrada:
    apolice_id: UUID
    valor_previsto: Decimal
    valor_recebido: Decimal | None = None
    id: UUID = field(default_factory=uuid4)
    ocorrido_em: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class SinistroAberto:
    apolice_id: UUID
    numero_sinistro: str
    data_ocorrencia: date
    id: UUID = field(default_factory=uuid4)
    ocorrido_em: datetime = field(default_factory=_now)
