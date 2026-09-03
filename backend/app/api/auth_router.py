import hashlib
import hmac as _hmac
import secrets
import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.infra import audit
from app.infra.auth_service import (
    checar_rate_limit,
    criar_sessao,
    invalidar_sessao,
    prorrogar_sessao,
    registrar_falha,
    resetar_tentativas,
    verificar_senha,
)
from app.infra.db import get_db
from app.infra.models import Usuario
from app.infra.secrets import get_optional_secret

_debug = get_optional_secret("DEBUG", "false").lower() in ("true", "1", "yes")
_SECURE_COOKIE = not _debug

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE = "sid"
_CSRF_COOKIE = "csrf_token"
_MAX_AGE = 8 * 3600


class LoginInput(BaseModel):
    email: str
    senha: str


class LoginOutput(BaseModel):
    nome: str
    papel: str


@router.post("/login", response_model=LoginOutput)
async def login(
    body: LoginInput,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginOutput:
    ip = request.client.host if request.client else None

    await checar_rate_limit(db, body.email)
    if ip:
        await checar_rate_limit(db, ip)

    res = await db.execute(
        select(Usuario)
        .where(Usuario.email == body.email)
        .where(Usuario.ativo.is_(True))
    )
    usuario = res.scalar_one_or_none()

    if usuario is None or not verificar_senha(usuario.senha_hash, body.senha):
        await registrar_falha(db, body.email)
        if ip:
            await registrar_falha(db, ip)
        _audit_key = get_optional_secret("SECRET_KEY", "dev").encode()
        email_hash = _hmac.new(
            _audit_key, body.email.encode(), hashlib.sha256
        ).hexdigest()
        await audit.registrar(
            db,
            tipo="falha_login",
            dados={"email_hash": email_hash},
            ip_origem=ip,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
        )

    await resetar_tentativas(db, body.email)
    sessao_id = await criar_sessao(db, usuario.id, ip)
    await audit.registrar(
        db,
        tipo="login",
        dados={},
        usuario_id=usuario.id,
        ip_origem=ip,
    )
    await db.commit()

    response.set_cookie(
        key=_COOKIE,
        value=str(sessao_id),
        httponly=True,
        samesite="strict",
        secure=_SECURE_COOKIE,
        max_age=_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        key=_CSRF_COOKIE,
        value=secrets.token_hex(32),
        httponly=False,  # JS precisa ler para enviar como header
        samesite="strict",
        secure=_SECURE_COOKIE,
        max_age=_MAX_AGE,
        path="/",
    )
    return LoginOutput(nome=usuario.nome, papel=usuario.papel)


@router.post("/logout", status_code=200)
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    sid = request.cookies.get(_COOKIE)
    if sid:
        try:
            await invalidar_sessao(db, UUID(sid))
            await db.commit()
        except ValueError:
            pass
    response.delete_cookie(_COOKIE)
    response.delete_cookie(_CSRF_COOKIE)
    return {}


class MeOutput(BaseModel):
    id: uuid.UUID
    nome: str
    papel: str
    email: str


@router.get("/me", response_model=MeOutput)
async def me(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MeOutput:
    """Retorna dados do usuário autenticado."""
    return MeOutput(
        id=usuario.id,
        nome=usuario.nome,
        papel=usuario.papel,
        email=usuario.email,
    )


@router.post("/refresh", status_code=200)
async def refresh(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Prorroga a sessão ativa por mais 8h."""
    ip = request.client.host if request.client else None
    if ip:
        await checar_rate_limit(db, f"refresh:{ip}")
    sid = request.cookies.get(_COOKIE)
    if not sid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado.",
        )
    try:
        sessao_id = uuid.UUID(sid)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado.",
        ) from exc

    ok = await prorrogar_sessao(db, sessao_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão expirada.",
        )
    await db.commit()

    response.set_cookie(
        key=_COOKIE,
        value=str(sessao_id),
        httponly=True,
        samesite="strict",
        secure=_SECURE_COOKIE,
        max_age=_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        key=_CSRF_COOKIE,
        value=secrets.token_hex(32),
        httponly=False,
        samesite="strict",
        secure=_SECURE_COOKIE,
        max_age=_MAX_AGE,
        path="/",
    )
    return {}
