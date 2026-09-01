#!/usr/bin/env bash
# Gera par de chaves EC (prime256v1 / ES256) para autenticação Justos.
# Saída: private-key.pem (NUNCA commitar) e public-key.pem (anexar ao e-mail).

set -euo pipefail

OUTDIR="$(cd "$(dirname "$0")/.." && pwd)/secrets"
mkdir -p "$OUTDIR"

PRIV="$OUTDIR/private-key.pem"
PUB="$OUTDIR/public-key.pem"

if [[ -f "$PRIV" ]]; then
  echo "⚠️  $PRIV já existe — delete manualmente se quiser regenerar."
  exit 1
fi

openssl ecparam -name prime256v1 -genkey -noout -out "$PRIV"
openssl ec -in "$PRIV" -pubout -out "$PUB"

chmod 600 "$PRIV"
chmod 644 "$PUB"

echo ""
echo "✅ Chaves geradas em $OUTDIR/"
echo "   private-key.pem  ← guardar em segredo (adicione ao .env como JUSTOS_PRIVATE_KEY)"
echo "   public-key.pem   ← ANEXAR AO E-MAIL para a Justos"
echo ""
echo "Conteúdo de public-key.pem:"
echo "---"
cat "$PUB"
