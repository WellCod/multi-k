import asyncio
import random
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from app.adapters.base import (
    Capacidades,
    MovimentoCanonico,
    PropostaCanonica,
    Restricao,
    ResultadoCotacao,
    ResultadoTransmissao,
    RiscoCanonico,
)


class FakeSeguradora:
    """Adapter de desenvolvimento. Simula latência e os 3 estados de retorno.

    Estado determinado pelo CEP:
    - termina em 99 → erro
    - termina em 88 → restrição (vistoria obrigatória)
    - demais        → sucesso
    """

    def __init__(self, latencia_min: float = 8.0, latencia_max: float = 15.0) -> None:
        self._min = latencia_min
        self._max = latencia_max

    def capacidades(self) -> Capacidades:
        return Capacidades(
            ramos=["auto", "moto", "imovel"],
            coberturas=[
                "CASCO",
                "RCF",
                "APP",
                "VIDROS",
                "INCENDIO",
                "ROUBO",
                "RESP_CIVIL",
                "DANOS_ELET",
                "QUEBRA_VIDROS",
            ],
            franquias=["REDUZIDA", "NORMAL", "MAJORADA"],
            parcelamentos=["AVISTA", "2X", "3X", "6X", "10X"],
        )

    async def cotar(self, r: RiscoCanonico) -> ResultadoCotacao:
        await self._latencia()
        return self._resultado(r)

    async def recotar(self, id: str, r: RiscoCanonico) -> ResultadoCotacao:
        await self._latencia()
        return self._resultado(r)

    async def transmitir(self, p: PropostaCanonica) -> ResultadoTransmissao:
        await self._latencia()
        protocolo = f"FAKE-{uuid4().hex[:8].upper()}"
        return ResultadoTransmissao(sucesso=True, protocolo=protocolo)

    async def movimentos(self, desde: date) -> list[MovimentoCanonico]:
        return []

    async def _latencia(self) -> None:
        if self._max > 0:
            delay = random.uniform(self._min, self._max)  # noqa: S311
            await asyncio.sleep(delay)

    def _resultado(self, r: RiscoCanonico) -> ResultadoCotacao:
        cep_val = r.dados.get("cep_pernoite") or r.dados.get("cep") or "00000000"
        cep = str(cep_val)

        if cep.endswith("99"):
            return ResultadoCotacao(
                sucesso=False,
                cotacao_id=None,
                premio_total=None,
                mensagens=["Risco recusado (simulação de erro)."],
            )

        if cep.endswith("88"):
            return ResultadoCotacao(
                sucesso=True,
                cotacao_id=str(uuid4()),
                premio_total=Decimal("2850.00"),
                restricoes=[
                    Restricao(
                        codigo="R001",
                        mensagem="Vistoria prévia obrigatória (simulação).",
                    )
                ],
                necessita_vistoria=True,
                payload_resposta={
                    "cia": "fake",
                    "simulado_em": datetime.now(UTC).isoformat(),
                },
            )

        return ResultadoCotacao(
            sucesso=True,
            cotacao_id=str(uuid4()),
            premio_total=Decimal("1950.00"),
            payload_resposta={
                "cia": "fake",
                "simulado_em": datetime.now(UTC).isoformat(),
            },
        )
