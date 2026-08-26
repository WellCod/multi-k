from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.auth_service import buscar_sessao_valida
from app.infra.db import get_db
from app.infra.models import Usuario


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    sid: Annotated[str | None, Cookie()] = None,
) -> Usuario:
    if not sid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado.",
        )
    try:
        sessao_id = UUID(sid)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida.",
        ) from err
    ip = request.client.host if request.client else None
    usuario = await buscar_sessao_valida(db, sessao_id, ip)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão expirada ou inválida.",
        )
    await db.execute(
        text("SELECT set_config('app.usuario_id', :uid, true)"),
        {"uid": str(usuario.id)},
    )
    await db.execute(
        text("SELECT set_config('app.papel', :papel, true)"),
        {"papel": usuario.papel},
    )
    return usuario


async def require_admin(
    usuario: Annotated[Usuario, Depends(get_current_user)],
) -> Usuario:
    if usuario.papel != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return usuario


CurrentUser = Annotated[Usuario, Depends(get_current_user)]
AdminUser = Annotated[Usuario, Depends(require_admin)]
