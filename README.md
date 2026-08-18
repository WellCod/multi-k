<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/TypeScript-5.5-3178C6?style=flat&logo=typescript&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/CI-GitHub_Actions-2088FF?style=flat&logo=github-actions&logoColor=white" />
</p>

<h1 align="center">multi-K</h1>
<p align="center">Multicálculo de seguros Auto e Residência com gestão de carteira, conciliação de comissão e auditoria.</p>

---

## O que é

Sistema para corretores de seguros cotarem, compararem e gerirem apólices junto a seguradoras. Integração via protocolo canônico — adicionar uma nova seguradora é uma nova classe, sem tocar no domínio.

**Funcionalidades:**
- Multicálculo com fan-out assíncrono sobre N seguradoras
- Funil de cotação em 5 passos (Auto e Residência)
- Gestão de carteira: apólices, parcelas, renovações
- Conciliação de comissão (prevista × recebida)
- Auditoria append-only e RBAC (corretor/admin)
- Dashboard com KPIs operacionais

---

## Arquitetura

```
React SPA (Vite + TypeScript)
      │  cookie de sessão (httponly · secure · samesite=strict)
      ▼
FastAPI (Python 3.12)     ← authN/authZ · auditoria · rate limit
      │                              │
      │                        PostgreSQL 16
      │                       (RLS por papel)
      ├── Domínio (eventos imutáveis)
      └── Orquestrador de cotação
                │
          PortaSeguradora  ◄── interface canônica (Protocol)
                │
      ┌─────────┼──────────────┐
    Fake      Yelum (fase 5)  Porto (fase futura)
                │
    integracao-tst.grupohdiseguros.com.br
```

**Decisões de design documentadas em [`docs/adr.md`](docs/adr.md)** — 32 ADRs cobrindo produto, domínio, stack, segurança e processo.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 |
| Banco | PostgreSQL 16 · RLS · eventos imutáveis |
| Frontend | React 18 · Vite · TypeScript · Tailwind CSS · shadcn/ui |
| Auth | Argon2id · cookie httponly · sessão própria sem SSO |
| Segredos | `SecretProvider` (interface) → `EnvSecretProvider` → GCP Secret Manager |
| CI/CD | GitHub Actions · gitleaks · ruff · mypy strict · pytest |
| Infra local | Docker Compose |

---

## Começando

```bash
# 1. Clone e configure
git clone https://github.com/WellCod/multi-k.git
cd multi-k
cp .env.example .env        # preencha SECRET_KEY

# 2. Instale dependências
make install                # pip install -e ".[dev]"
make install-frontend       # npm install

# 3. Suba o ambiente
make up                     # docker compose (postgres + adminer + api)

# 4. Verifique
curl http://localhost:8000/health   # → {"status": "ok", "version": "0.1.0"}

# 5. Frontend (dev)
cd frontend && npm run dev   # http://localhost:5173

# 6. Quality gates
make check                  # lint + tipos + testes + arquitetura
```

---

## Quality Gates

```bash
make lint        # ruff check + format
make typecheck   # mypy strict
make test        # pytest
make test-arch   # garante que código Yelum não vaza fora de adapters/yelum/
```

O CI roda automaticamente em push e pull request. `gitleaks` bloqueia merge se encontrar segredo no código.

---

## Segurança

- **Secrets via interface** — `SecretProvider` abstrai o acesso a segredos; nenhum módulo chama `os.environ` diretamente
- **Log com allowlist** — structlog emite apenas campos explicitamente permitidos; zero PII em log
- **Eventos imutáveis** — apólices e parcelas são projeções; sem UPDATE nem DELETE
- **RLS no Postgres** — isolamento de carteira garantido na camada de dados, não no controller
- **Gitleaks no CI** — scan de segredos em todo pull request
- **`.gitignore` auditado** — cobre `.env`, PDFs, coleções Postman, chaves, exports

---

## Fases

| # | Fase | Status |
|---|---|---|
| 0 | Setup local | ✅ |
| 1 | Fundação + adapter fake | 🔜 |
| 2 | Cotação end-to-end | — |
| 3 | Comparativo, PDF, gestão | — |
| 4 | Dashboard, relatórios, seed | — |
| 5 | Adapter Yelum real | — |
| 6 | Paridade ≥99% em 200 cotações | — |
| 7 | E-Retorno | — |
| 8 | Deploy GCP + endurecimento | — |
| 9 | MCP | — |

---

## Estrutura

```
backend/
  app/
    domain/        # modelos canônicos, eventos — agnósticos de seguradora
    adapters/
      base.py      # PortaSeguradora (Protocol) + tipos canônicos
      fake/        # adapter de desenvolvimento com latência simulada
      yelum/       # (fase 5) único lugar onde código Yelum é permitido
    api/           # rotas FastAPI
    infra/         # secrets, logging, auditoria, db
  tests/
    test_arch.py   # garante isolamento arquitetural — nunca delete
frontend/
  src/
    components/    # componentes reutilizáveis
    pages/         # páginas da SPA
    lib/           # utilitários
    hooks/         # React hooks
docs/
  adr.md           # 32 Architecture Decision Records
  escopo.md        # escopo e requisitos
  prompts.md       # guia de desenvolvimento por fase
```

---

## Licença

MIT
