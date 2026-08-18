import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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
