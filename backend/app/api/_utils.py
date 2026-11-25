"""Helpers partilhados pelos routers da API."""

from fastapi import HTTPException, status
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_or_404[Entidade](
    stmt: Select[Entidade],
    db: AsyncSession,
    detail: str = "Não encontrado.",
) -> Entidade:
    """Executa stmt e retorna o único resultado ou levanta HTTPException 404.

    `Entidade` é o tipo selecionado, ex.: Cliente em select(Cliente). Desde o
    SQLAlchemy 2.1 o parâmetro de Select é a própria entidade
    (`Select[Cliente]`), não mais uma tupla (`Select[tuple[Cliente]]`); é isso
    que permite ao mypy devolver o tipo certo para quem chama.
    """
    result = await db.execute(stmt)
    entidade = result.scalar_one_or_none()
    if entidade is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return entidade
