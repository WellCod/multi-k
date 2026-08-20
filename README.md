<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/TypeScript-5.5-3178C6?style=flat&logo=typescript&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/CI-GitHub_Actions-2088FF?style=flat&logo=github-actions&logoColor=white" />
  <img src="https://img.shields.io/badge/Fases_0--4-concluídas-22c55e?style=flat" />
</p>

<h1 align="center">multi-K</h1>
<p align="center">
  Plataforma de multicálculo de seguros para corretoras.<br/>
  Consulta N seguradoras em paralelo, compara e emite propostas — tudo em um único fluxo.
</p>

---

## O que é

Sistema desenvolvido do zero para uma corretora de seguros substituir planilhas e sistemas legados. O corretor preenche os dados do cliente uma vez e o sistema consulta todas as seguradoras cadastradas simultaneamente, retornando um comparativo com prêmio, coberturas, restrições e vistoria por seguradora.

**Principais funcionalidades entregues:**

| Módulo | O que faz |
|---|---|
| **Multicálculo async** | Fan-out para N seguradoras com fila em Postgres (SKIP LOCKED), timeout por CIA, resultado parcial exibido conforme chega |
| **Funil de cotação** | 5 passos (Auto e Residência), autosave por passo, recotar a partir de cotação anterior |
| **Comparativo inline** | Tabela com todas as seguradoras, prêmio, restrições, vistoria e botão "Transmitir" por resultado |
| **Gestão de carteira** | Clientes, apólices, parcelas, comissão prevista, renovações por janela D-30/D-45/D-60 |
| **Dashboard por papel** | Corretor: fila de trabalho. Admin: KPIs de produção, conversão e comissão |
| **Relatórios exportáveis** | Produção por corretor, funil de conversão, mix de carteira — export CSV e XLSX |
| **Timeline do cliente** | Cotação → proposta → apólice → parcela, tudo ordenado e imutável |
| **Auditoria append-only** | Toda ação relevante registrada; UPDATE e DELETE bloqueados por trigger no Postgres |

---

## Decisões de arquitetura relevantes

### Adapter Pattern com Protocol

Adicionar uma nova seguradora é implementar uma interface de 5 métodos. Nenhuma linha do domínio muda.

```python
class PortaSeguradora(Protocol):
    def capacidades(self) -> Capacidades: ...
    async def cotar(self, r: RiscoCanonico) -> ResultadoCotacao: ...
    async def recotar(self, id: str, r: RiscoCanonico) -> ResultadoCotacao: ...
    async def transmitir(self, p: PropostaCanonica) -> ResultadoTransmissao: ...
    async def movimentos(self, desde: date) -> list[MovimentoCanonico]: ...
```

O teste de arquitetura no CI garante que nenhum tipo ou campo específico de seguradora atravesse essa fronteira:

```bash
grep -ri "yelum|BrokerProposalNumber|CoverageCode" src/  # fora de adapters/yelum/ → CI falha
```

### Eventos imutáveis como fonte de verdade

Apólices e parcelas são **projeções** sobre um stream de eventos. Não existe `UPDATE` em entidade de negócio — toda alteração gera um novo evento. O E-Retorno da seguradora entrega movimentos, não estado.

### Fila em Postgres sem Redis

O orquestrador de cotação usa `SELECT ... FOR UPDATE SKIP LOCKED` direto no Postgres. Zero infraestrutura extra. A mesma tabela suporta N workers em paralelo sem duplicação de job.

### Log com allowlist, não denylist

`structlog` configurado para emitir **apenas campos explicitamente listados**. Campo novo não é logado por default. Teste automatizado falha se `cpf`, `password` ou `access_token` aparecerem em qualquer sink — a proteção de PII é verificada a cada commit.

### RLS no banco, não no controller

O isolamento de carteira entre corretores é garantido por Row Level Security no Postgres. O controller não precisa filtrar por `usuario_id` — se esquecer, o banco recusa. Testado com `test_rls.py`.

### SecretProvider como interface

```python
class SecretProvider(Protocol):
    def get(self, key: str) -> str: ...
```

`EnvSecretProvider` em desenvolvimento, GCP Secret Manager em produção. Nenhum módulo chama `os.environ` diretamente. A troca é uma linha no bootstrap.

---

## Stack

| Camada | Tecnologia | Por quê |
|---|---|---|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2.0 async | Tipagem forte, async nativo, ecossistema seguros |
| Banco | PostgreSQL 16 · RLS · triggers append-only | Isolamento de dados na camada certa |
| Migrations | Alembic + autogenerate | Schema versionado, rollback seguro |
| Validação | Pydantic v2 | Parse, não validação — falha cedo na fronteira |
| Frontend | React 18 · Vite · TypeScript · Tailwind · shadcn/ui | Ferramenta densa, não landing page |
| Formulários | react-hook-form + Zod | Autosave por passo, validação isomórfica |
| Auth | Argon2id · cookie httponly/secure/samesite=strict | Sem JWT no frontend, sem SSO, sem cadastro público |
| CI | GitHub Actions · gitleaks · ruff · mypy strict · pytest | Nada sobe sem passar em tudo |

---

## Rodando localmente

```bash
# 1. Clone e configure
git clone https://github.com/WellCod/multi-k.git
cd multi-k
cp .env.example .env          # preencha SECRET_KEY

# 2. Instale dependências
make install                  # pip install -e ".[dev]"
make install-frontend         # npm install

# 3. Suba o ambiente
make up                       # postgres + adminer + api (docker compose)

# 4. Verifique
curl http://localhost:8000/health   # → {"status": "ok", "version": "0.1.0"}

# 5. Frontend
cd frontend && npm run dev    # http://localhost:5173
```

**Credenciais de demonstração** (seed carregado automaticamente no startup):

| Papel | E-mail | Senha |
|---|---|---|
| Corretor | `ana.souza@demo.multik` | `Demo@2026` |
| Corretor | `carlos.mendes@demo.multik` | `Demo@2026` |
| Admin | `admin@demo.multik` | `Admin@2026` |

O seed cria ~40 clientes, ~120 cotações e ~60 propostas com dados sintéticos plausíveis (CPFs válidos pelo algoritmo, nomes brasileiros, região Campinas). Idempotente — pode rodar várias vezes.

---

## Quality Gates

```bash
make check        # roda tudo abaixo em sequência
make lint         # ruff check + format --check
make typecheck    # mypy strict — zero `Any` não declarado
make test         # pytest com cobertura
make test-arch    # garante isolamento do adapter Yelum
```

O CI executa automaticamente em todo push e pull request. `gitleaks` bloqueia merge se encontrar segredo no código. Nenhum `# noqa` ou `# type: ignore` sem justificativa documentada.

---

## Segurança

- **Argon2id** para senhas, sem PBKDF2 nem bcrypt
- **Rate limit** no login: 5 tentativas / 15 min por usuário e por IP; bloqueio progressivo
- **Cookie `httponly + secure + samesite=strict`** — sem token no localStorage, sem XSS leva sessão
- **RLS no Postgres** — corretor vê só a própria carteira; enforcement na camada de dados
- **Log com allowlist** — CPF, senha, tokens nunca aparecem em nenhum sink
- **Auditoria append-only** — trigger no Postgres impede UPDATE e DELETE na tabela de auditoria
- **SecretProvider** — nenhum `os.environ` direto em código de produção
- **gitleaks no CI** — scan de segredos em todo PR
- **Envelope encryption planejado** — CPF/chassi/placa com KMS antes da primeira cotação real

---

## Roadmap

| # | Fase | Status | Gate |
|---|---|---|---|
| 0 | Setup local | ✅ concluída | — |
| 1 | Fundação + adapter fake | ✅ concluída | — |
| 2 | Cotação end-to-end | ✅ concluída | — |
| 3 | Comparativo, PDF, gestão de carteira | ✅ concluída | — |
| 4 | Dashboard, relatórios, seed de demonstração | ✅ concluída | — |
| 5 | Adapter Yelum real (Auto + Residência) | ⏳ aguardando | Credencial de homologação |
| 6 | Paridade ≥ 99% em 200 cotações | ⏳ aguardando | Gate da Fase 5 |
| 7 | E-Retorno (comissão recebida, sinistro) | ⏳ aguardando | Security Assessment |
| 8 | Deploy GCP + endurecimento | ⏳ aguardando | Precede chave de produção |
| 9 | MCP / bot de cotação | ⏳ aguardando | Após paridade |

Fases 0–4 não dependem de nenhum terceiro. A barreira da Fase 5 é a credencial de homologação da seguradora, não código.

---

## Estrutura do projeto

```
backend/
  app/
    domain/        # modelos canônicos, eventos — agnósticos de seguradora
    adapters/
      base.py      # PortaSeguradora (Protocol) + tipos canônicos
      fake/        # adapter de desenvolvimento com latência simulada (8–15s)
      yelum/       # (fase 5) — único lugar onde código Yelum é permitido
    api/           # rotas FastAPI
    infra/         # secrets, logging, auditoria, db, worker
  tests/
    test_arch.py   # isolamento arquitetural — nunca remova
frontend/
  src/
    pages/         # CotacaoPage, ClientesPage, HistoricoPage, RelatoriosPage…
    components/    # Layout, DemoWatermark, ui/
    lib/           # api.ts (cliente HTTP), auth.ts, utils.ts
docs/
  adr.md           # Architecture Decision Records
  escopo.md        # escopo, requisitos e riscos
  prompts.md       # guia de desenvolvimento por fase
```

---

## ADRs selecionados

Decisões não óbvias documentadas em [`docs/adr.md`](docs/adr.md):

- Por que Postgres como fila (sem Redis/Celery)
- Por que evento imutável em vez de entidade mutável
- Por que RLS no banco e não no controller
- Por que allowlist de log e não denylist
- Por que SecretProvider como interface desde o dia 1
- Por que começar pela Yelum e não pela Porto

---

## Licença

MIT
