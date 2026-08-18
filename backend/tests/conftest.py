"""
Configura o banco de testes antes de qualquer import do app.
DATABASE_URL deve apontar para um Postgres de teste disponível.
"""

import os

# Define antes de qualquer import do app para que db.py use este URL.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://multik:multik_test@localhost:5432/multik_test",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-only")

import uuid  # noqa: E402
from collections.abc import AsyncGenerator  # noqa: E402

import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.domain.auth import TENANT_ID, Papel  # noqa: E402
from app.infra.auth_service import hash_senha  # noqa: E402
from app.infra.models import Base, Usuario  # noqa: E402

_TEST_URL = os.environ["DATABASE_URL"]

_RLS_SQL = """
ALTER TABLE eventos ENABLE ROW LEVEL SECURITY;
ALTER TABLE eventos FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'eventos' AND policyname = 'eventos_isolamento'
    ) THEN
        CREATE POLICY eventos_isolamento ON eventos
        USING (
            current_setting('app.papel', true) = 'admin'
            OR usuario_id::text = current_setting('app.usuario_id', true)
        );
    END IF;
END $$;
CREATE OR REPLACE FUNCTION enforce_audit_append_only()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'auditoria é append-only: % proibido', TG_OP;
END;
$$;
DROP TRIGGER IF EXISTS tg_auditoria_no_update ON auditoria;
CREATE TRIGGER tg_auditoria_no_update
    BEFORE UPDATE ON auditoria
    FOR EACH ROW EXECUTE FUNCTION enforce_audit_append_only();
DROP TRIGGER IF EXISTS tg_auditoria_no_delete ON auditoria;
CREATE TRIGGER tg_auditoria_no_delete
    BEFORE DELETE ON auditoria
    FOR EACH ROW EXECUTE FUNCTION enforce_audit_append_only();
"""


@pytest_asyncio.fixture(scope="module")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    e = create_async_engine(_TEST_URL)
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        for stmt in _RLS_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await conn.execute(text(stmt))
    yield e
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await e.dispose()


@pytest_asyncio.fixture
async def db(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        await session.begin()
        yield session
        await session.rollback()


async def criar_usuario(
    db: AsyncSession,
    email: str,
    papel: Papel,
    senha: str = "Senha@123",
) -> Usuario:
    u = Usuario(
        id=uuid.uuid4(),
        email=email,
        nome=email.split("@")[0],
        senha_hash=hash_senha(senha),
        papel=papel.value,
        tenant_id=TENANT_ID,
    )
    db.add(u)
    await db.flush()
    return u
