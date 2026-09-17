# Prontidão para produção — Justos

Data: 17/09/2026. Serve para responder, com evidência, a uma pergunta só:
**a integração Justos está configurada para produção?**

Cada item diz quem garante — o código, o CI ou uma pessoa. O que depende de
pessoa não fica marcado como pronto por otimismo.

## 1. Configuração do ambiente

| # | Item | Quem garante | Estado |
|---|---|---|---|
| 1.1 | `JUSTOS_ENV` aceita apenas `staging` ou `production`; valor inválido falha em vez de cair em staging | código + teste | ✅ |
| 1.2 | Em produção, a chave **não** pode vir de `JUSTOS_PRIVATE_KEY_PATH` — só do segredo inline | código + teste | ✅ |
| 1.3 | A interface só tira o aviso STAGING quando o ambiente é exatamente `production` | código | ✅ |
| 1.4 | `JUSTOS_PARTNER_NAME`, `JUSTOS_BROKER_ID` e `JUSTOS_CPF_CNPJ` presentes no ambiente de produção | pessoa | ⏳ |
| 1.5 | `JUSTOS_PRIVATE_KEY` de produção no gerenciador de segredos, com `\n` escapado | pessoa | ⏳ |

Antes de 1.1 e 1.2, um `JUSTOS_ENV=prod` deixava a aplicação cotando em staging
**sem o aviso na tela** — a combinação pior possível, porque a interface
afirmava produção.

## 2. Par de chaves

A seguradora exige um par **novo** para produção, distinto do de staging
(resposta de 09/09/2026).

| # | Item | Quem garante | Estado |
|---|---|---|---|
| 2.1 | Par EC P-256 de produção gerado (`scripts/gerar_chaves_ec.sh`) | pessoa | ⏳ |
| 2.2 | `public-key.pem` de produção enviado ao ponto focal, como anexo | pessoa | ⏳ |
| 2.3 | Chave cadastrada do lado da Justos e confirmada por eles | seguradora | ⏳ |
| 2.4 | Chave privada **fora** do repositório | `.gitignore` + gitleaks no CI | ✅ |

Para conferir qual chave está em uso de cada lado, sem trocar arquivo:

```bash
cd backend && python ../scripts/justos_chave_fingerprint.py
```

Imprime ambiente, origem da chave, curva e a impressão digital SHA-256 do SPKI.
A mesma impressão digital dos dois lados confirma que é o mesmo par; e a de
produção **tem de ser diferente** da de staging.

## 3. Fluxo exercitado contra a seguradora

E2E executado em 17/09/2026 contra `api.staging.justos.com.br`.

| Etapa | Estado |
|---|---|
| Autenticação (JWT ES256) | ✅ |
| `POST /brokers/quote` | ✅ |
| `POST /pricing` | ✅ mensal R$ 921,36 · anual R$ 10.516,92 |
| `PUT /coverages` | ✅ HTTP 200 |
| `convert-formal-quote` | ❌ HTTP 400 `failure_on_creating_user` |
| `checkout-link` | ⏸️ não alcançado |

Dois pontos fecharam nesta execução: o **veículo do script é válido na base
real** (placa e código FIPE aceitos) e o **`PUT /coverages` funcionou**, uma das
chamadas que a seguradora não encontrava nos logs em 09/09.

### O bloqueio, com evidência

```
400 {"error":"failure_on_creating_user",
     "context":{"title":"Erro ao validar o CPF",
     "description":"Tivemos uma instabilidade temporária ao validar o CPF.
                    Tente novamente em instantes."}}
```

A mensagem diz "temporária". As tentativas dizem outra coisa:

| Variação | Resultado |
|---|---|
| CPF sintético, cotação `90f10912-cd87-4cd2-924b-9a8cabc823e7` | 400 |
| CPF válido de pessoa real, cotação `214996d3-584b-473e-b8dd-bae4e078a944` | 400 |
| Mesma cotação, duas tentativas espaçadas em 30 s | 400 nas duas |
| Mesmo erro registrado em 09/09/2026 | persiste há mais de uma semana |

**Não é o tipo de CPF, não é transitório e não é o nosso payload** — as etapas
anteriores passam com os mesmos dados. O ponto de falha é a criação de usuário
no ambiente de staging da seguradora.

Isso precisa de ação do lado deles. O ponto focal ofereceu diagnosticar a partir
do `quote_uuid`, e há dois para consultar.

## 4. Aderência ao contrato

| # | Item | Estado |
|---|---|---|
| 4.1 | Matriz de requisitos J1–J4 sem pendência no fluxo de cotação e proposta | ✅ |
| 4.2 | Comissão gravada é a devolvida pela seguradora, não a enviada | ✅ |
| 4.3 | `ci_code` exigido pela classe de bônus | ✅ |
| 4.4 | Segurado PF e PJ, CEPs distintos, enums fechados | ✅ |
| 4.5 | Dinheiro em `Decimal`, sem prêmio zero inventado | ✅ |
| 4.6 | Resposta bruta da seguradora não vaza para tela, log ou banco | ✅ |
| 4.7 | Exportação de apólices (E-Retorno) | ⏸️ desenhada, no gate de fase |

O item 4.7 **não bloqueia** cotar e transmitir em produção: é importação de
apólices vendidas, posterior ao fluxo de venda.

## 5. Sequência recomendada

1. Fechar o **ciclo completo em staging** (§3) — é o que a própria seguradora
   pediu antes de liberar produção.
2. Gerar o par de produção e enviar a chave pública (§2.1 e 2.2).
3. Confirmar o cadastro com o ponto focal, conferindo a impressão digital (§2.3).
4. Publicar os segredos de produção (§1.4 e 1.5).
5. Virar `JUSTOS_ENV=production` e conferir em `/health` e no sumiço do badge.
6. Primeira cotação real acompanhada, conferindo a comissão devolvida.

## 6. Antes de integrar uma nova seguradora

A arquitetura suporta: implementar `PortaSeguradora` e a CIA entra pelo
registry, sem mudança no domínio. O que aprendemos com a Justos e vale como
critério de entrada para a próxima:

- **Não replicar correção em um adapter só.** A sanitização de erro ficou meses
  aplicada apenas na Justos; a varredura de 17/09 encontrou os mesmos defeitos
  na Yelum. Conversor de dinheiro e regras comuns ficam em `adapters/money.py`.
- **Ler o que a seguradora devolve, não assumir o que foi enviado.** Valeu para
  a comissão e vale para qualquer campo que a seguradora possa ajustar.
- **Default que preenche característica de risco é defeito**, não conveniência.
- **Faixa e enum vêm do contrato**, e a documentação pode estar desatualizada:
  a faixa de comissão publicada dizia 10–25 e a real é 0–25.
