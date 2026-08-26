# multi-K — Architecture Decision Records

Registro das decisões tomadas e do raciocínio por trás delas.

**Para o agente de IA que lê isto:** estas decisões foram tomadas com contexto que não está no código. Várias delas parecem erradas ou incompletas quando olhadas isoladamente — e é exatamente por isso que estão documentadas. Cada ADR tem uma seção **"Sinal de violação"** descrevendo o que um agente prestativo tende a fazer para "melhorar" a decisão. Se você está prestes a fazer alguma dessas coisas, **pare e pergunte** em vez de corrigir.

Status possíveis: `Aceita` · `Aceita (decisão do dono)` — tomada pelo dono do produto contra recomendação técnica, registrada com o tradeoff · `Provisória` — depende de informação que ainda não temos.

**Por que arquivo único:** com 1 dev e uso principal sendo colar como contexto para IA, um arquivo vence. Se o time crescer ou o número de ADRs justificar, quebra em `docs/adr/NNNN-*.md` depois.

---

# Produto e escopo

## ADR-001 — Construir em vez de comprar

**Status:** Aceita (decisão do dono)

**Contexto.** Existem plataformas prontas (TEx/Teleport, Segfy, Quiver) que resolvem multicálculo e gestão por ~R$ 125/assento/mês. Para 5 corretores, ~R$ 7,5k/ano contra 9–14 meses de desenvolvimento mais 0,5–1 FTE de manutenção permanente. A recomendação técnica foi comprar: cotação não é diferencial competitivo de corretora, e construir significa manter paridade de prêmio contra alvos móveis para sempre.

**Decisão.** Construir.

**Consequências.** A esteira de integrações é custo permanente, não projeto. Cada cia nova traz homologação, contrato e paridade próprios. O custo marginal da terceira e quarta cia é humano, não computacional.

**Quando a decisão vira claramente certa.** Se o multi-K for exposto a terceiros — white-label para outras corretoras, seguro embarcado em funil de parceiro, MGA. Aí licenciamento por assento quebra e a dependência vira barreira de entrada a favor.

**Reavaliar.** A cada cia adicionada.

---

## ADR-002 — Yelum primeiro, Porto depois

**Status:** Aceita · substitui a posição inicial (Porto Auto primeiro)

**Contexto.** O pedido original era Porto Auto. Mas o acesso à Porto é opaco — só aceitam parceiros previamente indicados pelas áreas de produto, e não há como ler o catálogo sem aprovação. A Yelum tem documentação técnica em mãos, canal de acesso nomeado (ponto focal comercial, que a Klubi já tem como corretora com código ativo) e o E-Retorno cobre metade do MVP.

**Decisão.** Yelum é a primeira integração. Porto entra na fase de acoplamento.

**Consequências.** Um multicálculo só com Yelum tem valor limitado para os corretores — a Porto pesa mais no mercado auto. Isso não muda a ordem de construção, muda a expectativa de adoção: não prometer uso real antes da segunda cia.

**Risco aberto.** A documentação é da "Squad Parcerias" e valida revenda, affinity, cooperativa e agência. Pode ser canal de parceria, não de corretora. Se for, Porto vira plano A.

---

## ADR-003 — Auto como produto, Residência como banco de provas

**Status:** Aceita

**Contexto.** A carteira é 70%+ auto, então Auto é o produto. Mas só temos contrato de Residência hoje. E há um problema estrutural: com um ramo só, é impossível saber o que no modelo é conceito de seguro e o que é peculiaridade daquele ramo — tudo parece genérico.

**Decisão.** Implementar os dois. Auto é o produto (funil, telas, demo). Residência valida o encanamento com contrato real.

**Consequências.** Custo adicional ~1 semana de formulário e telas. Se apertar, corta a UI de Residência e mantém só os testes de contrato — aí o custo é quase zero e a validação permanece.

**Alternativa descartada.** Auto sozinho: sem documentação de Auto, o adapter seria inventado e estaria errado em detalhes que só apareceriam quando a doc chegasse.

---

## ADR-004 — Gestão, comissão e sinistro dentro do MVP

**Status:** Aceita · substitui a posição inicial (gestão fora, conciliação como escopo próprio)

**Contexto.** A avaliação inicial assumia que dado de apólice, parcela e comissão viria por parse de arquivo com layout próprio por cia — caro e recorrente. A documentação da Yelum mostra o **E-Retorno**, que entrega comissão gerada, emissões, parcelas, andamento de pagamento e sinistros por API.

**Decisão.** Gestão, conciliação de comissão e sinistro read-only entram no MVP.

**Consequências.** Requer Security Assessment assinado (a Yelum exige para liberar E-Retorno). Isso converte segurança de precaução em pré-requisito de desbloqueio comercial.

**Fora do escopo.** Gestão de sinistro — perícia, documentação, regulação e indenização rodam na seguradora.

---

## ADR-005 — Nome: multi-K

**Status:** Aceita

Klubi → multi-K. Curto, carrega a marca sem explicação. "Multi-Kalculo" descartado: a troca de C por K em nome longo lê como marca de 2010, e o produto já está indo além de cotação (gestão, comissão, sinistro) — "Kalculo" ficaria pequeno.

---

# Domínio

## ADR-006 — Ciclo modelado como eventos imutáveis

**Status:** Aceita

**Contexto.** A escolha era entre apólice mutável (endosso faz UPDATE) e endosso como evento imutável com apólice sendo projeção. O E-Retorno da Yelum decidiu: ele retorna **movimentações** — emissões, endossos, parcelas, comissões, sinistros. A seguradora pensa em movimento, não em estado.

**Decisão.** `Cotacao → Proposta → Apolice → Endosso → Parcela → Comissao → Sinistro` como eventos imutáveis. Apólice e parcela são projeções.

**Por quê.** Com modelo mutável, você passa a vida traduzindo o stream deles para UPDATEs seus e perde "o que mudou e quando" — que é exatamente o que a conciliação de comissão precisa para achar endosso que alterou prêmio retroativamente.

**Sinal de violação.** Fazer `UPDATE` numa apólice ou parcela. Ingerir movimento do E-Retorno como mutação em vez de evento novo. Criar tabela `apolice` como fonte da verdade em vez de projeção.

---

## ADR-007 — Três camadas, e a camada `Negocio` NÃO é canônica

**Status:** Aceita

**Decisão.**
- `Risco` — canônico **por ramo**, agnóstico de cia
- `Negocio` — específico da cia, **deliberadamente não unificado**
- `Ciclo` — o único canônico universal

**Por quê.** A Yelum tem `BrokerCode`, `InternalBranchCode`, `SalesPartnerCode`, `Dealer`, `Affinity`, `EmployeeData`, `CooperativeCode`. A Porto terá outros nomes e campos que a Yelum não tem. Um modelo canônico que tenta cobrir os dois vira 40 campos opcionais que ninguém sabe preencher.

**Teste.** Se um campo só faz sentido para uma cia, não é canônico. Vai para o blob do adapter.

**Sinal de violação.** Criar `DadosComerciais` genérico com campos de duas cias. Adicionar campo opcional ao canônico "porque a Yelum precisa". Se você precisou mudar o domínio para acomodar uma cia, a camada anticorrupção está furada — isso é bug de arquitetura, não ajuste.

---

## ADR-008 — `PortaSeguradora` com teste de arquitetura no CI

**Status:** Aceita

**Decisão.** Uma interface, um adapter por cia. Nenhum tipo, campo ou código de seguradora atravessa a fronteira. CI falha se `yelum`, `BrokerProposalNumber`, `CoverageCode` ou `CommercialProductCode` aparecerem fora de `adapters/yelum/`.

**Por quê.** Sem enforcement mecânico, o vazamento acontece gradualmente e ninguém percebe até a segunda cia, quando o custo já é reescrita.

**Sinal de violação.** Importar de `adapters/yelum` fora do próprio adapter. Adicionar exceção ao teste de arquitetura "só desta vez".

---

## ADR-009 — `capacidades()` desde o dia 1, com uma cia só

**Status:** Aceita

**Contexto.** Parece over-engineering: uma cia, um ramo relevante, e já existe um método perguntando ao adapter o que ele suporta.

**Decisão.** Existe desde o início. A UI pergunta quais ramos, coberturas, franquias e parcelamentos existem, e renderiza.

**Por quê.** É o que evita `if cia == "yelum"` espalhado pelas telas. Sem isso, a segunda seguradora vira reescrita de frontend, não adição de adapter. E já se paga com Auto + Residência na mesma cia.

**Sinal de violação.** Qualquer condicional por nome de cia na UI. Lista de coberturas hardcoded no componente.

---

## ADR-010 — Domínios são dado, não código

**Status:** Aceita

**Decisão.** Tabela `dominio(cia, tipo, codigo, descricao, ativo, atualizado_em)`. `QuestionNumber`, `AnswerChoiceCode`, `StreetType`, `OccupationCode`, `MaritalStatus`, `PropertyType`, `ConstructionType`, `CoverageCode`, `PaymentPlanCode` — tudo mora ali.

**Por quê.** Duplo: (1) a API de Domínios da Yelum exige credencial que ainda não temos, então valores plausíveis populam a tabela agora e são substituídos por sync depois **sem uma linha de código mudar**; (2) quando a Yelum renomear uma cobertura, é `UPDATE`, não deploy.

**Sinal de violação.** `Enum` em Python ou TypeScript com códigos de cobertura. Constante com lista de profissões. `match` sobre `PaymentPlanCode`.

---

## ADR-011 — `payloadOriginal` é obrigatório

**Status:** Aceita

**Decisão.** Request e response brutos do adapter, cifrados, retidos 5 anos, em toda cotação.

**Por quê.** Duas razões independentes, cada uma suficiente:
1. Quando o corretor disser "o valor não bateu com o portal", é a única prova de qual dado foi enviado. Sem ele, toda divergência vira discussão sem árbitro.
2. A API de Proposta da Yelum **reenvia o contrato inteiro da cotação** mais o bloco `ProposalData`. Sem o payload guardado, você não consegue transmitir.

**Sinal de violação.** Guardar só os campos "úteis". Descartar o response depois de mapear. Sugerir remoção por economia de espaço — o volume é dezenas de MB/ano.

---

## ADR-012 — `Decimal` em todo valor monetário

**Status:** Aceita

**Contexto.** O contrato da Yelum é inconsistente: `TotalPremiumValue` é número no nível do `QuoteResidence` e string dentro de `Installments`, no mesmo response.

**Decisão.** Tudo vira `Decimal` na fronteira do adapter. `float` nunca toca dinheiro, em lugar nenhum.

**Por quê.** O critério de sucesso do sistema é paridade **exata** com o portal. Divergência > R$ 0,01 gera alerta. `float` introduz erro de arredondamento que torna esse critério impossível de atingir.

**Sinal de violação.** `float(valor)`. Aritmética de prêmio em JS sem biblioteca decimal. Serializar `Decimal` como número em JSON — mande string.

---

## ADR-013 — Três estados de retorno, não dois

**Status:** Aceita

**Contexto.** A documentação da Yelum descreve que, em caso de restrição, o sistema retorna mensagens informativas e restritivas **no response do cálculo**. Ou seja: cotou, mas com ressalvas. Há também `NeedInspectionRisk`, que muda o fluxo de venda.

**Decisão.** `Sucesso` · `Restricao` · `Erro` são estados distintos no canônico. Vistoria prévia aparece em destaque na UI.

**Por quê.** Modelar como sucesso/erro binário faz a tela mentir para o corretor — ele promete prazo ao cliente sem saber que há vistoria.

**Sinal de violação.** `if response.ok:` como único ramo. Tratar restrição como exceção.

---

# Stack

## ADR-014 — Monorepo, sem ferramenta de monorepo

**Status:** Aceita

**Decisão.** `backend/` e `frontend/` no mesmo repo. Sem Nx, Turborepo ou Lerna. Um `Makefile`.

**Por quê.** Tipos TS gerados do OpenAPI do FastAPI: com dois repos, mudar um campo vira commit + publicar pacote + bump + commit. Com um, é um commit e o CI valida os dois lados. Durante as 4 semanas iniciais o contrato muda toda semana.

**Não confundir.** Monorepo não implica deploy acoplado — Cloud Run recebe dois serviços com Dockerfiles separados. Eixos diferentes.

**Ferramenta descartada.** Existe para dezenas de pacotes com dependências cruzadas. Aqui são dois diretórios.

---

## ADR-015 — Vite, não Next.js

**Status:** Aceita

**Contexto.** Next é o default da comunidade — isso é convenção, não restrição.

**Decisão.** Vite + React + TypeScript.

**Por quê.** O backend é Python. Com Next: `browser → Next (Node) → FastAPI → Yelum`. Dois servidores, duas linguagens, dois deploys, dois lugares onde segredo pode vazar. As vantagens reais do Next (Server Components, route handlers como BFF) existem para quem não tem backend próprio. E SEO em ferramenta atrás de login vale zero.

**Quando inverter.** Se expuser cotação a cliente final em página pública. E aí a resposta não é migrar — é um app Next separado consumindo a mesma FastAPI.

---

## ADR-016 — FastAPI, não Django

**Status:** Aceita

Domínio é evento, trabalho é I/O externo. ORM e admin do Django atrapalham no primeiro; async e Pydantic v2 ajudam no segundo. Pydantic não é detalhe de framework aqui — o `RiscoCanonico` **é** um modelo Pydantic, e a fronteira do adapter é um `Protocol`. O modelo canônico vira código executável em vez de documento que envelhece. Flask descartado: você reconstruiria validação e async.

---

## ADR-017 — Fila em Postgres com `SKIP LOCKED`

**Status:** Aceita

**Decisão.** Sem Celery, sem Redis.

**Por quê.** 5 corretores × 30 cotações/dia = ~150/dia. Adicionar broker é mais um serviço para 1 dev operar, resolvendo um problema de escala que não existe. Postgres com `SKIP LOCKED` faz fila com transação e sem infraestrutura nova.

**Sinal de violação.** Adicionar Redis "porque é o padrão". Kafka. Qualquer broker sem um problema medido que o justifique.

---

## ADR-018 — Auth própria, não Clerk

**Status:** Aceita (decisão do dono) · substitui a posição inicial (Clerk)

**Contexto.** A recomendação inicial era não implementar auth próprio. Mas o escopo real é menor do que auth genérica: sem cadastro público, sem reset self-service, sem SSO — o admin provisiona. Isso remove justamente as partes perigosas.

**Decisão.** Argon2id + cookie `httponly`/`secure`/`samesite=strict` + rate limit no login.

**A parte que importa é a costura.** `get_current_user()` isola tudo; o resto do sistema nunca sabe de onde veio a identidade; `user_id` é UUID interno nosso, nunca ID de provedor externo. Trocar por Clerk depois é reescrever uma função.

**Sinal de violação.** ID de provedor externo vazando para o domínio. Lógica de autorização dentro do provedor de identidade em vez de RLS.

---

## ADR-019 — Local no MVP, GCP depois

**Status:** Aceita

**Decisão.** Docker Compose local. Cloud Run, Cloud SQL, VPC-SC e Secret Manager só na Fase 8.

**Por quê.** Enquanto o sistema roda 100% contra o adapter fake, **não existe PII nem segredo real**. O endurecimento pesado tem prazo definido: o dia em que a credencial de homologação chegar — não antes.

**O que ainda vale desde o dia 1** (barato agora, caro de retrofitar): logger com allowlist, `SecretProvider` como interface, padrão de RLS, auditoria append-only.

**Efeito colateral útil.** Rodando local, o IP visto pela Yelum é o do escritório — IP estável para informar se a homologação exigir allowlist. É por isso que a Fase 8 traz Cloud NAT com IP reservado: Cloud Run sai por IP efêmero e quebraria isso silenciosamente.

---

## ADR-020 — Nenhuma otimização preventiva

**Status:** Aceita

**Contexto.** O sistema é limitado pela Yelum, não por CPU nem por banco. A API deles declara p95 de até 1500ms e SLA de 85%/dia. Otimizar Python ganha milissegundos num caminho que gasta segundos esperando.

**Decisão.** Sem cache antes de medir, sem réplica de leitura, sem particionamento, sem microserviço.

**A única defesa preventiva aceita:** projeção materializada atualizada na entrada do evento, não no `SELECT` da tela. Custa nada agora e evita a única query pesada que o sistema teria.

**Onde performance aparece de verdade:** na percepção. Resultado parcial, tempo decorrido visível, botão cancelar. É por isso que o fake simula 8–15s — força a UI certa enquanto é barato mudar.

---

# Segurança

## ADR-021 — Log por allowlist, não denylist

**Status:** Aceita

**Decisão.** O logger estruturado emite **apenas** campos explicitamente permitidos. Campo novo não é logado por default. Teste que falha se `cpf`, `password`, `client_secret` ou `access_token` aparecerem em qualquer sink.

**Por quê.** Vazamento de PII raramente é invasão. É `console.log(req.body)` esquecido num deploy de sexta. Denylist falha no dia em que alguém adiciona `nomeMae` e ninguém lembra de bloquear.

**Sinal de violação.** Logar objeto inteiro. Adicionar campo à lista de bloqueio em vez de à de permissão. PII em URL ou query string — vaza para access log, histórico e header `Referer`.

---

## ADR-022 — Credenciais da Yelum: quatro segredos, dois são login humano

**Status:** Aceita

**Contexto.** O fluxo de token manda `client_id`, `client_secret`, `username` e `password` — e a documentação diz que usuário e senha de produção são **os mesmos do portal do corretor**. Diz `grant_type=client_credentials` mas é password grant.

**Decisão.**
- Pedir usuário de portal **dedicado à integração**, separado do login pessoal de qualquer corretor
- Todos os quatro vêm do `SecretProvider`
- `.env` local é aceitável **apenas enquanto não houver credencial real**; no dia que a chave de homologação chegar, provider definitivo
- Token é **opaco (~28 chars), não JWT** — não dá para ler expiração. Cache em memória do processo, `401` como sinal de expirado, reautentica e repete uma vez. Nunca em Redis, nunca em disco
- Rotação é 100% nossa: a chave do portal expira `never`

**Por quê o risco é maior que o normal.** Vazamento não dá acesso a uma API com escopo — dá acesso ao portal inteiro, com tudo que um corretor pode fazer lá, em nome da Klubi.

**Sinal de violação.** Decodificar o token para ler `exp`. Cachear em store compartilhado. `os.environ` direto. Credencial no banco.

---

## ADR-023 — RLS na camada de dados, não no controller

**Status:** Aceita

**Decisão.** Policy no Postgres: corretor vê a própria carteira, admin vê tudo. Dois papéis no MVP.

**Por quê.** "Corretor vê a própria carteira" precisa ser impossível de esquecer, não algo que se lembra de checar em cada endpoint novo. Com 2–5 pessoas o objetivo é accountability e trilha, não sigilo — mas o mecanismo fica pronto para quando não for.

**Sinal de violação.** `WHERE corretor_id = ?` no controller como única proteção. Endpoint novo sem escopo obrigatório na assinatura do repositório.

---

## ADR-024 — `tenant_id` sim, máquina multi-tenant não

**Status:** Aceita

Coluna `tenant_id NOT NULL` com valor fixo único em toda tabela de negócio, desde o início. Gestão de tenants, config por tenant e onboarding ficam fora.

**Por quê.** A coluna custa quase nada agora; adicioná-la depois em 30 tabelas, índices, queries e policies de RLS é semanas com dado em produção. A máquina, sem um segundo tenant, é desperdício.

---

## ADR-025 — Confidencialidade da documentação

**Status:** Aceita

Os PDFs da Yelum têm cláusula explícita de não-reprodução, e a collection do Postman contém usuário e senha de homologação. `.gitignore` inclui `docs/yelum/`, `*.pdf` e `*.postman_collection.json` **antes do primeiro `git add`**. Não vão para repositório público, issue tracker aberto nem Slack compartilhado.

---

# Processo e gates

## ADR-026 — Gate de paridade antes de liberar para corretor

**Status:** Aceita

**Decisão.** ≥99% de paridade exata em 200 cotações, sustentado 30 dias sem intervenção manual. Abaixo disso não sobe.

**Por quê.** Se o valor exibido não bate com o portal, o corretor volta ao portal e todo o resto foi desperdício. Não é métrica de qualidade — é o requisito funcional principal. 95% parece bom e destrói a confiança em duas semanas; reconquistar é mais caro que construir.

**Consequência.** O harness de reconciliação se constrói junto com a primeira cotação, não depois.

---

## ADR-027 — Transmissão de proposta permanece humana no MVP

**Status:** Aceita

**Contexto.** O dono decidiu que o bot de WhatsApp fará cotação automática, e que tratará as questões legais e de precisão depois. Registrado.

**Decisão.** Ainda assim, **transmitir** não é automático no MVP.

**Por quê.** Cotar é reversível. Transmitir é ato jurídico em nome da corretora. E o gate de paridade (ADR-026) ainda não passou — transmitir com prêmio divergente não é bug de tela, é proposta errada assinada pela Klubi.

**Revisitar.** Depois do gate.

---

## ADR-028 — MCP não expõe comissão nem desconto ao modelo

**Status:** Aceita

**Decisão.** `CommissionPct` e `PromotionalDiscountVlr` não são parâmetros de ferramenta MCP. Ficam fixos por configuração. `transmitir()` não é exposto.

**Por quê.** `CommissionPct` é **entrada** da cotação no contrato da Yelum, não consequência — entra no cálculo do prêmio. Um LLM com acesso a esse campo altera a receita da corretora ou o prêmio do cliente, e a falha seria silenciosa.

**Também.** Toda cotação originada por MCP é marcada como tal e entra em fila de revisão. Campos de risco alto (uso comercial, condutor 18–25, garagem) marcados com confirmação explícita registrada.

---

## ADR-029 — Não construir o que a seguradora já entrega

**Status:** Aceita

A Yelum expõe API de Impressão para cotação, proposta, apólice, parcelas e carta verde. Não construir gerador de PDF para esses.

**Construímos apenas o comparativo**, que é o único artefato que não existe no portal da seguradora — e é onde o produto justifica existir.

**Sinal de violação.** Implementar template de apólice. Recriar carnê de parcelas.

---

## ADR-030 — UI própria, não cópia de Segfy ou Teleport

**Status:** Aceita

**Contexto.** O pedido era usar as duas como base de interface.

**Decisão.** Usar a **convenção do gênero** (funil `segurado → objeto → perfil → coberturas → resultado`, que é pública e observável) e o conjunto de KPIs que o dashboard do Segfy demonstra ser o pulso operacional de uma corretora. Não replicar telas.

**Por quê.** Duas razões: as telas deles rodam atrás de login, então qualquer "reprodução" seria invenção com o nome deles colado; e a UI deles carrega complexidade que existe pelas restrições **deles** — 22 cias, milhares de corretoras, múltiplos ramos. Metade daquilo é configuração que a Klubi não precisa.

**Melhoria deliberada sobre o Segfy.** "Comissão produzida" vira **dois** números — produzida e recebida. A lacuna entre eles é a conciliação, e deixá-la visível na home é o que faz alguém agir.

---

## ADR-031 — Direção visual: densa e neutra

**Status:** Aceita

Ferramenta usada 30×/dia por 2–5 corretores. Densidade e velocidade acima de impressão: tab order correto, Enter avança, autosave por passo, recotar a partir de cotação anterior.

**Evitar explicitamente:** creme + serifada + terracota; quase-preto + verde ácido; broadsheet com fios finos. São defaults de IA e leem como template independente do assunto.

Cor apenas onde carrega informação — status, alerta, divergência. Copy em voz ativa, sentence case; botão "Transmitir" gera toast "Transmitida"; erro diz o que houve e o que fazer, nunca código HTTP.

---

## ADR-032 — Contrato da Yelum: confiar no exemplo, não na tabela

**Status:** Provisória — pendente de confirmação com a Yelum

**Divergências encontradas entre schema e exemplo:**

| Item | Divergência |
|---|---|
| `Partner` | `AgencyCode` no exemplo 11030 vs `CooperativeAgencyCode` na tabela e no 11043; um deles com espaços dentro das aspas |
| `EmployeeData` | `DepartmentCode` no exemplo e não na tabela; `EmployeeName` na tabela e não no exemplo |
| `PolicyHolderIsEmployee` | descrito como booleano, restrição diz numérica, exemplo manda `"T"` |
| chave de erro | sucesso usa `Success`, erro usa `Sucesso` |
| `CBE10` | aparece em `Residence[].Coverages` **e** no `Coverages[]` irmão, com valores diferentes (15000 vs 150000) — **qual vale para o cálculo é desconhecido** |

**Decisão provisória.** Confiar no exemplo. Aceitar `Success` e `Sucesso`. Pydantic estrito — falhar alto em campo desconhecido ou faltante, porque descobrir divergência na hora é melhor que descobrir no prêmio errado.

**A última linha é a perigosa:** errar qual nível de `Coverages` manda é errar prêmio. Pergunta aberta com a Yelum.

**Nota.** O changelog mostra mudanças a cada poucos meses. Versão do documento fica versionada no repo, e testes de contrato com os payloads exatos dos PDFs são o que avisa quando mudar.

---

## ADR-033 — FIPE: Parallelum exclusivo (BrasilAPI descartada)

**Status:** Aceita

**Contexto.** O plano original era BrasilAPI como primária + Parallelum como fallback. Após implementação, descobrimos que a BrasilAPI FIPE só expõe `/marcas` e usa o campo `valor` em vez de `codigo` para o ID da marca — inconsistente com os outros endpoints. Não há `/modelos`, `/anos` nem `/preco` na BrasilAPI.

**Decisão.** Parallelum exclusivo (`https://parallelum.com.br/fipe/api/v1/`). Sem fallback — a Parallelum já é o espelho oficial mais estável disponível.

**Consequências.** Se a Parallelum cair, o formulário de cotação auto/moto fica degradado (FipeSelector mostra erro amigável, cotação ainda é possível se o corretor souber o código FIPE). Cache de 30 dias elimina 99% das chamadas em ambiente real.

**Sinal de violação.** Reintroduzir BrasilAPI como primária. Chamar Parallelum sem passar pelo proxy backend (exporia CORS e eliminaria o cache).

---

## ADR-034 — FipeSelector: ComboBox inline em vez de select nativo

**Status:** Aceita

**Contexto.** A primeira versão usava um input de busca + `<select>` nativo abaixo, o que criava confusão: o usuário tinha que interagir com dois elementos distintos para fazer uma seleção.

**Decisão.** ComboBox inline: um único botão que abre uma caixa de busca + lista filtrada sobreposta. Navegação por teclado (Enter, Esc, ↑↓). Fechamento ao clicar fora. Implementado sem biblioteca adicional.

**Por quê.** O Select nativo não é estilizável de forma consistente entre browsers. O padrão de "botão trigger + lista inline" é mais previsível para o usuário e elimina a ambiguidade dos dois elementos. Custo: ~150 linhas de TSX, zero dependência nova.

**Sinal de violação.** Instalar `react-select`, `downshift` ou similar — as dependências existentes são suficientes e o componente customizado é testável e acessível.

---

## ADR-035 — UX-SEC antes de Fase 5: qualidade antes de escala

**Status:** Aceita

**Contexto.** A Fase 5 (Yelum) está bloqueada por credencial. Enquanto aguarda, há duas opções: aguardar passivamente, ou investir na qualidade do funil existente.

**Decisão.** A fase UX-SEC (auditoria 2026-08-24) é executada antes da Fase 5.

**Por quê.** Os problemas identificados — typo em campo financeiro, sem validação de `dados_risco` no backend, race condition no polling — são tecnicamente simples mas de alto impacto quando o volume de cotações aumentar. Integrar a Yelum em cima de um funil com esses problemas multiplica a superfície de falha silenciosa. Qualidade do funil é pré-requisito para confiança nos dados de paridade (Fase 6).

**Consequência.** Estimativa: 1 semana. Não atrasa Fase 5 porque o gate da Fase 5 (credencial) está fora do controle do time.

---

# Segurança

## ADR-036 — IP binding de sessão: soft-check, não hard-reject

**Status:** Aceita

**Contexto.** A sessão grava `ip_origem` no momento do login. A questão é o que fazer quando o IP muda durante a sessão: rejeitar a requisição (hard) ou só registrar o evento (soft).

**Decisão.** Soft-check: se `current_ip ≠ sessao.ip_origem`, emitir `WARNING session_ip_mismatch` no log estruturado. A sessão permanece válida.

**Por quê.** Hard-reject derruba usuários legítimos em redes móveis (IP troca a cada handover de cell tower), VPNs (IP muda ao reconectar) e NAT assimétrico (saída por links diferentes). O benefício de segurança real é baixo: o cookie `httponly + SameSite=Strict` já previne XSS e CSRF, e session-hijacking via rede requer MitM em HTTPS, o que é improvável. O log basta para detectar anomalia pós-fato.

**Revisar.** Se o produto migrar para contexto de alto risco (dados sensíveis de saúde, financeiro regulado), considerar hard-reject com janela de tolerância de IP.

**Sinal de violação.** Remover o log e voltar ao estado "IP nunca comparado". Ou implementar hard-reject sem permitir que o dono revise o tradeoff primeiro.

---

## ADR-037 — Hash determinístico no audit log: SHA-256, não `hash()` builtin

**Status:** Aceita

**Contexto.** O audit log de falha de login gravava `hash(body.email)` — o `hash()` do Python. Esse hash (a) não é determinístico entre processos (Python randomiza por padrão via `PYTHONHASHSEED`), (b) é reversível por dicionário para strings curtas e (c) muda entre versões do Python.

**Decisão.** `hashlib.sha256(email.encode()).hexdigest()` — determinístico, 256 bits, correlacionável entre processos e versões.

**Por quê.** O objetivo do hash no audit é correlacionar tentativas do mesmo e-mail entre sessões de log sem armazenar o e-mail em claro. `hash()` não cumpre nenhum dos três requisitos acima. SHA-256 cumpre todos.

**Nota sobre reversibilidade.** SHA-256 de e-mail é tecnicamente reversível por dicionário se o atacante souber o domínio. Aceitável aqui: o log é append-only com acesso restrito, e o ganho é correlação temporal, não anonimização forte. Para anonimização forte usar HMAC com chave rotacionável (como o CPF).

**Sinal de violação.** Voltar para `hash()`. Usar `md5()`. Logar o e-mail em claro.

---

## ADR-038 — CORS wildcard bloqueado no startup em produção

**Status:** Aceita

**Contexto.** `CORS_ORIGINS` é lida de variável de ambiente. Se alguém configurar `*` (wildcard), a API passa a aceitar requisições cross-origin de qualquer domínio — incluindo cookies com `credentials: true` (o que o browser bloqueia, mas o risco existe se o comportamento mudar).

**Decisão.** No startup do `main.py`, se `*` estiver em `CORS_ORIGINS` e `DEBUG=false`, o processo levanta `RuntimeError` e recusa iniciar.

**Por quê.** Fail-fast no startup é mais seguro que silenciosamente aceitar uma configuração perigosa. O erro aparece no log de deploy, não em produção sob carga.

**Consequência.** Em desenvolvimento (`DEBUG=true`) o wildcard ainda é aceito para facilitar o uso de `localhost:*` sem configuração.

**Sinal de violação.** Remover o guard para "simplificar o deploy". Usar `CORS_ORIGINS=*` em produção.
