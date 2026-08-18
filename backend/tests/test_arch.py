"""
Teste de arquitetura — garante isolamento do adapter Yelum.

Regra: nenhum símbolo específico da Yelum pode aparecer fora de
`backend/app/adapters/yelum/`. Se esse teste falhar, a camada anticorrupção
está furada — é bug de arquitetura, não de funcionalidade.

Rodar: pytest tests/test_arch.py
"""

import subprocess
import sys
from pathlib import Path

# Padrões que NUNCA devem aparecer fora de adapters/yelum/
FORBIDDEN_PATTERNS = [
    "yelum",
    "BrokerProposalNumber",
    "CoverageCode",
    "CommercialProductCode",
    "BrokerCode",
    "BrokerBranchCode",
]

# Diretórios onde a busca é feita (fora de adapters/yelum/)
SCAN_DIRS = [
    "app/domain",
    "app/api",
    "app/infra",
]

SCAN_FILES = ["app/main.py"]


def test_yelum_symbols_isolated() -> None:
    """Nenhum símbolo Yelum deve aparecer fora de adapters/yelum/."""
    root = Path(__file__).parent.parent

    violations: list[str] = []

    for pattern in FORBIDDEN_PATTERNS:
        targets = [str(root / d) for d in SCAN_DIRS] + [str(root / f) for f in SCAN_FILES]
        result = subprocess.run(
            ["grep", "-ri", "--include=*.py", pattern, *targets],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                violations.append(f"[{pattern}] {line}")

    assert not violations, (
        "Referências a Yelum encontradas fora de adapters/yelum/:\n"
        + "\n".join(violations)
        + "\n\nCorrija antes de fazer merge."
    )


def test_secret_provider_not_bypassed() -> None:
    """Nenhum módulo do app deve chamar os.environ diretamente."""
    root = Path(__file__).parent.parent

    result = subprocess.run(
        [
            "grep", "-rn", "--include=*.py",
            r"os\.environ",
            str(root / "app"),
        ],
        capture_output=True,
        text=True,
    )

    # Permitido apenas em infra/secrets.py
    allowed_file = str(root / "app" / "infra" / "secrets.py")
    violations = [
        line for line in result.stdout.strip().splitlines()
        if allowed_file not in line
    ]

    assert not violations, (
        "Uso direto de os.environ encontrado (use get_secret() em vez disso):\n"
        + "\n".join(violations)
    )


def test_float_not_used_for_money() -> None:
    """
    Detecta float sendo atribuído a campos com nomes de dinheiro.

    Heurística: variáveis como `premio`, `valor`, `comissao`, `parcela`,
    `desconto`, `iof` não podem receber literais float (ex: 1.5, 100.0).
    """
    root = Path(__file__).parent.parent

    # Grep por atribuições óbvias de float em nomes de campo monetário
    result = subprocess.run(
        [
            sys.executable, "-c",
            f"""
import ast, pathlib, sys

money_names = {{"premio", "valor", "comissao", "parcela", "desconto", "iof", "price", "amount"}}
violations = []

for f in pathlib.Path(r"{root}/app").rglob("*.py"):
    try:
        tree = ast.parse(f.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.annotation, ast.Name) and node.annotation.id == "float":
                if isinstance(node.target, ast.Name) and node.target.id in money_names:
                    violations.append(f"{{f}}:{{node.lineno}} float em campo monetário")
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in money_names:
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, float):
                        violations.append(f"{{f}}:{{node.lineno}} float literal em campo monetário")

if violations:
    print("\\n".join(violations))
    sys.exit(1)
""",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        "float detectado em campo monetário (use Decimal):\n" + result.stdout
    )
