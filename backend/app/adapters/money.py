"""Conversão de valor monetário — compartilhada por todos os adapters.

Regra 2 do projeto: dinheiro é Decimal, nunca float. Ter um conversor por
adapter foi como a Yelum acabou inventando prêmio zero enquanto a Justos já
recusava resposta incompleta; mantém-se um só para as duas não divergirem.
"""

from decimal import Decimal, InvalidOperation


def to_decimal(raw: object) -> Decimal | None:
    """Valor monetário explícito. Ausência, lixo ou negativo não viram zero."""
    if raw is None or isinstance(raw, (bool, dict, list)):
        return None
    try:
        amount = Decimal(str(raw))
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount.quantize(Decimal("0.01"))
