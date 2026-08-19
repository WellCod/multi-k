# multi-K — Prompts faseados

Um prompt por fase. Cola inteiro no Claude Code, junto com `multi-k-escopo.md`.

**Como usar:** não pule fases, não junte duas. A seção "NÃO faça" de cada uma é o que segura escopo quando é você sozinho decidindo — ela é a parte mais importante do prompt, não um rodapé.

**Regra permanente:** quatro módulos você lê linha por linha e nunca aceita em bloco — auth/sessão, cifragem de PII, redação de log, enforcement de RLS. O resto pode ser revisado por comportamento.

---

## FASE 0 — Setup local

```
Projeto multi-K: multicálculo e gestão para corretora de seguros.
Stack: Python 3.12 + FastAPI + Postgres 16 + React 18 + Vite + TypeScript + Tailwind + shadcn/ui.
Tudo roda local via Docker Compose. Nada de cloud nesta fase.

Crie a estrutura do projeto:

backend/
  app/
    domain/          # modelos canônicos, eventos, regras
    adapters/        # um subpacote por seguradora
      base.py        # PortaSeguradora (Protocol) + tipos canônicos de fronteira
      fake/
    api/             # rotas FastAPI
    infra/           # db, secrets, logging, auditoria
    main.py
  tests/
  pyproject.toml
frontend/
  src/{components,pages,lib,hooks}/
docker-compose.yml   # postgres + adminer
.github/workflows/ci.yml
.gitignore

Backend: fastapi, uvicorn, pydantic v2, sqlalchemy 2.0, alembic, httpx,
argon2-cffi, structlog, pytest, respx, ruff, mypy.

CI (roda local via `make check` e no GitHub Actions):
- gitleaks (bloqueia merge se achar segredo)
- ruff + mypy strict no backend
- pytest
- teste de arquitetura: falha se "yelum", "BrokerProposalNumber", "CoverageCode",
  "CommercialProductCode" aparecerem fora de backend/app/adapters/yelum/

.gitignore OBRIGATORIAMENTE inclui, antes de qualquer coisa:
  .env, .env.*, *.postman_collection.json, docs/yelum/, *.pdf

Motivo: a documentação da Yelum tem cláusula de confidencialidade e a collection
do Postman contém usuário e senha de homologação.

Crie `infra/secrets.py` com uma interface SecretProvider e uma implementação
EnvSecretProvider. Não use os.environ direto em lugar nenhum do código.
Isso existe para que trocar por Google Secret Manager depois seja uma classe.

PRONTO QUANDO: `docker compose up` sobe, `GET /health` responde 200,
`make check` passa, `npm run dev` abre a SPA.

NÃO FAÇA: autenticação, modelo de domínio, nenhuma tela além do esqueleto,
nenhuma configuração de GCP, nenhum Dockerfile de produção.
```

---

## FASE 1 — Fundação

```
Contexto: leia multi-k-escopo.md, seções 3 e 5.

Implemente, nesta ordem:

1. AUTENTICAÇÃO
Sem cadastro público, sem reset self-service, sem SSO. Admin provisiona usuários.
- Argon2id para senha
- Sessão em cookie httponly + secure + samesite=strict
- Rate limit no login: 5 tentativas / 15 min por usuário e por IP
- Dependency get_current_user() no FastAPI. NENHUMA outra parte do código
  sabe de onde veio a identidade. user_id é UUID interno gerado por nós.
- Papéis: corretor, admin

2. MODELO CANÔNICO — três camadas, Pydantic v2
- Risco: RiscoAuto e RiscoResidencia, agnósticos de seguradora
- Negocio: blob tipado por adapter. NÃO tente unificar entre cias.
- Ciclo: eventos imutáveis — CotacaoCriada, PropostaTransmitida, ApoliceEmitida,
  EndossoRegistrado, ParcelaGerada, ComissaoRegistrada, SinistroAberto
  Apólice e parcela são PROJEÇÕES dos eventos, nunca tabelas mutáveis.

TODO valor monetário é Decimal. float nunca toca dinheiro, em lugar nenhum.

3. TABELA DE DOMÍNIOS
dominio(cia, tipo, codigo, descricao, ativo, atualizado_em)
Nenhum código de cobertura, profissão, estado civil ou plano de pagamento
hardcoded em Python ou TypeScript. Tudo vem daqui.

4. PortaSeguradora (Protocol) + ADAPTER FAKE
Interface conforme escopo §2. O fake retorna dados plausíveis e simula
latência de 8 a 15 segundos — isso não é enfeite, é o que faz a demo passar
como sistema real e o que força a UI a tratar espera corretamente.
O fake deve conseguir retornar os três estados: sucesso, restrição, erro.

5. LOGGING COM ALLOWLIST
structlog configurado para logar APENAS campos explicitamente permitidos.
Campo novo não é logado por default. Teste automatizado que falha se
"cpf", "password", "client_secret", "access_token" aparecerem em qualquer sink.
Correlation ID em toda requisição.

6. AUDITORIA
Tabela append-only. Sem UPDATE, sem DELETE — garantido por permissão no
Postgres, não por convenção de código.
Registra: acesso a dado de cliente, revelação de PII, cotação, transmissão,
login, falha de login, mudança de papel.

7. RLS
Policy no Postgres: corretor vê a própria carteira, admin vê tudo.
Enforcement na camada de dados. Não confie no controller.
Toda tabela de negócio tem tenant_id NOT NULL com valor fixo único.
A coluna existe; a máquina multi-tenant não.

PRONTO QUANDO: login funciona, um corretor não enxerga carteira de outro
(teste automatizado prova isso), fake adapter retorna cotação pela interface,
nenhum CPF aparece em log algum.

NÃO FAÇA: telas além do login, o adapter da Yelum, PDF, dashboard,
qualquer chamada HTTP externa.
```

---

## FASE 2 — Cotação end-to-end

```
Contexto: escopo §6, funil de cotação.

1. ORQUESTRADOR
Fan-out assíncrono sobre N adapters (hoje só o fake). Timeout por cia,
resultado parcial exibido conforme chega, cancelamento pelo usuário.
Fila em Postgres com SKIP LOCKED. Não use Celery nem Redis.

2. CLIENTE E OBJETO
Cadastro de cliente com busca por CPF via blind index (HMAC), nunca por
CPF em claro. Veículos e imóveis vinculados ao cliente, reutilizáveis
entre cotações. Cliente com objeto cadastrado pula do passo 1 direto ao 3.

3. FUNIL — 5 passos, Auto e Residência
Passo 2 muda por ramo; o resto é o mesmo componente.
- React Hook Form + Zod
- Autosave a cada passo. Sessão expirada não pode perder 4 minutos de trabalho.
- Tab order correto, Enter avança. O usuário real é digitador rápido.
- Campos de domínio populados da tabela dominio, nunca de constante em código.
- CommissionPct é campo do formulário, visível apenas para admin.

4. HISTÓRICO IMUTÁVEL
Cotação nunca sofre UPDATE. Alteração gera nova versão com link para a anterior.
Guarde payloadOriginal — request e response brutos do adapter, cifrados.
Isso não é opcional: é a única prova de qual dado foi enviado quando o corretor
disser que o valor não bateu, E é o que a transmissão de proposta reenvia.

5. RECOTAR
A partir de cotação existente, pré-preenchida. Renovação e ajuste são a
maioria do volume real.

6. TRÊS ESTADOS DE RESULTADO
Sucesso, restrição (cotou com ressalvas) e erro são estados distintos.
Restrição exibe as mensagens ao corretor sem parecer falha.
Se o resultado indicar necessidade de vistoria prévia, isso aparece em
destaque — muda o prazo que o corretor promete ao cliente.

7. ESTADO DE CARREGAMENTO
"Consultando Yelum… 12s" com botão cancelar. Nunca spinner mudo.

PRONTO QUANDO: você cota Auto e Residência do início ao fim contra o fake,
o histórico guarda tudo, recotar funciona, e fechar o browser no passo 3
não perde os passos 1 e 2.

NÃO FAÇA: comparativo visual, PDF, transmissão de proposta, dashboard,
adapter real.
```

---

## FASE 3 — Comparativo, PDF, gestão

```
1. COMPARATIVO
Franquias lado a lado, coberturas com LMI, parcelamentos.
Este é o único artefato que não existe no portal da seguradora — é onde
o produto justifica existir. Densidade acima de decoração.

2. PDF PARA O CLIENTE
Comparativo com logo da corretora. É o entregável que vai pro cliente final.
Nota: quando a Yelum liberar, use a API de Impressão dela para cotação,
proposta, apólice, parcelas e carta verde. NÃO construa gerador para esses.
Construa apenas o comparativo, que é nosso.

3. TIMELINE DO CLIENTE
Cotação → proposta → apólice → endosso → parcela → renovação → sinistro,
em ordem, numa tela. Alimentada pelos eventos da Fase 1.

4. PROJEÇÕES DE GESTÃO
Apólice, parcela e comissão como projeções sobre o stream de eventos.
- Cronograma de parcelas com vencimento e status
- Comissão PREVISTA calculada de CommissionPct × prêmio × cronograma
- Campo separado para comissão RECEBIDA, ainda vazio (vem do E-Retorno na Fase 7)
- Distribuição por CommissionParticipation quando houver rateio

5. RENOVAÇÃO
Janela D-60 / D-45 / D-30 com responsável atribuído e status.

6. TRANSMISSÃO DE PROPOSTA
Implementada, disparada por humano com confirmação explícita.
PropostaCanonica = RiscoCanonico + DadosComplementares.
Ela reenvia o contrato inteiro da cotação — por isso payloadOriginal é obrigatório.

PRONTO QUANDO: comparativo gera PDF, timeline mostra a vida de um cliente,
parcelas e comissão prevista aparecem corretas, transmissão funciona contra o fake.

NÃO FAÇA: conciliação de comissão recebida (sem E-Retorno é chute),
gestão de sinistro, dashboard.
```

---

## FASE 4 — Dashboard, relatórios, seed — DEMO

```
Objetivo desta fase: algo apresentável à diretoria. O critério não é
funcionalidade, é PARECER REAL.

1. HOME POR PAPEL
Corretor: fila de trabalho. Renovações na janela atribuídas a mim, propostas
paradas, parcelas vencendo dos meus clientes, cotações abandonadas há 2+ dias.
O corretor abre o sistema para saber o que fazer, não para ver gráfico.

Admin/gestor: KPIs — segurados vigentes, apólices vigentes, cotações em
andamento, renovações efetivadas, prêmio líquido, e comissão PRODUZIDA ×
RECEBIDA lado a lado. A lacuna entre os dois é a conciliação; deixá-la
visível é o que faz alguém agir sobre ela.
Período 15/30/90/custom. Corte por ramo e por seguradora.
Barra horizontal ordenada, não donut — donut de 6 fatias não compara.

2. RELATÓRIOS
Produção por corretor, conversão cotação→proposta→apólice, ticket médio,
mix de carteira, retenção de renovação. Export CSV e XLSX em todos.

3. SEED SINTÉTICO — a parte que decide a demo
3 corretores, ~40 clientes, ~120 cotações, ~60 apólices vigentes.
Mix: 70% auto, 20% residencial, 10% outros.
Região Campinas/Indaiatuba-SP.
Veículos que uma corretora daqui realmente cota: Onix, HB20, Strada, Toro,
Corolla, Compass, Renegade, Kwid, Polo, T-Cross, Creta.
Prêmio auto: R$ 1.800–4.500/ano. Residencial: R$ 300–900/ano.
Nomes brasileiros plausíveis. NADA de "Cliente Teste 001".

CPF: gerado válido pelo algoritmo mas inexistente. ZERO PII real no seed,
nem sua, nem de cliente. Isso permite rodar a demo em qualquer laptop
ou link temporário sem exposição.

4. MARCA D'ÁGUA DE DEMO
Faixa discreta e permanente indicando dados simulados, visível em toda tela
que mostra valor de prêmio. Se alguém da diretoria repetir um número como
se fosse Yelum real, você criou um problema.

5. DESIGN
Ferramenta densa e neutra. Tipografia utilitária, hierarquia por peso e
espaço, cor apenas onde carrega informação: status, alerta, divergência.
NÃO use: fundo creme com serifada e acento terracota; fundo quase-preto com
verde ácido; layout broadsheet com fios finos. São defaults de IA e leem
como template.
Copy em voz ativa, sentence case. Botão "Transmitir" gera toast "Transmitida".
Erro diz o que houve e o que fazer, nunca código HTTP.

PRONTO QUANDO: alguém de fora abre o sistema e não percebe que os dados
são falsos até ler a marca d'água.

NÃO FAÇA: otimização de performance, responsividade mobile refinada,
adapter real, nada de infra.
```

**Depois desta fase:** demo para a diretoria, e o e-mail ao ponto focal da Yelum com a demo anexada e as 12 perguntas do escopo §10. Nesta ordem — a demo torna o pedido muito mais forte que uma intenção escrita.

---

## FASE 5 — Adapter Yelum real

**Gate: credencial de mock ou homologação.** Comece por Residência (contrato em mãos), Auto quando a documentação chegar.

```
Contexto: leia multi-k-escopo.md §4 inteiro antes de escrever qualquer código.

1. AUTENTICAÇÃO
POST /controledeacesso/token?grant_type=client_credentials
Content-Type: application/x-www-form-urlencoded
Body: client_id, client_secret, username, password

O token é OPACO, não JWT. Você não consegue ler a expiração.
Portanto: cache em memória do processo; trata 401 como expirado; reautentica
e repete a requisição UMA vez. Nunca tente adivinhar validade.
Nunca cacheie em Redis ou disco.
Os quatro segredos vêm do SecretProvider. Se já houver credencial real,
EnvSecretProvider não serve mais — implemente o provider definitivo.

2. ANTI-CORRUPTION LAYER
Mapeia RiscoResidencia → contrato Yelum e resposta → CotacaoCanonica.
Todo campo monetário vira Decimal na fronteira. O contrato mistura número e
string para o mesmo conceito (TotalPremiumValue) — normalize na entrada.
Booleanos são "T"/"F" string, exceto NeedInspectionRisk que é boolean real.
Aceite tanto "Success" quanto "Sucesso" como chave de status.
Pydantic estrito: falhe alto em campo desconhecido ou faltante. Descobrir
divergência na hora é melhor que descobrir no prêmio errado.

3. ENDPOINTS
POST /offer/v1/quote          cotar
PUT  /offer/v1/quote/{id}     recotar (mesmo contrato, id na URL e no body)
POST /offer/v1/proposal       transmitir
Base URL por ambiente, do SecretProvider. Nunca hardcoded.

4. RATE LIMIT E RESILIÊNCIA
500 req/min por IP, 300 transações/min, 429 se exceder.
SLA de 85%/dia significa quase 4h de indisponibilidade permitida por dia.
Circuit breaker, backoff exponencial, e a UI trata "Yelum fora" como estado
normal com mensagem clara — não como erro inesperado.

5. TESTES DE CONTRATO
respx com os payloads EXATOS dos PDFs de Residence Quote e Residence Proposal.
Rodam sem rede. São o que te avisa quando a Yelum mudar o contrato —
o changelog mostra mudanças a cada poucos meses.

6. SINCRONIZAÇÃO DE DOMÍNIOS
Job que popula a tabela dominio pela API de Domínios. Os valores plausíveis
da Fase 1 são substituídos pelos reais. Nenhuma linha de código muda.

7. AUTO
Quando a documentação chegar: novo RiscoAuto no mesmo adapter, outro
CommercialProductCode. NÃO invente nomes de campo de Auto antes de ter o
contrato — herde a estrutura de Residência para o encanamento e espere
a documentação para o miolo de risco.

PONTOS AMBÍGUOS — confirme com a Yelum antes de assumir:
- CBE10 aparece em Residence[].Coverages E no Coverages[] irmão, com valores
  diferentes. Qual vale para o cálculo?
- AgencyCode vs CooperativeAgencyCode em Partner
- DepartmentCode e EmployeeName em EmployeeData
Regra enquanto não houver resposta: confie no exemplo, não na tabela.

PRONTO QUANDO: cotação real de Residência retorna e o adapter fake continua
passando nos mesmos testes de interface.

NÃO FAÇA: transmissão automática, otimização de latência, mudar nada
fora de adapters/yelum/. Se precisar mudar o domínio para acomodar a Yelum,
PARE — sua camada anticorrupção está furada e isso é bug de arquitetura.
```

---

## FASE 6 — Paridade

```
O requisito funcional principal do sistema. Se o número na tela não bate com
o portal da Yelum, o corretor volta ao portal e todo o resto foi desperdício.

1. HARNESS DE RECONCILIAÇÃO
- Amostra diária de N cotações reais
- Tela para o operador lançar o valor obtido no portal da Yelum
- Compara prêmio total, prêmio líquido, IOF, franquia por cobertura,
  e cada opção de parcelamento
- Divergência > R$ 0,01 gera alerta com payloadOriginal anexado

2. DIAGNÓSTICO AUTOMÁTICO
Este é o instrumento que transforma horas de investigação em minutos:
- Decomposição do prêmio por cobertura (a API retorna prêmio por cobertura —
  isso isola metade dos casos sozinho)
- Diff campo a campo entre o que foi enviado e o que o portal recebeu
- Bisseção automática sobre o conjunto de campos para achar o culpado

3. PAINEL DE DIVERGÊNCIA
Taxa de paridade por dia, por produto, por faixa de prêmio. É a métrica mais
importante do sistema e precisa estar visível todo dia.

GATE: ≥99% de paridade exata em 200 cotações, sustentado 30 dias sem
intervenção manual. Abaixo disso não sobe para os corretores.
95% parece bom e destrói a confiança em duas semanas.

NÃO FAÇA: liberar para corretor antes do gate. Automatizar transmissão
antes do gate.
```

---

## FASE 7 — E-Retorno

**Gate: Security Assessment assinado.**

```
O E-Retorno entrega comissão gerada, emissões realizadas, parcelas geradas
e andamento dos pagamentos, além dos sinistros de cada apólice.

1. INGESTÃO
Job periódico consumindo movimentos. Cada movimento vira EVENTO no seu
stream — não faça UPDATE em projeção. Idempotência por identificador do
movimento: reprocessar o mesmo lote não pode duplicar nada.

2. CONCILIAÇÃO DE COMISSÃO
Compara prevista (CommissionPct × prêmio × cronograma) com recebida.
Encontra: parcela paga sem comissão repassada, percentual divergente,
estorno por cancelamento, endosso que alterou prêmio retroativamente,
comissão de apólice ausente da base.
Tela de exceções, não relatório passivo. O valor está em alguém agir.

3. SINISTRO READ-ONLY
Exibição e alerta "seu cliente abriu sinistro há 2 dias".
Sinistro é o momento de maior risco de churn da carteira — cliente que abre
sinistro e não sente o corretor presente não renova.
NÃO construa gestão de sinistro: perícia, documentação e indenização rodam
na seguradora.

PRONTO QUANDO: comissão recebida aparece no dashboard ao lado da prevista,
e a tela de exceções mostra divergências reais.
```

---

## FASE 8 — Deploy GCP e endurecimento

**Precede a chave de produção.**

```
1. INFRA
Cloud Run + Cloud SQL Postgres com IP privado (sem IP público) +
Secret Manager com CMEK + Cloud KMS + Artifact Registry.
Região southamerica-east1 — por latência até a Yelum, não por exigência
legal. A LGPD não obriga residência de dados no Brasil.

2. IP FIXO DE SAÍDA
VPC egress + Cloud NAT com IP externo reservado.
Cloud Run sai por IP efêmero de pool compartilhado. A Yelum controla rate
limit por IP e pode exigir allowlist. Retrofitar isso depois é doloroso.

3. CONSTRAINTS DE ORGANIZAÇÃO
- Proibir criação de chave de service account
  (constraints/iam.disableServiceAccountKeyCreation)
  Arquivo JSON de service account é o vetor nº 1 de vazamento em GCP.
  Use identidade anexada ao Cloud Run e Workload Identity Federation no CI.
- VPC Service Controls: perímetro em volta do projeto. Mesmo com credencial
  vazada, o dado não sai para outro projeto.
- Data Access logs LIGADOS — vêm desligados por padrão no GCP. Exporte para
  projeto separado onde a equipe de dev não tem permissão de apagar.
Verifique a sintaxe atual dessas constraints; ela muda.

4. PII EM PRODUÇÃO
Envelope encryption em CPF/CNPJ/chassi/placa com chave no KMS.
Blind index para busca. Exibição mascarada por padrão, revelar é logado.

5. OPERAÇÃO
Backup cifrado com restore TESTADO — backup não testado não é backup.
Cloud Armor. Runbook de incidente. Alerta de expiração de credencial.

6. REVISÃO ADVERSARIAL
Passe separado cujo único trabalho é ATACAR este código, sem o contexto de
tê-lo escrito. Código gerado e revisado pelo mesmo raciocínio herda os mesmos
pontos cegos. Foco: auth, cifragem, log, RLS, o adapter.

7. DOCUMENTAÇÃO LEGAL
ROPA, aviso de privacidade, teste de balanceamento de legítimo interesse,
política de retenção. Inclua: a Yelum consulta Boa Vista com o CPF enviado;
o WhatsApp é operador tratando dado de segurado.
Redija tudo, mas alguém com responsabilidade assina.

8. PENTEST EXTERNO
Antes de qualquer dado real de cliente.

NUNCA: dump de produção em dev. Use seed sintético. Se precisar reproduzir
bug com dado real, faça em produção com acesso temporário auditado.
```

---

## FASE 9 — MCP para o bot

**Só depois do gate de paridade.** Bot cotando sobre integração não validada multiplica um erro que você ainda não sabe que tem.

```
Servidor MCP expondo o domínio ao bot de WhatsApp. É mais um consumidor
da API interna, do lado do frontend — não um caminho novo até a Yelum.

FERRAMENTAS
- buscar_cliente(cpf)
- criar_ou_atualizar_risco(dados_parciais)   → validação incremental
- cotar(risco_id)
- consultar_status(protocolo)
- consultar_apolice / parcela / sinistro     (read-only, E-Retorno)

REGRAS DURAS
- CommissionPct e PromotionalDiscountVlr NÃO são expostos como parâmetro.
  Ficam fixos por configuração, fora do alcance do modelo. Um LLM com acesso
  a esses campos altera sua receita ou o prêmio do cliente.
- transmitir() NÃO é exposto. Transmissão é ato jurídico em nome da corretora
  e permanece humana.
- Toda cotação originada por MCP é marcada como tal e entra numa fila de
  revisão antes de sair para o cliente.
- Campos de risco alto (uso comercial do veículo, condutor 18–25, garagem)
  marcados como tal, com confirmação explícita registrada.
- Auditoria registra origem MCP e qual sessão de WhatsApp.

API INTERNA
Endpoint de cotação idempotente, aceita RiscoCanonico parcial com validação
incremental, retorna erro estruturado nomeando o campo culpado.
Isso serve o front hoje e o MCP depois, sem refactor.
```

---

## Ordem de execução

```
Hoje         Fase 0
Semana 1     Fase 1
Semana 2     Fase 2
Semana 3     Fase 3
Semana 4     Fase 4  →  DEMO  →  e-mail ao ponto focal Yelum
Em paralelo  cadastro no portal do desenvolvedor da Porto
Quando       Fase 5 → 6 → 7 → 8 → 9
a chave
chegar
```

Fases 0–4 não dependem de ninguém. Comece hoje.
