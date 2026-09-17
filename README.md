<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/TypeScript-5.5-3178C6?style=flat&logo=typescript&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/CI-GitHub_Actions-2088FF?style=flat&logo=github-actions&logoColor=white" />
  <img src="https://img.shields.io/badge/Fase_5-em_andamento-f59e0b?style=flat" />
  <img src="https://img.shields.io/badge/Justos-staging-22c55e?style=flat" />
  <img src="https://img.shields.io/badge/cobertura-96%25-22c55e?style=flat" />
</p>

<h1 align="center">multi-K</h1>
<p align="center">
  Plataforma de multicálculo de seguros para corretoras.<br/>
  Consulta N seguradoras em paralelo, compara e transmite propostas — tudo em um único fluxo.
</p>

---

## O que é

Sistema desenvolvido do zero para uma corretora de seguros substituir planilhas e sistemas legados. O corretor preenche os dados do cliente uma vez e o sistema consulta todas as seguradoras cadastradas simultaneamente, retornando um comparativo com prêmio, coberturas, restrições e vistoria por seguradora.

**Principais funcionalidades entregues:**

| Módulo | O que faz |
|---|---|
| **Multicálculo async** | Fan-out para N seguradoras com fila em Postgres (SKIP LOCKED), timeout por CIA, resultado parcial exibido conforme chega |
| **Funil de cotação** | 5 passos (Auto e Moto), autosave por passo, recotar a partir de cotação anterior, finalidade Uber/Táxi |
| **Tabela FIPE integrada** | Seleção Marca → Modelo → Ano com busca inline, valor FIPE em tempo real, proxy com cache 30 dias no backend |
| **Integração Justos (auto)** | Autenticação ES256, cotação, pricing, configurador de coberturas, recotação em lote, proposta formal, link de contratação e PDF de cotação/proposta |
| **Configurador de coberturas** | Recálculo é prévia sem gravação; aplicar reconfirma o preço na seguradora e grava seleção, valores e auditoria em uma transação |
| **Transmissão controlada** | Tentativa registrada antes da chamada externa, chave de idempotência, revisão exibida comparada sob bloqueio e resultado indefinido bloqueando reenvio até conferência auditada |
| **Comparativo inline** | Tabela por CIA com prêmio mensal/anual, condições de pagamento confirmadas pela seguradora, coberturas comparáveis, restrições e vistoria; export em PDF |
| **Gestão de clientes** | Listagem com busca, criação via modal, edição inline, veículos e imóveis por cliente; segurado pessoa física ou jurídica |
| **Gestão de carteira** | Apólices, parcelas, comissão prevista, renovações por janela D-30/D-45/D-60 |
| **Rascunhos server-side** | Cotação em andamento cifrada, versionada e vinculada ao usuário |
| **Dashboard por papel** | Corretor: fila de trabalho. Admin: KPIs de produção, conversão e comissão |
| **Relatórios exportáveis** | Produção por corretor, funil de conversão, mix de carteira — export CSV e XLSX |
| **Timeline do cliente** | Cotação → proposta → apólice → parcela, tudo ordenado e imutável |
| **Auditoria append-only** | Toda ação registrada; UPDATE e DELETE bloqueados por trigger no Postgres |
| **Segurança endurecida** | CSRF double-submit, AES-256-GCM em repouso, sessão revogável, cookie httponly/secure/samesite=strict, CORS guard produção |

---

## Estado da integração com seguradoras

O produto atende **Auto e Moto**. O código não depende de nenhuma seguradora específica — o que muda por integração é o estágio:

| Seguradora | Ramo | Estado |
|---|---|---|
| **Justos** | Auto | Credenciais recebidas. Autenticação, cotação, pricing e seleção de coberturas exercitados em staging; o ciclo completo até a proposta formal ainda não fechou em ambiente da seguradora. Produção depende de novo par de chaves EC. |
| **Yelum** | Imóvel | Adapter pronto e isolado, **sem uso no produto por ora**: o ramo imóvel está fora de escopo e não é oferecido na interface. O código permanece, com as mesmas regras da Justos; reativar é devolver a opção no frontend. Depende também da credencial de homologação. |
| **Fake** | Todos | Simulador usado em desenvolvimento e nos testes. Nenhum teste da suíte faz chamada real. |

A aderência da integração Justos ao contrato publicado é acompanhada requisito a requisito em [`docs/auditoria-requisitos-justos.md`](docs/auditoria-requisitos-justos.md): cada linha aponta evidência no código, teste e lacuna.

A importação automática de apólices vendidas (E-Retorno) está **desenhada e não ligada** — o desenho, com cursor durável, idempotência e as perguntas pendentes ao contrato, está em [`docs/justos/plano-exportacao-incremental.md`](docs/justos/plano-exportacao-incremental.md).

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
grep -ri "yelum|BrokerProposalNumber|CoverageCode" app/domain app/api app/infra app/main.py   # → CI falha
```

### Capacidades opcionais em vez de interface inchada

Nem toda seguradora oferece tudo. O que é específico entra como Protocol opcional, verificado com `isinstance`, e adapters que não implementam seguem o fluxo antigo sem mudança:

```python
class PreparadorTransmissao(Protocol):   # condições de pagamento confirmadas
class CatalogoRenovacao(Protocol):       # seguradoras aceitas como apólice anterior
```

A interface pergunta a capacidade, nunca o nome da seguradora — não existe `if cia == "justos"` no React.

### Eventos imutáveis como fonte de verdade

Apólices e parcelas são **projeções** sobre um stream de eventos. Não existe `UPDATE` em entidade de negócio — toda alteração gera um novo evento. O E-Retorno da seguradora entregará movimentos, não estado; a porta existe (`movimentos()`), a sincronização ainda não foi ligada.

### Dinheiro é `Decimal`, nunca `float`

Valor monetário entra por um único conversor que recusa ausente, negativo, não finito e não numérico. Resposta incompleta da seguradora **não vira prêmio zero** — a cotação é recusada com mensagem explícita. Opção de cobertura sem preço não é opção grátis: fica fora da comparação em vez de ser eleita a mais barata.

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
| PDF | reportlab | Comparativo gerado no servidor, sem dependência de navegador |
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

**Usuários de demonstração** (seed carregado automaticamente no startup):

| Papel | E-mail |
|---|---|
| Corretor | `ana.souza@demo.multik`, `carlos.mendes@demo.multik`, `fernanda.lima@demo.multik` |
| Admin | `admin@demo.multik` |

A senha é **gerada aleatoriamente a cada seed** e impressa uma única vez no log
da API — não existe senha fixa no repositório. Para recuperá-la:

```bash
docker compose logs api | grep -A 3 "SEED DEMO"
```

Se o log já rotacionou, recrie o banco de desenvolvimento para disparar um novo
seed.

O seed cria ~40 clientes, ~120 cotações, ~60 propostas e veículos/imóveis para ~60%/25% dos clientes, com dados sintéticos plausíveis (CPFs válidos pelo algoritmo, nomes brasileiros, região Campinas). Idempotente — pode rodar várias vezes.

Sem credenciais de seguradora configuradas, apenas o adapter `fake` aparece no multicálculo. As integrações reais entram sozinhas quando as variáveis de ambiente existem.

---

## Quality Gates

```bash
make check        # roda tudo abaixo em sequência
make lint         # ruff check + format --check
make typecheck    # mypy strict — zero `Any` não declarado
make test         # pytest contra banco de teste descartável
make test-arch    # garante isolamento do adapter Yelum
```

Estado atual: **575 testes de backend com 96% de cobertura**, mais 14 testes de contrato do frontend em `node --test`. O CI executa tudo em todo push e pull request, exige **85% de cobertura mínima** e roda `alembic upgrade head` contra um Postgres real. `gitleaks` bloqueia merge se encontrar segredo no código. Nenhum `# noqa` ou `# type: ignore` sem justificativa documentada.

Os testes usam banco exclusivo de regressão e respostas sintéticas. **Nenhum teste faz chamada real a seguradora.**

---

## Segurança

- **Argon2id** para senhas, sem PBKDF2 nem bcrypt
- **Rate limit** no login: 5 tentativas / 15 min por usuário e por IP; bloqueio progressivo
- **Cookie `httponly + secure + samesite=strict`** — sem token no localStorage, sem XSS leva sessão
- **Sessão revogável** — redefinir senha, desativar conta ou trocar papel invalida as sessões existentes na mesma transação; limite absoluto de 8 h desde o login, com conta e IP verificados também na renovação
- **RLS no Postgres** — corretor vê só a própria carteira; enforcement na camada de dados
- **CPF por índice cego** — HMAC-SHA256 versionado; o CPF em claro nunca é persistido
- **AES-256-GCM em repouso** — payload original da cotação e rascunhos cifrados por tipo de coluna transparente
- **Log com allowlist** — CPF, senha, tokens nunca aparecem em nenhum sink
- **Resposta de terceiro nunca vaza** — erro de seguradora vira mensagem própria; corpo bruto não chega ao usuário nem ao log
- **Auditoria append-only** — trigger no Postgres impede UPDATE e DELETE na tabela de auditoria
- **SecretProvider** — nenhum `os.environ` direto em código de produção
- **gitleaks no CI** — scan de segredos em todo PR

---

## Roadmap

| # | Fase | Status | Gate |
|---|---|---|---|
| 0 | Setup local | ✅ concluída | — |
| 1 | Fundação + adapter fake | ✅ concluída | — |
| 2 | Cotação end-to-end | ✅ concluída | — |
| 3 | Comparativo, PDF, gestão de carteira | ✅ concluída | — |
| 4 | Dashboard, relatórios, seed de demonstração | ✅ concluída | — |
| — | FIPE: proxy Parallelum + FipeSelector combobox | ✅ concluída | — |
| — | UX-SEC: validações, race-fix, responsividade | ✅ concluída | — |
| — | SEC: CSRF, AES-256-GCM, SHA-256, rate-limit, CORS | ✅ concluída | — |
| — | Transmissão controlada, revisão de coberturas e condições de pagamento | ✅ concluída | — |
| — | Aderência ao contrato Justos v2 (auditoria requisito a requisito) | 🔨 em andamento | — |
| 5 | Justos em produção | 🔨 em staging | Chave EC de produção |
| — | Adapter Yelum (ramo imóvel) | ⏸️ fora de escopo por ora | Decisão de produto · credencial de homologação |
| 6 | Paridade ≥ 99% em 200 cotações | ⏳ aguardando | Gate da Fase 5 |
| 7 | E-Retorno (comissão recebida, sinistro) | 📐 desenhado, não ligado | Gate de fase · respostas da seguradora |
| 8 | Deploy GCP + endurecimento | ⏳ aguardando | Precede chave de produção |
| 9 | MCP / bot de cotação | ⏳ aguardando | Após paridade |

Fases 0–4 não dependem de nenhum terceiro. As barreiras seguintes são credencial, homologação e decisão de produto ou de fase — não código pendente.

---

## Estrutura do projeto

```
backend/
  alembic/versions/   # migrações versionadas
  app/
    domain/           # modelos canônicos, eventos — agnósticos de seguradora
    adapters/
      base.py         # PortaSeguradora + capacidades opcionais + tipos canônicos
      registry.py     # get_adapter(cia), cias_para_ramo(ramo), catálogo para a UI
      fake/           # adapter de desenvolvimento
      justos/         # adapter Justos (auto): client, adapter, payment
      yelum/          # único lugar onde código Yelum é permitido
    api/              # rotas FastAPI (cotacao, comparativo, proposta, transmissao…)
    infra/            # secrets, logging, auditoria, db, worker, cpf, encryption,
                      # transmission_control, quote_revision, fipe_cache
  tests/
    test_arch.py      # isolamento arquitetural — nunca remova
frontend/
  src/
    pages/            # CotacaoPage, ComparativoPage, ClientesPage, HistoricoPage…
    components/       # FipeSelector, InsurerIdentity, TransmissionReview, ui/
    hooks/            # useFipe, useAuth
    lib/              # api.ts (cliente HTTP), auth.tsx, utils.ts
  tests/              # contratos de formulário e formatação (node --test)
docs/
  roadmap.md                       # visão geral e estado atual
  adr.md                           # Architecture Decision Records
  escopo.md                        # escopo, requisitos e riscos
  plano-seguranca-fluxo-fase5.md   # plano de execução por lote, com gates
  auditoria-requisitos-justos.md   # matriz requisito → código → teste → lacuna
  justos/                          # contratos da seguradora e planos derivados
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
