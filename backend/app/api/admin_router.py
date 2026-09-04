"""Rotas de gestão de usuários — visível apenas para admins."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, CurrentUser
from app.infra import audit
from app.infra.auth_service import hash_senha
from app.infra.db import get_db
from app.infra.models import ComissaoConfig, Usuario

router = APIRouter(prefix="/admin", tags=["admin"])

Db = Annotated[AsyncSession, Depends(get_db)]


class UsuarioAdminOut(BaseModel):
    id: uuid.UUID
    email: str
    nome: str
    papel: str
    ativo: bool
    criado_em: datetime

    model_config = {"from_attributes": True}


class UsuarioCriar(BaseModel):
    email: EmailStr
    nome: str
    papel: Literal["corretor", "admin"]
    senha: str

    @field_validator("nome")
    @classmethod
    def nome_min(cls, v: str) -> str:
        if len(v.strip()) < 2:
            raise ValueError("nome deve ter ao menos 2 caracteres")
        return v.strip()

    @field_validator("senha")
    @classmethod
    def senha_min(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("senha deve ter ao menos 8 caracteres")
        return v


class UsuarioAtualizar(BaseModel):
    nome: str | None = None
    papel: Literal["corretor", "admin"] | None = None
    ativo: bool | None = None

    @field_validator("nome")
    @classmethod
    def nome_min(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) < 2:
            raise ValueError("nome deve ter ao menos 2 caracteres")
        return v.strip() if v is not None else v


class ResetSenhaInput(BaseModel):
    nova_senha: str

    @field_validator("nova_senha")
    @classmethod
    def senha_min(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("nova_senha deve ter ao menos 8 caracteres")
        return v


@router.get("/usuarios", response_model=list[UsuarioAdminOut])
async def listar_usuarios(
    _usuario: AdminUser,
    db: Db,
    page: int = 1,
    page_size: int = 50,
) -> list[UsuarioAdminOut]:
    offset = (max(page, 1) - 1) * min(page_size, 200)
    result = await db.execute(
        select(Usuario)
        .order_by(Usuario.criado_em.desc())
        .offset(offset)
        .limit(min(page_size, 200))
    )
    return [UsuarioAdminOut.model_validate(u) for u in result.scalars().all()]


@router.post(
    "/usuarios",
    response_model=UsuarioAdminOut,
    status_code=status.HTTP_201_CREATED,
)
async def criar_usuario(
    _usuario: AdminUser,
    db: Db,
    body: UsuarioCriar,
) -> UsuarioAdminOut:
    existing = await db.execute(select(Usuario).where(Usuario.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-mail já cadastrado.",
        )
    novo = Usuario(
        email=body.email,
        nome=body.nome,
        senha_hash=hash_senha(body.senha),
        papel=body.papel,
    )
    db.add(novo)
    await db.flush()
    await db.refresh(novo)
    await audit.registrar(
        db,
        tipo="admin_criar_usuario",
        dados={"email": body.email, "papel": body.papel},
        usuario_id=_usuario.id,
    )
    await db.commit()
    return UsuarioAdminOut.model_validate(novo)


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioAdminOut)
async def atualizar_usuario(
    usuario_id: uuid.UUID,
    _usuario: AdminUser,
    db: Db,
    body: UsuarioAtualizar,
) -> UsuarioAdminOut:
    if body.ativo is False and usuario_id == _usuario.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode desativar sua própria conta.",
        )
    result = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    alvo = result.scalar_one_or_none()
    if alvo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )
    mudancas: dict[str, object] = {}
    if body.nome is not None:
        mudancas["nome"] = body.nome
        alvo.nome = body.nome
    if body.papel is not None:
        mudancas["papel"] = body.papel
        alvo.papel = body.papel
    if body.ativo is not None:
        mudancas["ativo"] = body.ativo
        alvo.ativo = body.ativo
    await audit.registrar(
        db,
        tipo="admin_atualizar_usuario",
        dados={"usuario_id": str(usuario_id), **mudancas},
        usuario_id=_usuario.id,
    )
    await db.commit()
    await db.refresh(alvo)
    return UsuarioAdminOut.model_validate(alvo)


@router.post(
    "/usuarios/{usuario_id}/reset-senha",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reset_senha(
    usuario_id: uuid.UUID,
    _usuario: AdminUser,
    db: Db,
    body: ResetSenhaInput,
) -> None:
    result = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    alvo = result.scalar_one_or_none()
    if alvo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )
    alvo.senha_hash = hash_senha(body.nova_senha)
    await audit.registrar(
        db,
        tipo="admin_reset_senha",
        dados={"usuario_id": str(usuario_id)},
        usuario_id=_usuario.id,
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Gestão de Comissão por CIA
# ---------------------------------------------------------------------------


class ComissaoConfigOut(BaseModel):
    cia: str
    ramo: str
    pct_padrao: Decimal
    atualizado_em: datetime

    model_config = {"from_attributes": True}


class ComissaoConfigIn(BaseModel):
    pct_padrao: Decimal

    @field_validator("pct_padrao")
    @classmethod
    def validar_pct(cls, v: Decimal) -> Decimal:
        if not (Decimal("0.0001") <= v <= Decimal("0.3000")):
            raise ValueError("pct_padrao deve ser entre 0.01% e 30%")
        return v


@router.get("/comissoes", response_model=list[ComissaoConfigOut])
async def listar_comissoes(
    _usuario: AdminUser,
    db: Db,
) -> list[ComissaoConfigOut]:
    result = await db.execute(
        select(ComissaoConfig).order_by(ComissaoConfig.cia, ComissaoConfig.ramo)
    )
    return [ComissaoConfigOut.model_validate(c) for c in result.scalars().all()]


@router.get("/comissoes/{cia}/{ramo}", response_model=ComissaoConfigOut)
async def get_comissao(
    cia: str,
    ramo: str,
    _usuario: CurrentUser,
    db: Db,
) -> ComissaoConfigOut:
    cfg = await db.get(ComissaoConfig, (cia, ramo))
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuração de comissão não encontrada.",
        )
    return ComissaoConfigOut.model_validate(cfg)


@router.put("/comissoes/{cia}/{ramo}", response_model=ComissaoConfigOut)
async def upsert_comissao(
    cia: str,
    ramo: str,
    _usuario: AdminUser,
    db: Db,
    body: ComissaoConfigIn,
) -> ComissaoConfigOut:
    existing = await db.get(ComissaoConfig, (cia, ramo))
    if existing is not None:
        existing.pct_padrao = body.pct_padrao
        existing.atualizado_em = datetime.now(UTC)
    else:
        existing = ComissaoConfig(
            cia=cia, ramo=ramo, pct_padrao=body.pct_padrao
        )
        db.add(existing)
    await db.commit()
    await db.refresh(existing)
    return ComissaoConfigOut.model_validate(existing)


@router.delete(
    "/comissoes/{cia}/{ramo}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_comissao(
    cia: str,
    ramo: str,
    _usuario: AdminUser,
    db: Db,
) -> None:
    cfg = await db.get(ComissaoConfig, (cia, ramo))
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuração de comissão não encontrada.",
        )
    await db.delete(cfg)
    await db.commit()
