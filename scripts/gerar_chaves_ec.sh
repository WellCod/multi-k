#!/usr/bin/env bash
# Gera par de chaves EC (prime256v1 / ES256) para autenticação com uma CIA.
#
# Uso:
#   bash scripts/gerar_chaves_ec.sh <cia>
#   bash scripts/gerar_chaves_ec.sh justos
#   bash scripts/gerar_chaves_ec.sh porto
#
# Saída em secrets/<cia>/:
#   private-key.pem  — NUNCA commitar, nunca compartilhar
#   public-key.pem   — ANEXAR ao e-mail de onboarding da CIA

set -euo pipefail

CIA="${1:-}"
if [[ -z "$CIA" ]]; then
  echo "Uso: bash scripts/gerar_chaves_ec.sh <cia>"
  echo "Exemplo: bash scripts/gerar_chaves_ec.sh justos"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTDIR="$ROOT/secrets/$CIA"
mkdir -p "$OUTDIR"

PRIV="$OUTDIR/private-key.pem"
PUB="$OUTDIR/public-key.pem"

if [[ -f "$PRIV" ]]; then
  echo "⚠️  $PRIV já existe."
  echo "   Delete manualmente se quiser regenerar (e avise a CIA para revogar a chave anterior)."
  exit 1
fi

openssl ecparam -name prime256v1 -genkey -noout -out "$PRIV"
openssl ec -in "$PRIV" -pubout -out "$PUB"

chmod 600 "$PRIV"
chmod 644 "$PUB"

# Fingerprint SHA-256 para o registro
FINGERPRINT=$(openssl ec -in "$PRIV" -pubout 2>/dev/null | openssl dgst -sha256 | awk '{print $2}')
CREATED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo ""
echo "✅ Chaves geradas em secrets/$CIA/"
echo "   private-key.pem  ← guardar em segredo"
echo "   public-key.pem   ← anexar ao e-mail de onboarding"
echo ""
echo "   Fingerprint SHA-256: $FINGERPRINT"
echo "   Gerado em:           $CREATED_AT"
echo ""
echo "Próximos passos:"
echo "  1. Copie o conteúdo de secrets/$CIA/public-key.pem e anexe ao e-mail"
echo "  2. Atualize docs/chaves_ec.md com os metadados abaixo:"
echo ""
echo "  | $CIA | $CREATED_AT | $FINGERPRINT | ativa |"
echo ""
echo "Conteúdo de public-key.pem:"
echo "---"
cat "$PUB"
