# multi-K — Prompts faseados

Um prompt por fase. Cole inteiro no assistente junto com `docs/escopo.md` e `docs/adr.md`.

**Como usar:** não pule fases, não junte duas. A seção "NÃO faça" de cada uma é o que segura escopo quando é você sozinho decidindo — ela é a parte mais importante do prompt, não um rodapé.

**Regra permanente:** quatro módulos você lê linha por linha e nunca aceita em bloco — auth/sessão, cifragem de PII, redação de log, enforcement de RLS. O resto pode ser revisado por comportamento.

---

## FASE 0 — Setup local ✅ concluída
## FASE 1 — Fundação ✅ concluída
## FASE 2 — Cotação end-to-end ✅ concluída
## FASE 3 — Comparativo, PDF, gestão ✅ concluída
## FASE 4 — Dashboard, relatórios, seed ✅ concluída
## FASE JUSTOS — Adapter Justos ✅ concluído (aguarda credenciais)
## FASE FIPE — Integração Tabela FIPE ✅ concluída

---

## FASE UX-SEC — Qualidade e segurança do funil de cotação

**Objetivo:** corrigir problemas de validação, segurança e UX identificados na
auditoria do funil `/cotacao` em 2026-08-24, antes de integrar novas seguradoras.
Qualidade de funil antes de escala.

**Branch:** `feat/ux-sec`  
**Estimativa:** 1 semana

### P0 — Crítico (atacar primeiro, quebra dados reais)

#### P0.1 — Typo `commissao_pct` no banco

```
Arquivo: backend/app/infra/models.py linha 212
Problema: coluna se chama `commissao_pct` (duplo ss), todo o código Python e
          frontend usa `comissao_pct` (um s). Comissões persistem no campo errado.

Ação:
1. Renomear coluna em models.py para `comissao_pct`
2. Criar migration: backend/alembic/versions/003_fix_comissao_pct.py
   ALTER TABLE proposta RENAME COLUMN commissao_pct TO comissao_pct;
3. Verificar todos os arquivos que referenciam o nome do campo
4. `make check` deve passar
```

#### P0.2 — `dados_risco` sem validação no backend

```
Arquivo: backend/app/api/cotacao_router.py
Problema: CriarCotacaoInput aceita `dados: dict[str, Any]` sem schema.
          Bypass via curl aceita qualquer payload — cotação criada com lixo.

Ação:
1. Criar schemas Pydantic em backend/app/domain/risco.py (ou cotacao_router.py):
   - RiscoAutoInput: cep_pernoite, codigo_fipe, ano_modelo, finalidade (obrigatórios)
   - RiscoMotoInput: cep_pernoite, codigo_fipe, cilindrada, categoria, finalidade
   - RiscoImovelInput: cep, tipo_imovel, tipo_construcao, valor_imovel (Decimal, > 0)
2. Usar Annotated + discriminator: ramo="auto" → RiscoAutoInput, etc.
3. Campos extras são permitidos (seguradora pode precisar de campos adicionais)
4. Testar com pytest: cotação com ramo="auto" sem codigo_fipe → 422
```

#### P0.3 — Comissão sem validação visual de range

```
Arquivo: frontend/src/pages/CotacaoPage.tsx (modal transmitir proposta)
Problema: campo de comissão não valida visualmente range 1%–30%.
          Usuário pode digitar 150% sem nenhum erro na tela.

Ação:
1. Adicionar validação no Zod schema da modal: comissao deve estar entre 0.01 e 0.30
2. Mostrar mensagem de erro inline no campo
3. Desabilitar botão "Confirmar" enquanto inválido
```

### P1 — Alto

#### P1.1 — Race condition no polling

```
Arquivo: frontend/src/pages/CotacaoPage.tsx (startPolling / stopPolling)
Problema: dois cliques rápidos criam dois timers simultâneos;
          setState pode ser chamado após unmount.

Ação:
1. Antes de startPolling, chamar stopPolling (limpar timer anterior)
2. Usar AbortController para cancelar requisição HTTP em andamento
3. Adicionar flag `mounted` no useEffect que contém o polling:
   return () => { mounted = false; stopPolling(); }
4. Só chamar setCotacao se mounted === true
```

#### P1.2 — Vigência sem validação cruzada

```
Arquivo: frontend/src/pages/CotacaoPage.tsx (step4Schema)
Problema: aceita fim_vigencia < inicio_vigencia sem nenhum erro.

Ação frontend:
  step4Schema: adicionar .refine() que valida:
  - inicio_vigencia não pode ser mais de 30 dias no passado
  - fim_vigencia deve ser > inicio_vigencia
  - intervalo deve ser entre 1 mês e 13 meses (seguro anual com pequena margem)

Ação backend:
  Em proposta_router.py ao criar proposta, validar inicio < fim.
  Retornar 422 com mensagem clara se inválido.
```

#### P1.3 — Erro de busca CPF silencioso

```
Arquivo: frontend/src/pages/CotacaoPage.tsx (searchByCpf, catch vazio)
Problema: se API cair durante busca CPF, usuário avança sem saber.

Ação:
1. No catch, guardar estado: setSearchError("Não foi possível verificar o CPF")
2. Exibir banner amarelo (warning, não bloqueador) abaixo do campo CPF
3. Usuário ainda pode avançar — o erro é informativo, não bloqueador
```

#### P1.4 — `alert()` ao falhar criação de cotação

```
Arquivo: frontend/src/pages/CotacaoPage.tsx (handleStep4 catch)
Problema: alert() bloqueia UI e parece erro do browser.

Ação:
1. Criar componente <ErrorBanner message={} onRetry={} /> reutilizável
2. Substituir alert() por setErrorMsg(err.message)
3. Exibir ErrorBanner no step 5 abaixo do LoadingPanel
4. Botão "Tentar novamente" no ErrorBanner que volta ao step 4
```

#### P1.5 — `valor_imovel` enviado como string mal formatada

```
Arquivo: frontend/src/pages/CotacaoPage.tsx (step2ImovelSchema)
Problema: transform atual faz v.replace(/\D/g, ".") — converte letras em ponto,
          gerando strings malformadas como "300000.00" com formatação incorreta.

Ação:
1. Novo transform: remover tudo exceto dígitos e vírgula, tratar vírgula como decimal
   z.string()
     .transform(v => v.replace(/[^\d,]/g, "").replace(",", "."))
     .pipe(z.coerce.number().positive("Valor deve ser maior que zero"))
2. Exibir preview formatado em R$ abaixo do campo (read-only)
```

#### P1.6 — Sem loading state durante criação de cotação

```
Arquivo: frontend/src/pages/CotacaoPage.tsx (handleStep4)
Problema: usuário clica "Solicitar cotação", nada acontece visivelmente até
          o step 5 aparecer — parece travado.

Ação:
1. Adicionar estado: const [criando, setCriando] = useState(false)
2. No handleStep4: setCriando(true) antes da chamada, false no finally
3. Desabilitar botão "Solicitar cotação" enquanto criando === true
4. Mostrar spinner no botão: <Spinner /> Criando cotação...
```

### P2 — Médio

#### P2.1 — PII em sessionStorage

```
Arquivo: frontend/src/pages/CotacaoPage.tsx (saveRascunho / clearRascunho)
Problema: dados do veículo, CEP e dados FIPE persistem no sessionStorage
          após o usuário sair sem completar.

Ação:
1. Chamar clearRascunho() no handleCancelar (já existe? verificar)
2. Chamar clearRascunho() no handleStep5 após cotação criada com sucesso
3. Verificar se clearRascunho limpa toda a chave STORAGE_KEY — se não, corrigir
```

#### P2.2 — `/cotacao?recotar=` sem cotação

```
Arquivo: frontend/src/pages/CotacaoPage.tsx (useEffect recotar)
Problema: URL com UUID inválido ou de outro usuário não dá feedback.

Ação:
1. Adicionar .catch() no api.cotacoes.get(recotar)
2. setRecotar Error("Cotação não encontrada ou sem permissão de acesso")
3. Exibir ErrorBanner no topo da página — não bloquear formulário vazio
4. Botão "Fazer nova cotação" no banner que limpa o query param
```

#### P2.3 — Labels de cobertura ilegíveis

```
Arquivo: frontend/src/pages/CotacaoPage.tsx (Step 3 — seleção de coberturas)
Problema: checkboxes mostram códigos internos: CASCO, RCF, APP, VIDROS, etc.

Ação:
1. Criar mapa de labels em lib/dominios.ts:
   const COBERTURA_LABELS: Record<string, string> = {
     CASCO: "Colisão e danos",
     RCF: "Responsabilidade civil",
     APP: "Acidentes pessoais de passageiros",
     VIDROS: "Vidros e retrovisores",
     INCENDIO: "Incêndio e raio",
     ROUBO: "Roubo e furto",
     RESP_CIVIL: "Danos a terceiros",
     DANOS_ELET: "Danos elétricos",
     QUEBRA_VIDROS: "Quebra de vidros",
   }
2. Usar COBERTURA_LABELS[codigo] ?? codigo como label visível
```

#### P2.4 — Responsividade mobile

```
Arquivos: múltiplos steps em CotacaoPage.tsx
Problema: grid-cols-2 fixo sem breakpoint — campos estreitos em celular (320px).

Ação:
1. Substituir className="grid grid-cols-2 gap-4" por
   className="grid grid-cols-1 sm:grid-cols-2 gap-4"
   em todos os grids do formulário
2. Verificar FipeSelector em tela pequena — ComboBox com max-h-52 pode sair da tela
3. Testar com DevTools em 375px (iPhone SE)
```

#### P2.5 — Cleanup de timers no unmount

```
Arquivo: frontend/src/pages/CotacaoPage.tsx (startPolling)
Problema: se componente desmonta durante polling (ex: navegação), timer continua.

Ação: já coberto pelo P1.1 (AbortController + flag mounted)
Verificar: stopPolling limpa pollRef.current com clearTimeout — confirmar.
```

### NÃO faça nesta fase

- Não adicione nova seguradora (Fase 5)
- Não mude o modelo de dados de cotação ou proposta além da correção do typo
- Não implemente criptografia de PII (KMS é Fase 8)
- Não mude a autenticação ou sessão
- Não implemente validação de CEP via API externa (ViaCEP) — vai para Fase 5+

### Critério de pronto

- [ ] `make check` passa sem warnings
- [ ] Migration `003` aplicada sem erro
- [ ] Criar cotação auto sem `codigo_fipe` → backend retorna 422
- [ ] Criar cotação com `fim_vigencia < inicio_vigencia` → erro inline
- [ ] Dois cliques rápidos em "Solicitar" → apenas um polling ativo
- [ ] Formulário legível em 375px
- [ ] sessionStorage limpo após cancelar ou concluir

---

## FASE 5 — Adapter Yelum real

*(aguarda credencial de homologação)*

**Objetivo:** integração com a API da Yelum para cotação de Residência (depois Auto).

**Gate de entrada:** credencial de mock ou homologação recebida do ponto focal Yelum.

**Restrição crítica:** código Yelum fica exclusivamente em `adapters/yelum/`. O CI bloqueia vazamento por grep em todo PR. O `test_arch.py` nunca deve ser modificado.

Contexto completo: `docs/escopo.md §4` e `docs/escopo.md §10` (12 perguntas ao ponto focal).

---

## FASE 6 — Paridade

*(gate: ≥99% em 200 cotações, 30 dias)*

Implementar suite de paridade automática: robot que faz cotação pelo sistema e pelo portal da seguradora, compara prêmio centavo a centavo. Gate: 99% de match sustentado por 30 dias.

---

## FASE 7 — E-Retorno

*(gate: Security Assessment assinado pela Yelum)*

Implementar ingestão de movimentos via E-Retorno: emissões, endossos, parcelas, comissões, sinistros. Conciliação automática de comissão prevista vs recebida.

---

## FASE 8 — Deploy GCP

*(gate: precede chave de produção)*

Cloud Run + Cloud SQL + Secret Manager + KMS. Envelope encryption para CPF/chassi/placa. Região `southamerica-east1`.

---

## FASE 9 — MCP para o bot

*(gate: após paridade)*

Expor multi-K como MCP server para bot interno da corretora. Ferramentas: `cotar(ramo, dados)`, `comparar(cotacao_id)`, `transmitir(cotacao_id, plano)`.
