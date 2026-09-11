"""Drafts never leave the authenticated account or enter browser storage."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.infra.db import get_db
from app.infra.models import RascunhoCotacao

router = APIRouter(prefix="/rascunhos/cotacao", tags=["rascunhos"])


class DraftInput(BaseModel):
    dados: dict[str, Any]
    versao: int = Field(ge=0)


@router.get("")
async def load(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    response: Response,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    draft = (
        await db.execute(
            select(RascunhoCotacao).where(RascunhoCotacao.usuario_id == usuario.id)
        )
    ).scalar_one_or_none()
    return {
        "dados": draft.dados if draft else None,
        "versao": draft.versao if draft else 0,
    }


@router.put("")
async def save(
    body: DraftInput, usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict[str, int]:
    stmt = insert(RascunhoCotacao).values(
        usuario_id=usuario.id,
        tenant_id=usuario.tenant_id,
        dados=body.dados,
        versao=1,
        atualizado_em=datetime.now(UTC),
    )
    returning_stmt = stmt.on_conflict_do_update(
        index_elements=[RascunhoCotacao.usuario_id],
        set_={
            "dados": body.dados,
            "versao": RascunhoCotacao.versao + 1,
            "atualizado_em": datetime.now(UTC),
        },
        where=RascunhoCotacao.versao == body.versao,
    ).returning(RascunhoCotacao.versao)
    version = (await db.execute(returning_stmt)).scalar_one_or_none()
    if version is None:
        raise HTTPException(
            409,
            "O rascunho foi alterado em outra sessão. "
            "Reabra a cotação antes de continuar.",
        )
    await db.commit()
    return {"versao": version}


@router.delete("", status_code=204)
async def clear(
    usuario: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    await db.execute(
        delete(RascunhoCotacao).where(RascunhoCotacao.usuario_id == usuario.id)
    )
    await db.commit()
