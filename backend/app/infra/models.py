import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.auth import TENANT_ID


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    nome: Mapped[str] = mapped_column(String(255))
    senha_hash: Mapped[str] = mapped_column(Text)
    papel: Mapped[str] = mapped_column(String(20))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(default=lambda: TENANT_ID)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class Sessao(Base):
    __tablename__ = "sessoes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id"), nullable=False
    )
    criada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip_origem: Mapped[str | None] = mapped_column(String(45), default=None)
    tenant_id: Mapped[uuid.UUID] = mapped_column(default=lambda: TENANT_ID)


class TentativaLogin(Base):
    __tablename__ = "tentativas_login"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identificador: Mapped[str] = mapped_column(String(255), index=True)
    contagem: Mapped[int] = mapped_column(Integer, default=0)
    ultima_tentativa: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    bloqueado_ate: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )


class Dominio(Base):
    __tablename__ = "dominio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cia: Mapped[str | None] = mapped_column(String(50), default=None)
    tipo: Mapped[str] = mapped_column(String(50))
    codigo: Mapped[str] = mapped_column(String(50))
    descricao: Mapped[str] = mapped_column(String(255))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(default=lambda: TENANT_ID)

    __table_args__ = (Index("ix_dominio_tipo_codigo", "tipo", "codigo"),)


class EventoDB(Base):
    __tablename__ = "eventos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tipo: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    usuario_id: Mapped[uuid.UUID] = mapped_column()
    ocorrido_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(default=lambda: TENANT_ID)


class Auditoria(Base):
    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(50))
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    ip_origem: Mapped[str | None] = mapped_column(String(45), default=None)
    dados: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(default=lambda: TENANT_ID)


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(255))
    # CPF nunca armazenado em claro — só o índice cego (HMAC-SHA256)
    cpf_idx: Mapped[str] = mapped_column(String(64), index=True)
    email: Mapped[str | None] = mapped_column(String(255), default=None)
    telefone: Mapped[str | None] = mapped_column(String(20), default=None)
    data_nascimento: Mapped[date | None] = mapped_column(Date, default=None)
    sexo: Mapped[str | None] = mapped_column(String(1), default=None)
    estado_civil: Mapped[str | None] = mapped_column(String(50), default=None)
    profissao: Mapped[str | None] = mapped_column(String(50), default=None)
    usuario_id: Mapped[uuid.UUID] = mapped_column()
    tenant_id: Mapped[uuid.UUID] = mapped_column(default=lambda: TENANT_ID)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class Veiculo(Base):
    __tablename__ = "veiculos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clientes.id"))
    fipe_codigo: Mapped[str | None] = mapped_column(String(20), default=None)
    marca: Mapped[str] = mapped_column(String(100))
    modelo: Mapped[str] = mapped_column(String(100))
    ano_fabricacao: Mapped[int] = mapped_column(Integer)
    ano_modelo: Mapped[int] = mapped_column(Integer)
    placa: Mapped[str | None] = mapped_column(String(10), default=None)
    chassi: Mapped[str | None] = mapped_column(String(17), default=None)
    combustivel: Mapped[str] = mapped_column(String(20))
    finalidade: Mapped[str] = mapped_column(String(50), default="lazer")
    cep_pernoite: Mapped[str] = mapped_column(String(8))
    tenant_id: Mapped[uuid.UUID] = mapped_column(default=lambda: TENANT_ID)


class Imovel(Base):
    __tablename__ = "imoveis"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clientes.id"))
    cep: Mapped[str] = mapped_column(String(8))
    logradouro: Mapped[str | None] = mapped_column(String(255), default=None)
    numero: Mapped[str | None] = mapped_column(String(20), default=None)
    tipo_imovel: Mapped[str] = mapped_column(String(50))
    tipo_construcao: Mapped[str] = mapped_column(String(50))
    tenant_id: Mapped[uuid.UUID] = mapped_column(default=lambda: TENANT_ID)


class Cotacao(Base):
    __tablename__ = "cotacoes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clientes.id"), default=None
    )
    ramo: Mapped[str] = mapped_column(String(20))
    # aguardando | processando | sucesso | restricao | erro
    status: Mapped[str] = mapped_column(String(20), default="aguardando")
    dados_risco: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    cotacao_id_cia: Mapped[str | None] = mapped_column(String(100), default=None)
    # Decimal nunca float
    premio_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None)
    restricoes: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    mensagens: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    necessita_vistoria: Mapped[bool] = mapped_column(Boolean, default=False)
    # Payload bruto — cifrado em produção (FASE 8/KMS); armazenado em claro até lá
    payload_original: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    versao_anterior_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cotacoes.id"), default=None
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column()
    tenant_id: Mapped[uuid.UUID] = mapped_column(default=lambda: TENANT_ID)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class Proposta(Base):
    """Registro imutável de cada transmissão de proposta.

    Append-only: nunca sofre UPDATE. Recotar + transmitir gera novo registro.
    Parcelas e comissão são projeções computadas sobre este registro.
    """

    __tablename__ = "propostas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cotacao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cotacoes.id"))
    protocolo: Mapped[str] = mapped_column(String(100))
    commissao_pct: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    plano_pagamento: Mapped[str] = mapped_column(String(20))
    n_parcelas: Mapped[int] = mapped_column(Integer)
    valor_parcela: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    comissao_parcela: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    inicio_vigencia: Mapped[date | None] = mapped_column(Date, default=None)
    transmitida_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column()
    tenant_id: Mapped[uuid.UUID] = mapped_column(default=lambda: TENANT_ID)


class CotacaoJob(Base):
    """Fila de trabalho para o orquestrador SKIP LOCKED."""

    __tablename__ = "cotacao_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cotacao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cotacoes.id"))
    cia: Mapped[str] = mapped_column(String(50))
    # pendente | processando | concluido | erro
    status: Mapped[str] = mapped_column(String(20), default="pendente")
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    processado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(default=lambda: TENANT_ID)
