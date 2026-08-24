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

---

## FASE FIPE — Integração Tabela FIPE

**Objetivo:** substituir campos manuais de veículo (marca/modelo/ano digitados)
por seleção assistida via tabela FIPE oficial, com cache no backend para
escalar sem depender do rate limit de APIs externas.

**Por que agora:** o adapter Justos exige `codigo_fipe` obrigatório. Sem FIPE
no form, nenhuma cotação Justos funciona em produção.

### 1. BACKEND — proxy + cache

Crie `backend/app/api/fipe_router.py` com 4 rotas:

```
GET /fipe/marcas?tipo=carros|motos
GET /fipe/modelos?tipo=carros&marca_id={codigo}
GET /fipe/anos?tipo=carros&marca_id={codigo}&modelo_id={codigo}
GET /fipe/preco?tipo=carros&marca_id={m}&modelo_id={m}&ano_id={a}
```

Cache em memória com TTL de 30 dias (FIPE atualiza mensalmente).
Fonte primária: BrasilAPI (`https://brasilapi.com.br/api/fipe/`).
Fallback: Parallelum (`https://parallelum.com.br/fipe/api/v1/`).

Não exige autenticação para chamar — rotas públicas dentro do `/api`.
Retorno sempre serializado como JSON limpo, sem expor campos desnecessários.

Estrutura de cache em memória:

```python
# infra/fipe_cache.py
@dataclass
class _Entry:
    data: list[dict[str, str]]
    expira_em: float  # monotonic

_cache: dict[str, _Entry] = {}
TTL = 30 * 24 * 3600  # 30 dias
```

### 2. FRONTEND — componente FipeSelector

Crie `frontend/src/hooks/useFipe.ts`:
- `useFipeMarcas(tipo)` — carrega marcas ao montar
- `useFipeModelos(tipo, marcaId)` — carrega quando marcaId muda
- `useFipeAnos(tipo, marcaId, modeloId)` — carrega quando modeloId muda
- `useFipePreco(tipo, marcaId, modeloId, anoId)` — retorna codigo_fipe + valor

Crie `frontend/src/components/FipeSelector.tsx`:
- Selects em cascata: Marca → Modelo → Ano
- Ao selecionar Ano: exibe `codigo_fipe` (read-only) e `Valor FIPE` formatado em R$
- Loading state em cada select (disabled + spinner)
- Dark mode correto
- Props: `tipo: "carros" | "motos"`, `onChange(fipe: FipeResult)`

Atualize `CotacaoPage.tsx`:
- Step 2 Auto: substitui campos `marca`, `modelo`, `ano_fabricacao`, `ano_modelo` pelo `FipeSelector`
- Step 2 Moto: idem com `tipo="motos"`
- Adicionar campo `placa` (opcional, string livre, máscara ABC-1234 / ABC1D23)
- `codigo_fipe` e `valor_fipe` entram no `dados_risco` enviado ao backend
- Manter `cep_pernoite`, `finalidade`, `blindado`, `garagem` como estão

Atualize os schemas Zod (step2AutoSchema, step2MotoSchema):
- Adicionar `codigo_fipe: z.string().min(1)`
- Adicionar `placa: z.string().optional()`
- Remover `marca`, `modelo` como campos livres (viram read-only preenchidos pelo selector)

### 3. UX — diretrizes

- Select de Marca vem com input de busca/filtro (há ~60 marcas de carros)
- Selects dependentes ficam disabled até o anterior ser preenchido
- Valor FIPE exibido em destaque perto do selector: "Valor FIPE: R$ 48.000"
- Erro de API externa mostra mensagem amigável + opção de digitar manualmente
- Skeleton loader enquanto carrega, não spinner mudo

### 4. Schemas de dados

Após a FIPE, `dados_risco` de uma cotação auto terá:
```json
{
  "ramo": "auto",
  "codigo_fipe": "004090-4",
  "placa": "ABC1D23",
  "cep_pernoite": "13013001",
  "finalidade": "lazer",
  "blindado": false,
  "garagem": true,
  "cpf": "...",
  "nome": "...",
  "sexo": "M",
  "data_nascimento": "1990-01-15",
  "ano_modelo": 2023,
  "valor_fipe": "48000.00"
}
```

**PRONTO QUANDO:** usuário seleciona Marca → Modelo → Ano e o formulário
preenche `codigo_fipe` automaticamente. Cotação enviada ao backend inclui
`codigo_fipe` no `dados_risco`. `make check` continua passando.

**NÃO FAÇA:** autenticar o endpoint FIPE, criar tabela no banco para o cache
(memória é suficiente no MVP), mudar nada nos adapters de seguradora.

---

<!-- original prompts preservados abaixo -->

## FASE 0 — Setup local (referência)

Stack: Python 3.12 + FastAPI + Postgres 16 + React 18 + Vite + TypeScript + Tailwind + shadcn/ui.

**PRONTO QUANDO:** `docker compose up` sobe, `GET /health` responde 200, `make check` passa, `npm run dev` abre a SPA.

---

## FASE 1 — Fundação

Contexto: leia `docs/escopo.md`, seções 3 e 5.

Implemente, nesta ordem:

1. **AUTENTICAÇÃO** — Sem cadastro público, sem reset self-service, sem SSO. Admin provisiona usuários. Argon2id para senha. Sessão em cookie httponly + secure + samesite=strict. Rate limit no login: 5 tentativas / 15 min por usuário e por IP. Dependency `get_current_user()` no FastAPI. Papéis: corretor, admin.

2. **MODELO CANÔNICO** — Três camadas, Pydantic v2. `RiscoAuto` e `RiscoResidencia` agnósticos de seguradora. `Negocio` blob tipado por adapter. Ciclo: eventos imutáveis `CotacaoCriada`, `PropostaTransmitida`, `ApoliceEmitida`, `EndossoRegistrado`, `ParcelaGerada`, `ComissaoRegistrada`, `SinistroAberto`. TODO valor monetário é `Decimal`. `float` nunca toca dinheiro.

3. **TABELA DE DOMÍNIOS** — `dominio(cia, tipo, codigo, descricao, ativo, atualizado_em)`. Nenhum código de cobertura, profissão, estado civil ou plano de pagamento hardcoded.

4. **PortaSeguradora + ADAPTER FAKE** — Interface conforme `docs/escopo.md §2`. O fake retorna dados plausíveis e simula latência de 8–15 segundos. Deve conseguir retornar os três estados: sucesso, restrição, erro.

5. **LOGGING COM ALLOWLIST** — structlog configurado para logar APENAS campos explicitamente permitidos. Teste automatizado que falha se "cpf", "password", "client_secret", "access_token" aparecerem em qualquer sink.

6. **AUDITORIA** — Tabela append-only. Sem UPDATE, sem DELETE — garantido por permissão no Postgres. Registra: acesso a dado de cliente, revelação de PII, cotação, transmissão, login, falha de login, mudança de papel.

7. **RLS** — Policy no Postgres: corretor vê a própria carteira, admin vê tudo. Enforcement na camada de dados. Toda tabela de negócio tem `tenant_id NOT NULL`.

**PRONTO QUANDO:** login funciona, um corretor não enxerga carteira de outro (teste automatizado), fake adapter retorna cotação pela interface, nenhum CPF aparece em log algum.

**NÃO FAÇA:** telas além do login, adapter da Yelum, PDF, dashboard, qualquer chamada HTTP externa.

---

## FASE 2 — Cotação end-to-end

Contexto: `docs/escopo.md §6`, funil de cotação.

1. **ORQUESTRADOR** — Fan-out assíncrono sobre N adapters. Timeout por cia, resultado parcial exibido conforme chega, cancelamento pelo usuário. Fila em Postgres com SKIP LOCKED. Não use Celery nem Redis.

2. **CLIENTE E OBJETO** — Cadastro de cliente com busca por CPF via blind index (HMAC). Veículos e imóveis vinculados ao cliente, reutilizáveis entre cotações.

3. **FUNIL — 5 passos, Auto e Residência** — React Hook Form + Zod. Autosave a cada passo. Tab order correto, Enter avança. Campos de domínio populados da tabela `dominio`. `CommissionPct` visível apenas para admin.

4. **HISTÓRICO IMUTÁVEL** — Cotação nunca sofre UPDATE. Alteração gera nova versão com link para a anterior. Guarde `payloadOriginal` — request e response brutos do adapter, cifrados.

5. **RECOTAR** — A partir de cotação existente, pré-preenchida.

6. **TRÊS ESTADOS DE RESULTADO** — Sucesso, restrição e erro são estados distintos. Vistoria prévia aparece em destaque.

7. **ESTADO DE CARREGAMENTO** — "Consultando Yelum… 12s" com botão cancelar. Nunca spinner mudo.

**PRONTO QUANDO:** você cota Auto e Residência do início ao fim contra o fake, o histórico guarda tudo, recotar funciona, e fechar o browser no passo 3 não perde os passos 1 e 2.

**NÃO FAÇA:** comparativo visual, PDF, transmissão de proposta, dashboard, adapter real.

---

## FASE 3 — Comparativo, PDF, gestão

1. **COMPARATIVO** — Franquias lado a lado, coberturas com LMI, parcelamentos. Densidade acima de decoração.

2. **PDF PARA O CLIENTE** — Comparativo com logo da Klubi. Quando a Yelum liberar, use a API de Impressão dela para cotação, proposta, apólice, parcelas e carta verde. NÃO construa gerador para esses.

3. **TIMELINE DO CLIENTE** — `Cotação → proposta → apólice → endosso → parcela → renovação → sinistro` em ordem, numa tela.

4. **PROJEÇÕES DE GESTÃO** — Apólice, parcela e comissão como projeções sobre o stream de eventos. Comissão PREVISTA calculada. Campo separado para comissão RECEBIDA (vem do E-Retorno na Fase 7).

5. **RENOVAÇÃO** — Janela D-60 / D-45 / D-30 com responsável atribuído.

6. **TRANSMISSÃO DE PROPOSTA** — Implementada, disparada por humano com confirmação explícita.

**PRONTO QUANDO:** comparativo gera PDF, timeline mostra a vida de um cliente, parcelas e comissão prevista aparecem corretas, transmissão funciona contra o fake.

**NÃO FAÇA:** conciliação de comissão recebida, gestão de sinistro, dashboard.

---

## FASE 4 — Dashboard, relatórios, seed — DEMO

**Objetivo:** algo apresentável à diretoria. O critério não é funcionalidade, é PARECER REAL.

1. **HOME POR PAPEL** — Corretor: fila de trabalho (renovações na janela, propostas paradas, parcelas vencendo, cotações abandonadas há 2+ dias). Admin/gestor: KPIs com comissão PRODUZIDA × RECEBIDA lado a lado.

2. **RELATÓRIOS** — Produção por corretor, conversão, ticket médio, mix de carteira. Export CSV e XLSX.

3. **SEED SINTÉTICO** — 3 corretores, ~40 clientes, ~120 cotações, ~60 apólices. Região Campinas/Indaiatuba-SP. Nomes brasileiros plausíveis. CPF válido pelo algoritmo mas inexistente. ZERO PII real.

4. **MARCA D'ÁGUA DE DEMO** — Faixa discreta indicando dados simulados, visível em toda tela que mostra valor de prêmio.

5. **DESIGN** — Ferramenta densa e neutra. NÃO use: creme + serif + terracota; dark + verde ácido; broadsheet com fios finos. São defaults de IA.

**PRONTO QUANDO:** alguém de fora abre o sistema e não percebe que os dados são falsos até ler a marca d'água.

**Depois:** demo para a diretoria + e-mail ao ponto focal da Yelum com as 12 perguntas do `docs/escopo.md §10`.

---

## FASE 5 — Adapter Yelum real

**Gate: credencial de mock ou homologação.** Comece por Residência.

Contexto: leia `docs/escopo.md §4` inteiro antes de escrever qualquer código.

1. **AUTENTICAÇÃO** — Token é OPACO, não JWT. Cache em memória, `401` como expirado, reautentica e repete UMA vez. Os quatro segredos vêm do `SecretProvider`.

2. **ANTI-CORRUPTION LAYER** — Mapeia `RiscoResidencia → contrato Yelum` e `resposta → CotacaoCanonica`. Todo campo monetário vira `Decimal` na fronteira. Pydantic estrito: falhe alto em campo desconhecido ou faltante.

3. **ENDPOINTS** — `POST /offer/v1/quote`, `PUT /offer/v1/quote/{id}`, `POST /offer/v1/proposal`. Base URL por ambiente, do `SecretProvider`.

4. **RATE LIMIT E RESILIÊNCIA** — Circuit breaker, backoff exponencial. "Yelum fora" é estado normal.

5. **TESTES DE CONTRATO** — respx com os payloads EXATOS dos PDFs. Rodam sem rede.

6. **SINCRONIZAÇÃO DE DOMÍNIOS** — Job que popula a tabela `dominio` pela API de Domínios.

**PONTOS AMBÍGUOS — confirme com a Yelum antes de assumir:** `CBE10` duplo, `AgencyCode` vs `CooperativeAgencyCode`, `DepartmentCode`/`EmployeeName`.

**NÃO FAÇA:** transmissão automática, mudar nada fora de `adapters/yelum/`.

---

## FASE 6 — Paridade

**Gate: ≥99% de paridade exata em 200 cotações, sustentado 30 dias.**

1. **HARNESS DE RECONCILIAÇÃO** — Amostra diária. Tela para operador lançar valor do portal. Divergência > R$ 0,01 gera alerta com `payloadOriginal` anexado.

2. **DIAGNÓSTICO AUTOMÁTICO** — Decomposição por cobertura, diff campo a campo, bisseção automática.

3. **PAINEL DE DIVERGÊNCIA** — Taxa de paridade por dia, por produto, por faixa de prêmio.

**NÃO FAÇA:** liberar para corretor antes do gate. Automatizar transmissão antes do gate.

---

## FASE 7 — E-Retorno

**Gate: Security Assessment assinado.**

1. **INGESTÃO** — Job periódico. Cada movimento vira EVENTO — não UPDATE em projeção. Idempotência por identificador do movimento.

2. **CONCILIAÇÃO DE COMISSÃO** — Prevista vs recebida. Tela de exceções, não relatório passivo.

3. **SINISTRO READ-ONLY** — Exibição e alerta. Não construa gestão de sinistro.

---

## FASE 8 — Deploy GCP e endurecimento

**Precede a chave de produção.**

Cloud Run + Cloud SQL (IP privado) + Secret Manager (CMEK) + KMS + Artifact Registry. Região `southamerica-east1`. IP fixo de saída via VPC egress + Cloud NAT. PII com envelope encryption. Backup com restore testado. Pentest externo antes de dado real de cliente.

---

## FASE 9 — MCP para o bot

**Só depois do gate de paridade.**

Ferramentas: `buscar_cliente`, `criar_ou_atualizar_risco`, `cotar`, `consultar_status`, `consultar_apolice/parcela/sinistro`.

`CommissionPct` e `PromotionalDiscountVlr` NÃO são parâmetros de ferramenta. `transmitir()` NÃO é exposto. Toda cotação por MCP entra em fila de revisão.

---

## Ordem de execução

```
Hoje         Fase 0  ✅
Semana 1     Fase 1
Semana 2     Fase 2
Semana 3     Fase 3
Semana 4     Fase 4  →  DEMO  →  e-mail ao ponto focal Yelum
Em paralelo  Cadastro no portal do desenvolvedor da Porto
Quando       Fase 5 → 6 → 7 → 8 → 9
a chave
chegar
```

Fases 0–4 não dependem de ninguém. Comece hoje.
