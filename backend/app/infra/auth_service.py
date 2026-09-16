import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.models import Sessao, TentativaLogin, Usuario
from app.infra.secrets import get_optional_secret

_log = logging.getLogger(__name__)

# warn  → loga discrepância (padrão)
# strict → rejeita sessão se IP mudou
# off    → ignora verificação de IP
_IP_CHECK_MODE = get_optional_secret("IP_CHECK_MODE", "warn").lower()

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
        select(Sessao)
        .where(Sessao.id == sessao_id, Sessao.expira_em > agora)
        .where(Sessao.criada_em > agora - SESSION_DURATION)
    )
    sessao = res.scalar_one_or_none()
    if sessao is None:
        return None
    if current_ip and sessao.ip_origem and sessao.ip_origem != current_ip:
        if _IP_CHECK_MODE == "strict":
            _log.warning("session_ip_mismatch_rejected")
            return None
        if _IP_CHECK_MODE != "off":
            _log.warning("session_ip_mismatch")
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


async def invalidar_sessoes_usuario(db: AsyncSession, usuario_id: UUID) -> None:
    """Revoga credenciais existentes na mesma transação da mudança de acesso."""
    await db.execute(
        update(Sessao)
        .where(Sessao.usuario_id == usuario_id)
        .values(expira_em=datetime.now(UTC))
    )


async def prorrogar_sessao(
    db: AsyncSession, sessao_id: UUID, current_ip: str | None = None
) -> bool:
    """Renova somente sessões válidas, sem ultrapassar oito horas desde o login."""
    if await buscar_sessao_valida(db, sessao_id, current_ip) is None:
        return False
    agora = datetime.now(UTC)
    res = await db.execute(
        select(Sessao)
        .where(Sessao.id == sessao_id, Sessao.expira_em > agora)
        .with_for_update()
    )
    sessao = res.scalar_one_or_none()
    if sessao is None:
        return False
    sessao.expira_em = min(
        agora + SESSION_DURATION, sessao.criada_em + SESSION_DURATION
    )
    await db.flush()
    return True


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
