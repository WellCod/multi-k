import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.models import Sessao, TentativaLogin, Usuario

_log = logging.getLogger(__name__)

_ph = PasswordHasher()

SESSION_DURATION = timedelta(hours=8)
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = timedelta(minutes=15)


def hash_senha(senha: str) -> str:
    return _ph.hash(senha)


def verificar_senha(hash_: str, senha: str) -> bool:
    try:
        _ph.verify(hash_, senha)
        return True
    except VerifyMismatchError:
        return False


async def criar_sessao(db: AsyncSession, usuario_id: UUID, ip: str | None) -> UUID:
    sessao_id = uuid4()
    sessao = Sessao(
        id=sessao_id,
        usuario_id=usuario_id,
        expira_em=datetime.now(UTC) + SESSION_DURATION,
        ip_origem=ip,
    )
    db.add(sessao)
    await db.flush()
    return sessao_id


async def buscar_sessao_valida(
    db: AsyncSession, sessao_id: UUID, current_ip: str | None = None
) -> Usuario | None:
    agora = datetime.now(UTC)
    res = await db.execute(
        select(Sessao).where(Sessao.id == sessao_id).where(Sessao.expira_em > agora)
    )
    sessao = res.scalar_one_or_none()
    if sessao is None:
        return None
    if current_ip and sessao.ip_origem and sessao.ip_origem != current_ip:
        _log.warning(
            "session_ip_mismatch sessao=%s stored=%s current=%s",
            sessao_id,
            sessao.ip_origem,
            current_ip,
        )
    res2 = await db.execute(
        select(Usuario)
        .where(Usuario.id == sessao.usuario_id)
        .where(Usuario.ativo.is_(True))
    )
    return res2.scalar_one_or_none()


async def invalidar_sessao(db: AsyncSession, sessao_id: UUID) -> None:
    res = await db.execute(select(Sessao).where(Sessao.id == sessao_id))
    sessao = res.scalar_one_or_none()
    if sessao:
        sessao.expira_em = datetime.now(UTC)
        await db.flush()


async def checar_rate_limit(db: AsyncSession, identificador: str) -> None:
    agora = datetime.now(UTC)
    res = await db.execute(
        select(TentativaLogin).where(TentativaLogin.identificador == identificador)
    )
    tentativa = res.scalar_one_or_none()
    if (
        tentativa
        and tentativa.bloqueado_ate is not None
        and tentativa.bloqueado_ate > agora
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas. Tente novamente em 15 minutos.",
        )


async def registrar_falha(db: AsyncSession, identificador: str) -> None:
    agora = datetime.now(UTC)
    janela_inicio = agora - RATE_LIMIT_WINDOW
    res = await db.execute(
        select(TentativaLogin).where(TentativaLogin.identificador == identificador)
    )
    tentativa = res.scalar_one_or_none()
    if tentativa is None:
        db.add(
            TentativaLogin(
                identificador=identificador,
                contagem=1,
                ultima_tentativa=agora,
            )
        )
    else:
        if tentativa.ultima_tentativa < janela_inicio:
            tentativa.contagem = 1
        else:
            tentativa.contagem += 1
        tentativa.ultima_tentativa = agora
        if tentativa.contagem >= RATE_LIMIT_MAX:
            tentativa.bloqueado_ate = agora + RATE_LIMIT_WINDOW
    await db.flush()


async def resetar_tentativas(db: AsyncSession, identificador: str) -> None:
    res = await db.execute(
        select(TentativaLogin).where(TentativaLogin.identificador == identificador)
    )
    tentativa = res.scalar_one_or_none()
    if tentativa:
        tentativa.contagem = 0
        tentativa.bloqueado_ate = None
        await db.flush()
