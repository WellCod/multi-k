# multi-K — Roadmap

*Atualizado: 2026-08-21*

---

## Visão geral

```
✅ Fase 0   Setup local
✅ Fase 1   Fundação + adapter fake
✅ Fase 2   Cotação end-to-end
✅ Fase 3   Comparativo, PDF, gestão
✅ Fase 4   Dashboard, relatórios, seed demo
✅ Justos   Adapter Justos (aguarda credenciais + form FIPE)
🔧 FIPE     Integração Tabela FIPE              ← PRÓXIMA
⏳ Fase 5   Adapter Yelum (gate: credencial)
⏳ Fase 6   Paridade (gate: ≥99% em 200 cotações)
⏳ Fase 7   E-Retorno (gate: Security Assessment)
⏳ Fase 8   Deploy GCP + endurecimento
⏳ Fase 9   MCP para o bot
```

---

## Estado atual (2026-08-21)

### O que está funcionando
- Login, sessão, RBAC (corretor / admin)
- Cotação Auto, Moto e Imóvel contra adapter fake
- Comparativo multi-seguradora, PDF, histórico imutável
- Recotar a partir de cotação existente
- Dashboard por papel, renovações D-30/D-45/D-60
- Relatórios (produção, funil, mix) com export CSV/XLSX
- Seed sintético de demonstração (3 corretores, ~40 clientes, ~120 cotações)
- Dark mode persistido
- Adapter Justos implementado (ramo auto, aguarda credenciais e form FIPE)

### O que ainda não está funcionando em produção
- Cotação Justos: faltam credenciais + campos FIPE no formulário
- Cotação Yelum: aguarda credencial de homologação
- Formulário auto/moto sem seleção FIPE (campos manuais por enquanto)

---

## FASE FIPE — Plano detalhado

**Estimativa:** 1–2 dias de desenvolvimento  
**Branch sugerida:** `feat/fipe-selector`  
**PR alvo:** `main`

### Backend (½ dia)

| Arquivo | O que fazer |
|---|---|
| `backend/app/infra/fipe_cache.py` | Cache em memória, TTL 30 dias, thread-safe |
| `backend/app/api/fipe_router.py` | 4 endpoints GET proxy + cache |
| `backend/app/main.py` | Registrar fipe_router |

**Endpoints:**
```
GET /api/fipe/marcas?tipo=carros
GET /api/fipe/modelos?tipo=carros&marca_id=59
GET /api/fipe/anos?tipo=carros&marca_id=59&modelo_id=5940
GET /api/fipe/preco?tipo=carros&marca_id=59&modelo_id=5940&ano_id=2023-1
```

**Fonte de dados:** BrasilAPI (primária) → Parallelum (fallback)  
**Rate limit BrasilAPI:** sem limite publicado; cache elimina 99% das chamadas  
**Cache TTL:** 30 dias (FIPE atualiza mensalmente)

### Frontend (1 dia)

| Arquivo | O que fazer |
|---|---|
| `frontend/src/hooks/useFipe.ts` | 4 hooks: marcas, modelos, anos, preco |
| `frontend/src/components/FipeSelector.tsx` | Selects em cascata com loading/dark mode |
| `frontend/src/pages/CotacaoPage.tsx` | Substituir Step2Auto e Step2Moto |

**UX do FipeSelector:**
1. Select "Marca" (com input de busca — há ~60 marcas)
2. Select "Modelo" (habilitado após marca, ~100 modelos)
3. Select "Ano / Combustível" (habilitado após modelo)
4. Exibe read-only: código FIPE + valor formatado em R$
5. Campo "Placa" opcional (livre, não bloqueia cotação)
6. Skeleton loader enquanto carrega; erro amigável se API falhar

**Mudanças no schema Zod:**
- Adiciona: `codigo_fipe` (obrigatório para Justos)
- Adiciona: `placa` (opcional)
- Mantém: `cep_pernoite`, `finalidade`, `blindado`, `garagem`
- Remove manual: `marca`, `modelo` (ficam read-only preenchidos pelo selector)

### Critério de pronto
- [ ] Usuário seleciona Marca → Modelo → Ano → `codigo_fipe` preenchido
- [ ] `dados_risco` enviado inclui `codigo_fipe`
- [ ] `make check` passa (ruff + mypy + pytest)
- [ ] Dark mode funcionando no FipeSelector
- [ ] Erro de API externa não quebra o formulário

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
| BrasilAPI + cache backend para FIPE | Sem rate limit previsível na BrasilAPI; cache 30 dias elimina dependência |
| Adapter Justos antes de Yelum | Documentação Justos disponível; Yelum aguarda credencial |
| Cache FIPE em memória (não DB) | FIPE muda mensalmente; reiniciar processo é aceitável no MVP |
| Parallelum como fallback da BrasilAPI | Redundância sem custo; mesma estrutura de dados |
| `codigo_fipe` obrigatório no Justos | Exigência explícita da API Justos (`vehicle_fipe_code`) |
