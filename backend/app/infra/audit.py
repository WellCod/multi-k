import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auth import TENANT_ID
from app.infra.models import Auditoria


async def registrar(
    db: AsyncSession,
    tipo: str,
    dados: dict[str, Any],
    usuario_id: uuid.UUID | None = None,
    ip_origem: str | None = None,
) -> None:
    entrada = Auditoria(
        tipo=tipo,
        usuario_id=usuario_id,
        ip_origem=ip_origem,
        dados=dados,
        criado_em=datetime.now(UTC),
        tenant_id=TENANT_ID,
    )
    db.add(entrada)
    await db.flush()
