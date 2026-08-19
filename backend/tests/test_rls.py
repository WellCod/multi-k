"""
RLS: corretor vê apenas seus próprios eventos; admin vê tudo.
Enforcement acontece no Postgres, não no controller.

Usa db_rls (SET LOCAL ROLE multik_app) para garantir que o role nao-superuser
esteja sujeito as politicas de Row Level Security.
"""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auth import Papel
from app.infra.models import EventoDB
from tests.conftest import criar_usuario


async def test_corretor_nao_ve_eventos_de_outro(db_rls: AsyncSession) -> None:
    a = await criar_usuario(db_rls, "corrA@rls.com", Papel.CORRETOR)
    b = await criar_usuario(db_rls, "corrB@rls.com", Papel.CORRETOR)
    await db_rls.flush()

    # Insere evento como A (RLS exige usuario_id = app.usuario_id para INSERT)
    await db_rls.execute(
        text("SELECT set_config('app.usuario_id', :uid, true)"), {"uid": str(a.id)}
    )
    await db_rls.execute(
        text("SELECT set_config('app.papel', :p, true)"), {"p": "corretor"}
    )
    db_rls.add(
        EventoDB(
            id=uuid.uuid4(),
            tipo="cotacao.criada",
            payload={"ramo": "auto"},
            usuario_id=a.id,
        )
    )
    await db_rls.flush()

    # Consulta como corretor B — nao deve ver eventos de A
    await db_rls.execute(
        text("SELECT set_config('app.usuario_id', :uid, true)"), {"uid": str(b.id)}
    )
    await db_rls.execute(
        text("SELECT set_config('app.papel', :p, true)"), {"p": "corretor"}
    )
    res = await db_rls.execute(select(EventoDB))
    assert len(res.scalars().all()) == 0, "Corretor B não deve ver eventos de A"


async def test_admin_ve_todos_os_eventos(db_rls: AsyncSession) -> None:
    adm = await criar_usuario(db_rls, "adm@rls.com", Papel.ADMIN)
    c = await criar_usuario(db_rls, "corrC@rls.com", Papel.CORRETOR)
    await db_rls.flush()

    # Admin pode inserir eventos de qualquer usuario
    await db_rls.execute(
        text("SELECT set_config('app.usuario_id', :uid, true)"),
        {"uid": str(adm.id)},
    )
    await db_rls.execute(
        text("SELECT set_config('app.papel', :p, true)"), {"p": "admin"}
    )
    for i in range(3):
        db_rls.add(
            EventoDB(
                id=uuid.uuid4(),
                tipo=f"tipo.{i}",
                payload={},
                usuario_id=c.id,
            )
        )
    await db_rls.flush()

    res = await db_rls.execute(select(EventoDB))
    assert len(res.scalars().all()) >= 3, "Admin deve ver todos os eventos"


async def test_corretor_ve_proprio_evento(db_rls: AsyncSession) -> None:
    d = await criar_usuario(db_rls, "corrD@rls.com", Papel.CORRETOR)
    await db_rls.flush()

    await db_rls.execute(
        text("SELECT set_config('app.usuario_id', :uid, true)"), {"uid": str(d.id)}
    )
    await db_rls.execute(
        text("SELECT set_config('app.papel', :p, true)"), {"p": "corretor"}
    )
    db_rls.add(
        EventoDB(
            id=uuid.uuid4(),
            tipo="cotacao.criada",
            payload={},
            usuario_id=d.id,
        )
    )
    await db_rls.flush()

    res = await db_rls.execute(
        select(EventoDB).where(EventoDB.usuario_id == d.id)
    )
    assert len(res.scalars().all()) == 1


async def test_auditoria_append_only(db_rls: AsyncSession) -> None:
    from app.infra import audit

    await audit.registrar(db_rls, "login", {}, usuario_id=None)
    await db_rls.flush()

    from sqlalchemy import update

    from app.infra.models import Auditoria

    with pytest.raises(Exception, match="append-only"):
        await db_rls.execute(update(Auditoria).values(tipo="alterado"))
        await db_rls.flush()
