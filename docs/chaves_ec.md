# Registro de Chaves EC por CIA

Arquivo de controle para os pares de chaves EC usados na autenticação com seguradoras.

> **As chaves privadas ficam em `secrets/<cia>/private-key.pem`** (no `.gitignore`).
> Este arquivo registra apenas metadados: CIA, data de criação, fingerprint e status.
> Para revogar uma chave: contate a CIA e peça a remoção; depois apague `secrets/<cia>/`
> e gere um novo par com `bash scripts/gerar_chaves_ec.sh <cia>`.

---

## Como usar

```bash
# Gerar nova chave para uma CIA
bash scripts/gerar_chaves_ec.sh justos

# O script imprime a linha para colar nesta tabela
```

---

## Chaves registradas

| CIA | Criada em | Fingerprint SHA-256 | Status | Env variável |
|---|---|---|---|---|
| justos | 2026-09-01 | `0757636d3aa93164ead0735dd83d1438a616caf3424dd280a0f47723ca8d7d6e` | ativa — aguarda registro Justos | `JUSTOS_PRIVATE_KEY` |

---

## Onde cada arquivo vive

```
secrets/
  justos/
    private-key.pem   ← nunca commitar (está no .gitignore)
    public-key.pem    ← anexar ao e-mail de onboarding
  porto/              ← quando vier
    private-key.pem
    public-key.pem
```

## Rotação de chave

1. Gerar novo par: `bash scripts/gerar_chaves_ec.sh <cia>`  
2. Enviar nova `public-key.pem` para a CIA e pedir substituição  
3. Atualizar status da linha antiga para `revogada` e adicionar nova linha  
4. Atualizar `JUSTOS_PRIVATE_KEY` (ou equivalente) no Secret Manager  
5. Apagar `secrets/<cia>/` anterior depois da CIA confirmar a troca  
