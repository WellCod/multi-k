# multi-K — Roadmap

*Atualizado: 2026-08-28 (tarde)*

---

## Visão geral

```
✅ Fase 0      Setup local
✅ Fase 1      Fundação + adapter fake
✅ Fase 2      Cotação end-to-end
✅ Fase 3      Comparativo, PDF, gestão
✅ Fase 4      Dashboard, relatórios, seed demo
✅ Justos      Adapter Justos (aguarda credenciais)
✅ FIPE        Proxy Parallelum + FipeSelector combobox
✅ UX-SEC      Qualidade e segurança do funil de cotação
✅ SEC         Endurecimento de segurança (auditoria 2026-08-26)
🔨 Fase 5      Adapters Yelum + Justos (scaffold + docs; gate: credenciais)
⏳ Fase 6      Paridade (gate: ≥99% em 200 cotações)
⏳ Fase 7      E-Retorno (gate: Security Assessment)
⏳ Fase 8      Deploy GCP + endurecimento
⏳ Fase 9      MCP para o bot
```

---

## Estado atual (2026-08-25)

### O que está funcionando

- Login, sessão, RBAC (corretor / admin)
- Cotação Auto, Moto e Imóvel contra adapter fake
- **FipeSelector combobox** — Marca → Modelo → Ano, step indicator, busca inline, dark mode
- **Proxy FIPE** — 4 endpoints, cache em memória 30 dias, fonte: Parallelum
- Finalidade com opções Uber/App e Táxi
- Validação de data de nascimento (não futura, até 100 anos)
- Comparativo multi-seguradora, PDF, histórico imutável
- Recotar a partir de cotação existente (com pré-preenchimento de dados_risco)
- Dashboard por papel, renovações D-30/D-45/D-60
- Relatórios (produção, funil, mix) com export CSV/XLSX
- Seed sintético de demonstração (3 corretores, ~40 clientes, ~120 cotações)
- Dark mode persistido
- Adapter Justos implementado (ramo auto, aguarda credenciais)
- **UX-SEC completa**: validações, loading states, race-fix, responsividade, segurança

### O que ainda não está em produção

- Cotação Justos: faltam credenciais (`JUSTOS_PARTNER_NAME`, `JUSTOS_BROKER_ID`, chave EC)
- Cotação Yelum: aguarda credencial de homologação
- Payload `dados_risco` em claro no JSONB (planejado para Fase 8/KMS)

---

## FASE UX-SEC — concluída ✅

*Entregue em 2026-08-25*

### P0 — Crítico ✅

| # | Problema | Arquivo | Status |
|---|---|---|---|
| P0.1 | Typo `commissao_pct` → `comissao_pct` | `alembic/versions/004_fix_comissao_pct.py` | ✅ Migration criada |
| P0.2 | `dados_risco` sem validação backend | `api/cotacao_router.py` — `_RISCO_SCHEMAS` + `model_validator` | ✅ Retorna 422 para dados inválidos |
| P0.3 | Frontend: comissão > 100% sem erro | `CotacaoPage.tsx` — `TransmitirModal` | ✅ Validação 1–30% com mensagem inline |

### P1 — Alto ✅

| # | Problema | Arquivo | Status |
|---|---|---|---|
| P1.1 | Race condition: dois pollings simultâneos | `CotacaoPage.tsx` `startPolling` | ✅ `stopPolling()` chamado no início |
| P1.2 | Vigência: `fim < início` aceito | `step4Schema` + backend | ✅ `.superRefine` Zod + validação BE |
| P1.3 | Erro busca CPF silencioso | `CotacaoPage.tsx` `searchByCpf` | ✅ Banner inline `cpfSearchError` |
| P1.4 | `alert()` ao falhar cotação | `CotacaoPage.tsx` | ✅ `setCotacaoErrMsg` → `serverError` no Step4 |
| P1.5 | `valor_imovel` enviado como string BRL | `step2ImovelSchema` | ✅ Transform: remove ponto, troca vírgula |
| P1.6 | Sem loading state ao criar cotação | `CotacaoPage.tsx` | ✅ `criando` state, botão desabilitado, "Enviando…" |

### P2 — Médio ✅

| # | Problema | Arquivo | Status |
|---|---|---|---|
| P2.1 | PII em `sessionStorage` após logout | `auth.tsx` | ✅ `sessionStorage.clear()` no logout |
| P2.2 | `/cotacao?recotar=invalido` sem feedback | `CotacaoPage.tsx` | ✅ `recotarError` banner inline |
| P2.3 | Labels de cobertura ilegíveis | Step 3 | ✅ Exibe `d.descricao` dos domínios + código em cinza |
| P2.4 | Grids 2-col sem breakpoint mobile | Múltiplos steps | ✅ `grid-cols-1 sm:grid-cols-2` em todos os grids |
| P2.5 | Timer de polling não limpo no unmount | `CotacaoPage.tsx` | ✅ `useEffect(() => () => clearTimeout(pollRef.current), [])` |

### Auditoria de código (2026-08-25) ✅

| # | Problema | Arquivo | Status |
|---|---|---|---|
| A2 | `cpf.py` sem warning ao usar chave dev-only | `infra/cpf.py` | ✅ `structlog.warning` quando chave padrão em uso |
| D1 | `_get_*_ou_404` duplicado nos 3 routers | `api/_utils.py` | ✅ Helper genérico `get_or_404` extraído |
| FS1 | sessionStorage não limpo no logout | `lib/auth.tsx` | ✅ `sessionStorage.clear()` no logout |
| FD1 | `fmtReal`/`fmtDate` duplicadas no HomePage | `lib/utils.ts` + `pages/HomePage.tsx` | ✅ Consolidado em utils.ts + `formatDatetime` adicionado |
| MK1 | `make test` não dropa DB anterior | `Makefile` | ✅ `DROP DATABASE IF EXISTS` antes do CREATE |

### Critério de pronto — todos ✅

- [x] `make check` passa com zero erros
- [x] `commissao_pct` corrigido no banco via migration
- [x] Criar cotação com `dados_risco` inválido retorna 422 (não 200)
- [x] Polling com dois cliques rápidos não gera estado inconsistente
- [x] `fim_vigencia < inicio_vigencia` rejeitado com mensagem clara
- [x] Formulário usável em mobile (320px)
- [x] sessionStorage limpo após cancelamento, logout ou conclusão

---

## FASE FIPE — concluída ✅

*Entregue em 2026-08-24*

| Entregável | Status |
|---|---|
| `backend/app/infra/fipe_cache.py` — cache TTL 30 dias, thread-safe | ✅ |
| `backend/app/api/fipe_router.py` — proxy Parallelum, 4 endpoints | ✅ |
| `frontend/src/hooks/useFipe.ts` — 4 hooks com cancelamento | ✅ |
| `frontend/src/components/FipeSelector.tsx` — combobox cascata, step indicator | ✅ |
| `CotacaoPage.tsx` — Step2Auto e Step2Moto integrados | ✅ |
| Finalidade: Uber/App e Táxi adicionados | ✅ |
| Validação data de nascimento | ✅ |
| Adapter Justos: `"uber"` → `"app_driver"` | ✅ |

**Decisões desta fase:**
- Fonte: Parallelum exclusivo (BrasilAPI descartada — só tem `/marcas`, usa `valor` em vez de `codigo`, inconsistente)
- Cache em memória (não Redis) — FIPE muda mensalmente; reiniciar o processo é aceitável no MVP
- ComboBox inline em vez de input+select separados — UX mais intuitiva sem dependência extra

---

## FASE SEC — Endurecimento de segurança ✅

*Entregue em 2026-08-26*

### Auditoria (2026-08-26)

| # | Severidade | Problema | Arquivo | Status |
|---|---|---|---|---|
| M1 | Médio | `hash()` builtin (não-determinístico entre processos) no audit log de falha de login | `api/auth_router.py:68` | ✅ `hashlib.sha256` |
| C3 | Crítico | `ip_origem` gravada na sessão mas nunca comparada no re-uso | `infra/auth_service.py`, `api/deps.py` | ✅ Soft-check: warning no log quando IP muda |
| B1 | Baixo | Adminer exposto em `0.0.0.0:8080` — acessível na rede local | `docker-compose.yml` | ✅ `127.0.0.1:8080:8080` |
| B2 | Baixo | CORS sem proteção contra `*` em produção | `main.py` | ✅ RuntimeError no startup se `*` + `DEBUG=false` |
| M3 | Médio | FIPE sem rate-limit nos endpoints públicos | `api/fipe_router.py` | ✅ 60 req/min por IP (sliding-window em memória) |
| B3 | Baixo | Timeout explícito no cliente Justos | `adapters/justos/client.py` | ✅ Já implementado: 30 s auth, 60 s cotação |
| A1 | Alto | `secure=False` no cookie fora de HTTPS | `api/auth_router.py` | ✅ `_SECURE_COOKIE = not _debug` — em produção sempre `True` |

| C2 | Crítico | `_DEV_KEY` HMAC do CPF — fallback inseguro mesmo em DEBUG | `infra/cpf.py` | ✅ `CPF_HMAC_KEY` obrigatório sempre; testes usam fixture |
| B4 | Baixo | Sem pin de versão máxima — upgrade major silencioso | `pyproject.toml` | ✅ Limites superiores adicionados em todas as dependências |

| A2 | Alto | Sem token CSRF (mitigado por `SameSite=Strict`) | `main.py` + `auth_router.py` + `api.ts` | ✅ Double-submit cookie (middleware + cookie `csrf_token` + header `X-CSRF-Token`) |
| M4 | Médio | `dados_negocio` sem schema na transmissão | `api/proposta_router.py` | ✅ Validator: max 50 chaves, max 10 KB JSON |

### C1 — concluído ✅

| # | Severidade | Problema | Arquivo | Status |
|---|---|---|---|---|
| C1 | Crítico | `payload_original` em JSONB claro | `infra/models.py`, `infra/encryption.py` | ✅ AES-256-GCM via TypeDecorator; chave via PAYLOAD_ENCRYPTION_KEY |

### Itens planejados (Fase 8 / pré-produção)

| # | Severidade | Problema | Arquivo | Quando |
|---|---|---|---|---|
| A3 | Alto | Rate-limit por IP em memória (não sobrevive restart) | `infra/auth_service.py` | Fase 8 (Redis) |
| M2 | N/A | Token Justos opaco (~28 chars), não JWT — expiração via TTL fixo (ADR-022) | `adapters/justos/client.py` | — |

### Critério de pronto — todos ✅

- [x] `make check` passa com zero erros
- [x] IP de origem comparado a cada uso da sessão (warning no log)
- [x] Audit log de falha de login com hash determinístico (SHA-256)
- [x] Adminer acessível apenas em localhost
- [x] CORS com `*` bloqueado em produção
- [x] Endpoints FIPE com rate-limit 60 req/min por IP
- [x] `CPF_HMAC_KEY` obrigatório — sem fallback de chave hardcoded
- [x] Dependências com limites de versão máxima (sem upgrade major silencioso)
- [x] CSRF double-submit cookie em todas as rotas mutantes autenticadas
- [x] `dados_negocio` limitado a 50 chaves e 10 KB

---

## FASE 5 — Adapter Yelum real

**Gate:** credencial de mock ou homologação  
**Estimativa:** 3–5 semanas após receber credencial  
**Produto inicial:** Residência (produto 11030); Auto aguarda documentação do ponto focal

### Scaffold + documentação entregues (2026-08-28)

| Arquivo | Conteúdo |
|---|---|
| `app/adapters/yelum/client.py` | HTTP client, auth form-encoded, cache token 1 h, retry em 401 |
| `app/adapters/yelum/adapter.py` | `YelumSeguradora` — cotar/recotar/transmitir, quirks documentados |
| `app/adapters/registry.py` | Fábrica `get_adapter(cia)` — fora do escopo de scan do test_arch |
| `tests/test_yelum_adapter.py` | 7 testes com respx (sucesso, vistoria, recusa, retry 401) |

**Quirks Yelum já tratados:**
- Booleans como `"T"/"F"` (exceto `NeedInspectionRisk` que é bool real)
- `TotalPremiumValue` é número no topo, string em `Installments`
- Chave de sucesso/erro: `Success` (sucesso) vs `Sucesso` (erro) — adapter aceita ambas
- Retry único automático em 401 sem Redis

**Para ativar Yelum quando a credencial chegar:**
1. Preencher no `.env`: `YELUM_CLIENT_ID`, `YELUM_CLIENT_SECRET`, `YELUM_USERNAME`, `YELUM_PASSWORD`
2. Ajustar `YELUM_ENV=homologacao` (ou `producao`)
3. Confirmar nomes de campos com a Collection Postman (ver `_payload_cotacao` em `adapter.py`)
4. Yelum aparece automaticamente via `cias_para_ramo("imovel")` — zero código novo

**Para ativar Justos quando as credenciais chegarem:**
1. Preencher no `.env`: `JUSTOS_PARTNER_NAME`, `JUSTOS_BROKER_ID`, `JUSTOS_CPF_CNPJ`, `JUSTOS_PRIVATE_KEY`
2. Ajustar `JUSTOS_ENV=production` (padrão: staging)
3. Justos aparece automaticamente via `cias_para_ramo("auto")` — zero código novo

### Melhorias entregues (2026-08-28 — pós-scaffold)

| Item | Arquivo | Status |
|---|---|---|
| Proponente aninhado no Yelum adapter | `adapters/yelum/adapter.py` | ✅ |
| cpf+telefone no bloco proponente (frontend) | `CotacaoPage.tsx` | ✅ |
| Campos opcionais Yelum no Step2Imovel | `CotacaoPage.tsx` | ✅ |
| `cobertura_imovel` CBE10-CBE80 no seed + migração 007 | `seed.py`, `007_cobertura_imovel_dominios.py` | ✅ |
| Justos integrado ao `cias_para_ramo("auto")` | `adapters/registry.py` | ✅ |
| Proponente aninhado no Justos adapter | `adapters/justos/adapter.py` | ✅ |
| `ci_code` em renovações Justos | `adapters/justos/client.py` + `adapter.py` | ✅ |
| Armazena fipe_price_percentage_covered, commission, plans | `adapters/justos/adapter.py` | ✅ |
| 5 testes Justos adapter | `tests/test_justos_adapter.py` | ✅ |
| Cobertura do comparativo por-job | `tests/test_proposta.py` | ✅ |

Ações humanas necessárias:
1. E-mail ao ponto focal Yelum com 12 perguntas (`docs/escopo.md §10`)
2. Cadastro no Portal do Desenvolvedor Yelum
3. NDA (se exigido para homologação)

---

## FASE 6 — Paridade

**Gate:** ≥ 99% de paridade exata em 200 cotações, sustentado 30 dias  
**Estimativa:** 4–8 semanas

---

## FASE 7 — E-Retorno

**Gate:** Security Assessment assinado  
**Estimativa:** 4–6 semanas

---

## FASE 8 — Deploy GCP

**Gate:** precede chave de produção  
**Estimativa:** 3–4 semanas

Cloud Run + Cloud SQL + Secret Manager + KMS. Região `southamerica-east1`.

Itens de segurança antes do deploy:
- KMS para cifrar `payload_original` (PII em claro no JSONB até lá)
- Rotação de `CPF_HMAC_KEY` com plano de migração de índices
- `DEBUG=false` obrigatório em todos os ambientes de produção

---

## FASE 9 — MCP para o bot

**Gate:** após gate de paridade (Fase 6)  
**Estimativa:** 2–3 semanas

---

## Decisões de arquitetura registradas

| Decisão | Motivo |
|---|---|
| Parallelum exclusivo para FIPE (sem BrasilAPI) | BrasilAPI só tem /marcas e usa campo `valor` em vez de `codigo` — inconsistente |
| Cache FIPE em memória (não DB) | FIPE muda mensalmente; reiniciar processo é aceitável no MVP |
| ComboBox inline no FipeSelector | UX mais intuitiva do que input+select separados; zero dependência nova |
| UX-SEC antes de Fase 5 | Não faz sentido integrar nova seguradora com funil quebrado; qualidade antes de escala |
| `codigo_fipe` obrigatório no Justos | Exigência explícita da API Justos (`vehicle_fipe_code`) |
| Adapter Justos antes de Yelum | Documentação Justos disponível; Yelum aguarda credencial |
| `sessionStorage.clear()` no logout | Garante que todo PII (rascunho de cotação, dados de sessão) é apagado |
| Helper genérico `get_or_404` em `api/_utils.py` | Elimina triplicação idêntica nos 3 routers; erro 404 padronizado |
