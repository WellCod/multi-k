"""Geração de CPF válido pelo algoritmo (dígitos verificadores corretos).

O CPF gerado passa na validação matemática mas não existe na base da Receita.
Uso exclusivo em seeds e testes — nunca em produção.
"""

import secrets


def _digito(parcial: list[int], peso_inicio: int) -> int:
    """Calcula um dígito verificador pelo algoritmo do CPF."""
    soma = sum(d * p for d, p in zip(parcial, range(peso_inicio, 1, -1), strict=False))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def gerar_cpf() -> str:
    """Retorna CPF válido (11 dígitos sem pontuação) gerado aleatoriamente."""
    base = [secrets.randbelow(10) for _ in range(9)]
    d1 = _digito(base, 10)
    d2 = _digito(base + [d1], 11)
    digits = base + [d1, d2]
    return "".join(str(d) for d in digits)
