"""
RLS: corretor vê apenas seus próprios eventos; admin vê tudo.
Enforcement acontece no Postgres, não no controller.
"""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auth import Papel
from app.infra.models import EventoDB
from tests.conftest import criar_usuario


async def test_corretor_nao_ve_eventos_de_outro(
    db: AsyncSession,
) -> None:
    a = await criar_usuario(db, "corrA@rls.com", Papel.CORRETOR)
    b = await criar_usuario(db, "corrB@rls.com", Papel.CORRETOR)
    await db.flush()

    evento = EventoDB(
        id=uuid.uuid4(),
        tipo="cotacao.criada",
        payload={"ramo": "auto"},
        usuario_id=a.id,
    )
    db.add(evento)
    await db.flush()

    # Ativa RLS como corretor B
    await db.execute(
        text("SELECT set_config('app.usuario_id', :uid, true)"), {"uid": str(b.id)}
    )
    await db.execute(text("SELECT set_config('app.papel', :p, true)"), {"p": "corretor"})

    res = await db.execute(select(EventoDB))
    visivel = res.scalars().all()
    assert len(visivel) == 0, "Corretor B não deve ver eventos de A"


async def test_admin_ve_todos_os_eventos(db: AsyncSession) -> None:
    adm = await criar_usuario(db, "adm@rls.com", Papel.ADMIN)
    c = await criar_usuario(db, "corrC@rls.com", Papel.CORRETOR)
    await db.flush()

    for i in range(3):
        db.add(
            EventoDB(
                id=uuid.uuid4(),
                tipo=f"tipo.{i}",
                payload={},
                usuario_id=c.id,
            )
        )
    await db.flush()

    # Ativa RLS como admin
    await db.execute(
        text("SELECT set_config('app.usuario_id', :uid, true)"), {"uid": str(adm.id)}
    )
    await db.execute(text("SELECT set_config('app.papel', :p, true)"), {"p": "admin"})

    res = await db.execute(select(EventoDB))
    todos = res.scalars().all()
    assert len(todos) >= 3, "Admin deve ver todos os eventos"


async def test_corretor_ve_proprio_evento(db: AsyncSession) -> None:
    d = await criar_usuario(db, "corrD@rls.com", Papel.CORRETOR)
    await db.flush()

    db.add(
        EventoDB(
            id=uuid.uuid4(),
            tipo="cotacao.criada",
            payload={},
            usuario_id=d.id,
        )
    )
    await db.flush()

    await db.execute(
        text("SELECT set_config('app.usuario_id', :uid, true)"), {"uid": str(d.id)}
    )
    await db.execute(text("SELECT set_config('app.papel', :p, true)"), {"p": "corretor"})

    res = await db.execute(select(EventoDB).where(EventoDB.usuario_id == d.id))
    assert len(res.scalars().all()) == 1


async def test_auditoria_append_only(db: AsyncSession) -> None:
    from app.infra import audit

    await audit.registrar(db, "login", {}, usuario_id=None)
    await db.flush()

    from sqlalchemy import update

    from app.infra.models import Auditoria

    with pytest.raises(Exception, match="append-only"):
        await db.execute(update(Auditoria).values(tipo="alterado"))
        await db.flush()
