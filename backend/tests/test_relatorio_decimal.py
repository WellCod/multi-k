from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api.relatorio_router import ComissaoRamoOut, resumo_comissoes


async def test_resumo_preserva_centavos_e_totais_vazios():
    itens = [
        ComissaoRamoOut(ramo="auto", n_propostas=1,
                        premio_total=Decimal("900719925474099.91"),
                        comissao_total=Decimal("0.10")),
        ComissaoRamoOut(ramo="moto", n_propostas=1,
                        premio_total=Decimal("0.09"),
                        comissao_total=Decimal("0.20")),
    ]
    usuario = SimpleNamespace(id="test", papel="corretor")
    with patch("app.api.relatorio_router.relatorio_comissoes", new_callable=AsyncMock) as dados:
        dados.return_value = itens
        result = await resumo_comissoes(usuario, None, 30, None, None)
        assert result.premio_total == Decimal("900719925474100.00")
        assert result.comissao_total == Decimal("0.30")
        assert result.model_dump(mode="json")["comissao_total"] == "0.30"
        dados.return_value = []
        result = await resumo_comissoes(usuario, None, 30, None, None)
        assert result.premio_total == Decimal("0.00")
        assert result.comissao_total == Decimal("0.00")
