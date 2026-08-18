"""
Teste de arquitetura — garante isolamento do adapter Yelum.

Regra: nenhum símbolo específico da Yelum pode aparecer fora de
`backend/app/adapters/yelum/`. Se esse teste falhar, a camada anticorrupção
está furada — é bug de arquitetura, não de funcionalidade.

Rodar: pytest tests/test_arch.py
"""

import ast
import subprocess
from pathlib import Path

FORBIDDEN_PATTERNS = [
    "yelum",
    "BrokerProposalNumber",
    "CoverageCode",
    "CommercialProductCode",
    "BrokerCode",
    "BrokerBranchCode",
]

SCAN_DIRS = ["app/domain", "app/api", "app/infra"]
SCAN_FILES = ["app/main.py"]

MONEY_NAMES = {
    "premio",
    "valor",
    "comissao",
    "parcela",
    "desconto",
    "iof",
    "price",
    "amount",
}


def test_yelum_symbols_isolated() -> None:
    """Nenhum símbolo Yelum deve aparecer fora de adapters/yelum/."""
    root = Path(__file__).parent.parent

    dir_targets = [str(root / d) for d in SCAN_DIRS]
    file_targets = [str(root / f) for f in SCAN_FILES]
    targets = dir_targets + file_targets

    violations: list[str] = []
    for pattern in FORBIDDEN_PATTERNS:
        result = subprocess.run(
            ["grep", "-ri", "--include=*.py", pattern, *targets],
            capture_output=True,
            text=True,
        )
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
        ["grep", "-rn", "--include=*.py", r"os\.environ", str(root / "app")],
        capture_output=True,
        text=True,
    )

    allowed = str(root / "app" / "infra" / "secrets.py")
    violations = [
        line for line in result.stdout.strip().splitlines() if allowed not in line
    ]

    assert not violations, (
        "Uso direto de os.environ encontrado (use get_secret()):\n"
        + "\n".join(violations)
    )


def test_float_not_used_for_money() -> None:
    """float em campos monetários quebra paridade exata (use Decimal)."""
    root = Path(__file__).parent.parent
    violations: list[str] = []

    for py_file in (root / "app").rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign):
                ann = node.annotation
                target = node.target
                if (
                    isinstance(ann, ast.Name)
                    and ann.id == "float"
                    and isinstance(target, ast.Name)
                    and target.id in MONEY_NAMES
                ):
                    violations.append(
                        f"{py_file}:{node.lineno} float em campo monetário"
                    )

            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if not (isinstance(t, ast.Name) and t.id in MONEY_NAMES):
                        continue
                    val = node.value
                    if isinstance(val, ast.Constant) and isinstance(val.value, float):
                        violations.append(
                            f"{py_file}:{node.lineno} float literal em campo monetário"
                        )

    assert not violations, (
        "float detectado em campo monetário (use Decimal):\n" + "\n".join(violations)
    )
