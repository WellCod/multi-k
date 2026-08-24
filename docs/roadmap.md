# multi-K — Roadmap

*Atualizado: 2026-08-24*

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
🔧 UX-SEC      Qualidade e segurança do funil de cotação   ← PRÓXIMA
⏳ Fase 5      Adapter Yelum (gate: credencial)
⏳ Fase 6      Paridade (gate: ≥99% em 200 cotações)
⏳ Fase 7      E-Retorno (gate: Security Assessment)
⏳ Fase 8      Deploy GCP + endurecimento
⏳ Fase 9      MCP para o bot
```

---

## Estado atual (2026-08-24)

### O que está funcionando

- Login, sessão, RBAC (corretor / admin)
- Cotação Auto, Moto e Imóvel contra adapter fake
- **FipeSelector combobox** — Marca → Modelo → Ano, step indicator, busca inline, dark mode
- **Proxy FIPE** — 4 endpoints, cache em memória 30 dias, fonte: Parallelum
- Finalidade com opções Uber/App e Táxi
- Validação de data de nascimento (não futura, até 100 anos)
- Comparativo multi-seguradora, PDF, histórico imutável
- Recotar a partir de cotação existente
- Dashboard por papel, renovações D-30/D-45/D-60
- Relatórios (produção, funil, mix) com export CSV/XLSX
- Seed sintético de demonstração (3 corretores, ~40 clientes, ~120 cotações)
- Dark mode persistido
- Adapter Justos implementado (ramo auto, aguarda credenciais)

### O que ainda não está em produção

- Cotação Justos: faltam credenciais (`JUSTOS_PARTNER_NAME`, `JUSTOS_BROKER_ID`, chave EC)
- Cotação Yelum: aguarda credencial de homologação
- Issues de UX/segurança identificados na análise de 2026-08-24 (detalhados abaixo)

---

## FASE UX-SEC — Qualidade e segurança do funil de cotação

**Estimativa:** 1 semana  
**Branch:** `feat/ux-sec`  
**Origem:** auditoria técnica de 2026-08-24 do `/cotacao`

### P0 — Crítico (quebra dados reais)

| # | Problema | Arquivo | Ação |
|---|---|---|---|
| P0.1 | Typo `commissao_pct` no banco (deveria ser `comissao_pct`) | `infra/models.py:212`, migration Alembic | Corrigir campo + migration `003_fix_commissao_pct.py` |
| P0.2 | `dados_risco` aceita `dict[str, Any]` sem validação backend | `api/cotacao_router.py` | Criar schemas Pydantic `RiscoAutoInput`, `RiscoMotoInput`, `RiscoImovelInput` com discriminator por `ramo` |
| P0.3 | Frontend permite comissão > 100% sem erro visual | `CotacaoPage.tsx` (modal transmitir) | Adicionar `min(0.01)` `max(0.30)` no input + mensagem de erro |

### P1 — Alto (UX e fluxo quebrado)

| # | Problema | Arquivo | Ação |
|---|---|---|---|
| P1.1 | Race condition: dois pollings simultâneos | `CotacaoPage.tsx` `startPolling` | Cancelar timer anterior antes de iniciar; usar `AbortController` para a requisição |
| P1.2 | Vigência: `fim < início` aceito sem erro | `CotacaoPage.tsx` `step4Schema` + backend | Adicionar `.refine(fim > inicio)` no Zod; validar no backend ao criar proposta |
| P1.3 | Erro busca CPF silencioso | `CotacaoPage.tsx` `searchByCpf` | Substituir `catch {}` por banner de erro inline "Não foi possível buscar o cliente" |
| P1.4 | `alert()` ao falhar criação de cotação | `CotacaoPage.tsx` `handleStep4` | Substituir por `<ErrorBanner>` inline no step 5 |
| P1.5 | `valor_imovel` enviado como string | `step2ImovelSchema` | Transform correto: remover pontos, trocar vírgula, parsear como Decimal; validar > 0 |
| P1.6 | Sem loading state ao criar cotação | `CotacaoPage.tsx` `handleStep4` | Desabilitar botão e mostrar spinner entre step 4 → step 5 |

### P2 — Médio (segurança e qualidade)

| # | Problema | Arquivo | Ação |
|---|---|---|---|
| P2.1 | PII (placa, CEP, dados FIPE) em `sessionStorage` | `CotacaoPage.tsx` `saveRascunho` | Limpar `sessionStorage` ao cancelar, logout ou completar cotação |
| P2.2 | `/cotacao?recotar=uuid-inválido` sem feedback | `CotacaoPage.tsx` useEffect recotar | Capturar erro, mostrar `<ErrorBanner>` "Cotação não encontrada ou sem permissão" |
| P2.3 | Labels de cobertura: `CASCO`, `RCF`, `APP` | Step 3 cobertura | Mapa de labels legíveis: CASCO→"Colisão e danos", RCF→"Responsabilidade civil", etc. |
| P2.4 | Grids 2-col sem breakpoint mobile | Múltiplos steps | Trocar `grid-cols-2` por `grid-cols-1 sm:grid-cols-2` |
| P2.5 | Timer de polling não é limpo no unmount | `CotacaoPage.tsx` | Adicionar cleanup `return () => stopPolling()` no useEffect |

### Critério de pronto

- [ ] `make check` passa com zero erros
- [ ] `commissao_pct` corrigido no banco via migration
- [ ] Criar cotação com `dados_risco` inválido retorna 422 (não 200)
- [ ] Polling com dois cliques rápidos não gera estado inconsistente
- [ ] `fim_vigencia < inicio_vigencia` rejeitado com mensagem clara
- [ ] Formulário usável em mobile (320px)
- [ ] sessionStorage limpo após cancelamento ou conclusão

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

## FASE 5 — Adapter Yelum real

**Gate:** credencial de mock ou homologação  
**Estimativa:** 3–5 semanas  
**Produto inicial:** Residência (depois Auto)

Contexto: `docs/escopo.md §4` e `docs/prompts.md → FASE 5`

Ações humanas necessárias antes:
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
