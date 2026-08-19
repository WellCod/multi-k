# multi-K — Escopo

Multicálculo e gestão da Klubi. Substitui o documento anterior baseado em Porto Auto.

**Decisões fechadas:** Yelum primeiro (Porto na fase 2 de acoplamento) · Auto como produto, Residência como banco de provas · Python/FastAPI + React/Vite + Postgres · auth própria · local no MVP, GCP depois · Marketplace + E-Retorno no escopo · 2–5 corretores · carteira 70%+ auto.

---

## 1. O que mudou e por quê

| Antes | Agora | Motivo |
|---|---|---|
| Porto Auto primeiro | Yelum primeiro | Contrato em mãos; canal de acesso nomeado (ponto focal comercial) |
| Só Auto | Auto + Residência | Só com dois ramos dá pra saber o que é genérico. Residência tem contrato real hoje |
| Gestão fora do MVP | Gestão dentro | E-Retorno entrega comissão, parcela, emissão e sinistro por API |
| Conciliação fora | Conciliação dentro | Deixou de ser parse de arquivo |
| Clerk | Auth própria | Sem cadastro público, sem reset self-service → escopo pequeno |
| Cloud Run desde o início | Local no MVP | Sem PII enquanto for mock; infra vira problema só na homologação |
| Apólice mutável (default) | Evento imutável | E-Retorno entrega movimento, não estado |

---

## 2. Arquitetura

```
React SPA (Vite)          ← nunca vê credencial de seguradora
      │ cookie de sessão
FastAPI                   ← authN/authZ, auditoria, rate limit
      │
      ├── Domínio (evento)          ├── Orquestrador de cotação
      │                              │
      │                        PortaSeguradora  ← interface
      │                              │
      │                    ┌─────────┴─────────┐
      │                 Fake              Yelum
      │                                        │
Postgres                              integracao[-tst].grupohdiseguros.com.br
```

**Regra dura:** nenhum tipo, campo ou código da Yelum atravessa `PortaSeguradora`. Teste de arquitetura no CI: `grep -ri "yelum\|BrokerProposalNumber\|CoverageCode" src/` fora de `adapters/yelum/` falha o build.

```python
class PortaSeguradora(Protocol):
    def capacidades(self) -> Capacidades: ...
    async def cotar(self, r: RiscoCanonico) -> ResultadoCotacao: ...
    async def recotar(self, id: str, r: RiscoCanonico) -> ResultadoCotacao: ...
    async def transmitir(self, p: PropostaCanonica) -> ResultadoTransmissao: ...
    async def movimentos(self, desde: date) -> list[MovimentoCanonico]: ...
```

`capacidades()` responde quais ramos, coberturas, franquias e parcelamentos existem. É o que impede `if cia == "yelum"` na UI e o que faz a segunda cia custar semanas em vez de meses.

---

## 3. Modelo — três camadas

O erro a evitar é canonizar tudo. Só a camada `Ciclo` é universal.

### `Risco` — canônico por ramo, agnóstico de cia

**Auto:** veículo (FIPE, ano, placa, chassi, combustível, blindagem, alienação), uso (CEP pernoite, garagem, km/mês, finalidade), condutores (principal + demais, faixa etária, relação), histórico (bônus, cia anterior, sinistros), coberturas desejadas.

**Residência:** imóvel (tipo, construção, ocupação, atividade profissional), local de risco, proteções (alarme, cerca, grades), coberturas com LMI prédio/conteúdo.

**Comum:** proponente (CPF/CNPJ, nascimento, sexo, estado civil, profissão, renda), vigência, renovação.

### `Negocio` — específico da cia, deliberadamente NÃO canônico

Da Yelum: `BrokerCode`, `BrokerBranchCode`, `InternalBranchCode`, `CommissionParticipation[]`, `SalesPartnerCode`, `Dealer`, `Affinity`, `EmployeeData`, `Seller`, `CommissionPct`, `PromotionalDiscountVlr`.

A Porto terá equivalentes com outros nomes e campos que a Yelum não tem. **Blob tipado por adapter.** Teste: se um campo só faz sentido para uma cia, não é canônico.

### `Ciclo` — o canônico de verdade

`Cotacao → Proposta → Apolice → Endosso → Parcela → Comissao → Sinistro`

Idêntico entre ramos e entre cias. Modelado como **eventos imutáveis**; apólice e parcela são projeções.

### Domínios

`dominio(cia, tipo, codigo, descricao, ativo, atualizado_em)`

Tudo que a Yelum chama de "tabela de domínios" mora aqui: `QuestionNumber`, `AnswerChoiceCode`, `StreetType`, `OccupationCode`, `MaritalStatus`, `PropertyType`, `ConstructionType`, `CoverageCode`, `PaymentPlanCode`. Populado com valores plausíveis agora, sincronizado pela API quando a credencial sair. **Zero código muda.**

---

## 4. Contrato Yelum — o que já sabemos

### Auth

```
POST https://integracao-tst.grupohdiseguros.com.br/controledeacesso/token?grant_type=client_credentials
Content-Type: application/x-www-form-urlencoded
client_id, client_secret, username, password
→ { "access_token": "..." }
```

Quatro segredos. `username`/`password` são o login do Meu Espaço Corretor. Diz `client_credentials` mas é password grant.

**Token é opaco (~28 chars), não JWT.** Não dá pra ler expiração. Design: cache em memória do processo, trata `401` como expirado, reautentica e repete **uma vez**. Nunca em Redis, nunca em disco.

Aberto: `expires_in` vem no response? "Certificação digital" na seção de segurança significa mTLS?

### Endpoints (Residência confirmado)

| Operação | Método | Path |
|---|---|---|
| Cotar | POST | `/offer/v1/quote` |
| Recotar | PUT | `/offer/v1/quote/{BrokerProposalNumber}` |
| Propor | POST | `/offer/v1/proposal` |

Ambientes: mock `integracao-tst.../offer/property/sandbox/v1/`, homologação `integracao-tst.../offer/v1/`, produção `integracao.../offer/v1/`.

Produtos: `11030` Residência, `11043` Affinity Residência. Auto: desconhecido.

### Armadilhas confirmadas

| Item | Detalhe |
|---|---|
| Tipo de dinheiro | `TotalPremiumValue` é número no topo, string em `Installments`. **Decimal em tudo, float nunca** |
| Booleanos | `"T"/"F"` string, exceto `NeedInspectionRisk` que é boolean real |
| Chave de erro | Sucesso usa `Success`, erro usa `Sucesso`. Aceita as duas |
| `Coverages` duplo | `CBE10` aparece em `Residence[].Coverages` e no `Coverages[]` irmão com valores diferentes. **Ambíguo — perguntar** |
| `AgencyCode` | Exemplo 11030 usa `AgencyCode`, tabela e 11043 usam `CooperativeAgencyCode`. Um deles com espaços dentro das aspas |
| `EmployeeData` | `DepartmentCode` no exemplo e não na tabela; `EmployeeName` na tabela e não no exemplo |
| Regra geral | **Confia no exemplo, não na tabela** |

### Não-funcionais

500 req/min por IP, 300 transações/min, `429` se exceder. SLA 85%/dia — **Yelum fora do ar é estado normal, não exceção.** p95 até 1500ms para APIs de canal.

Changelog mostra mudanças a cada poucos meses. Versão do doc versionada no repo.

### Terceiro estado de retorno

Cotação não é sucesso/erro binário. Retorna com `Restricao[]` e `MensagemInformativa[]`, e `NeedInspectionRisk` muda o fluxo de venda. O canônico precisa disso ou a tela mente pro corretor.

---

## 5. Segurança

Prioridade estrutural: **o Security Assessment assinado é pré-requisito para liberar o E-Retorno.** Não é precaução, é desbloqueio comercial.

### Ativo crítico: credenciais Yelum

Quatro segredos, e dois deles são o login humano do portal. Vazou = terceiro operando como a Klubi.

- **Pede um usuário de portal dedicado à integração**, separado do login pessoal de qualquer corretor
- Local (mock): `.env` no `.gitignore` é aceitável **enquanto não houver credencial real**
- **No dia que a chave de homologação chegar:** Secret Manager ou equivalente, `.env` deixa de servir. `SecretProvider` como interface desde o dia 1 para a troca ser uma classe
- Chave do portal expira `never` — rotação é 100% sua
- Collection do Postman contém senha de homologação. `.gitignore` **antes** de baixar

### PII

- Envelope encryption em CPF/CNPJ/chassi/placa, chave no KMS
- Busca por CPF via blind index (HMAC + coluna indexada)
- Exibição mascarada por padrão; revelar é ação logada
- Prazo: antes da primeira cotação com dado real. Enquanto for mock, não há PII

### Log — onde o vazamento acontece

**Allowlist, não denylist.** Campo novo não é logado por default. Zero PII em log, APM, error tracker, URL ou query string. Correlation ID em tudo.

### Auth

Sem cadastro público, sem reset self-service, sem SSO. Argon2id + cookie `httponly`/`secure`/`samesite=strict` + rate limit no login. `get_current_user()` isola tudo — o resto do sistema nunca sabe de onde veio a identidade. `user_id` é UUID interno.

### RBAC

Dois papéis no MVP: `corretor` (própria carteira) e `admin` (tudo). Enforcement em RLS, não no controller. Com 2–5 pessoas o escopo é accountability, não sigilo — mas o mecanismo fica pronto.

### Auditoria

Append-only, sem UPDATE nem DELETE: acesso a dado de cliente, revelação de PII, cotação, transmissão, login, mudança de papel.

### LGPD

Base legal: execução de contrato (cliente), legítimo interesse (prospect, com teste de balanceamento documentado). **A Yelum consulta Boa Vista com o CPF enviado** — isso entra no ROPA e no aviso de privacidade. WhatsApp entra como operador. Retenção: cotação não convertida 24 meses, apólice 5 anos após vigência.

### Confidencialidade

Os PDFs da Yelum têm cláusula explícita de não-reprodução. Não vão para repositório público, issue tracker aberto nem Slack compartilhado.

---

## 6. UX

### Brief

Ferramenta de trabalho para 2–5 corretores que a usam 30×/dia. **Densidade e velocidade, não impressão.** Otimiza para repetição: tab order correto, Enter avança, autosave por passo, recotar a partir de cotação anterior.

Deliberadamente **não** é: cream + serif + terracota, nem dark + acid green, nem broadsheet com hairlines. Esses são defaults de IA e leem como template. A direção aqui é **ferramenta densa e neutra** — tipografia utilitária, hierarquia por peso e espaço, cor só onde carrega informação (status, alerta, divergência). Uma decisão de cor com significado vale mais que uma paleta bonita.

### Copy

Nomeia pelo que a pessoa controla, não pelo sistema. Voz ativa, sentence case. Botão que diz "Transmitir" gera toast "Transmitida". Erro diz o que aconteceu e o que fazer: "Veículo com restrição de aceitação para o perfil informado" — nunca `HTTP 422`. Tela vazia é convite para agir.

### Funil de cotação

```
[1] Identificação   CPF → cliente existente ou novo
[2] Objeto          Auto: placa → FIPE · Residência: CEP → local de risco
[3] Perfil          Condutores/uso · Imóvel/proteções
[4] Coberturas      Defaults pré-marcados. Ajuste opcional
[5] Resultado       Franquias, parcelamentos, restrições, vistoria prévia
                    → PDF · WhatsApp · Salvar · (Transmitir = humano)
```

**Carregamento honesto:** "Consultando Yelum… 12s" com cancelar. Spinner mudo destrói confiança.

### Home por papel

Gestor vê KPIs. Corretor vê fila de trabalho: renovações na janela atribuídas a mim, propostas paradas, parcelas vencendo, cotações abandonadas há 2+ dias. KPI é consequência, tarefa é o que abre o dia.

### Dashboard

KPIs: segurados vigentes, apólices vigentes, cotações em andamento, renovações efetivadas, prêmio líquido, **comissão produzida × recebida** (a lacuna entre os dois é a conciliação, e deixá-la visível é o que faz alguém agir). Período 15/30/90/custom. Corte por ramo e por seguradora. Barra horizontal ordenada em vez de donut.

---

## 7. MVP

**Dentro:** auth, RBAC, cotação Auto + Residência, comparativo, PDF, cliente/veículo, histórico imutável, gestão (apólice/parcela/renovação), comissão e conciliação, sinistro read-only, dashboard, relatórios, auditoria.

**Fora:** multi-tenant (só a coluna `tenant_id`), transmissão automática, MCP/bot, outras cias, gestão de sinistro, app nativo.

**Transmissão de proposta:** implementada, disparada por humano. Automatizar só depois do gate de paridade.

### Critério de sucesso

**≥99% de paridade exata em 200 cotações, sustentado por 30 dias sem intervenção.** Nada mais. 95% parece bom e destrói a confiança do corretor em duas semanas.

---

## 8. Fases

| # | Fase | Duração | Gate |
|---|---|---|---|
| 0 | Setup local | 1 dia | — |
| 1 | Fundação + adapter fake | 1 sem | — |
| 2 | Cotação end-to-end | 1 sem | — |
| 3 | Comparativo, PDF, gestão | 1 sem | — |
| 4 | Dashboard, relatórios, seed | 1 sem | **→ demo diretoria** |
| 5 | Adapter Yelum real | 3–5 sem | chave homologação (NDA) |
| 6 | Paridade | 4–8 sem | **≥99% em 200** |
| 7 | E-Retorno | 4–6 sem | Security Assessment |
| 8 | Deploy GCP + endurecimento | 3–4 sem | precede chave produção |
| 9 | MCP para o bot | 2–3 sem | após paridade |

**Demo em 4 semanas. Produção com corretor usando: 6–9 meses**, dominado por NDA, validação EH e Security Assessment — nenhum deles acelera com dev.

---

## 9. Riscos

| Risco | Mitigação |
|---|---|
| Chave Yelum não sai | Fases 1–4 não dependem. Pedir mock e homologação em paralelo |
| Canal Parcerias ≠ canal corretora | Perguntar explicitamente. Se for, Porto vira plano A |
| Doc de Auto não chega | Residência valida o encanamento; Auto herda estrutura |
| Paridade < 99% | Gate da Fase 6. Kill criterion |
| Canônico em formato Yelum | Dois ramos desde o início |
| Vazamento de credencial | §5. Usuário dedicado, Secret Manager na homologação |
| Rate limit / allowlist por IP | Rodando local, o IP é o do escritório. Perguntar se produção exige allowlist |

### Kill criteria

- 3 meses sem credencial → mata
- Paridade não bate 99% em 2 meses de tentativa → mata
- Custo acumulado > 2× licença de 5 anos → reavalia

---

## 10. Pedido consolidado ao ponto focal Yelum

1. Descrição da companhia, objetivo e modelo de negócio (o que o PDF pede)
2. **Credencial de mock sai antes do NDA?**
3. Documentação de **Auto** (Quote e Proposal) — prioridade máxima
4. Documentação de **Domínios**, **E-Retorno**, **Impressão**
5. Collection completa do Postman
6. Corretora com código ativo consome Marketplace e E-Retorno, ou exige contrato de parceria de outro tipo?
7. Usuário de portal dedicado à integração, separado do login pessoal?
8. "Certificação digital" = mTLS? Em quais ambientes?
9. Produção exige allowlist de IP?
10. `expires_in` no response do token? TTL?
11. `Success` vs `Sucesso` — qual a chave correta no erro?
12. `CBE10` nos dois níveis de `Coverages` — qual vale pro cálculo?
