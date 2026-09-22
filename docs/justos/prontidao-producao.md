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

E2E executado em 21/09/2026 contra `api.staging.justos.com.br`. **O ciclo
fechou inteiro**, da autenticação ao link de checkout.

O bloqueio de 17/09 (`failure_on_creating_user`) era do lado da seguradora, em
staging, e foi contornado conforme orientação deles.

| Etapa | Estado |
|---|---|
| Autenticação (JWT ES256) | ✅ |
| `POST /brokers/quote` | ✅ |
| `POST /pricing` | ✅ |
| `PUT /coverages` | ✅ |
| `convert-formal-quote` | ✅ |
| `checkout-link` | ✅ link devolvido |

Dois pontos fecharam nesta execução: o **veículo do script é válido na base
real** (placa e código FIPE aceitos) e o **`PUT /coverages` funcionou**, uma das
chamadas que a seguradora não encontrava nos logs em 09/09.

### O que só apareceu ao fechar o ciclo

Três coisas que o `pricing` não detecta e o `convert-formal-quote` detecta:

**Placa e código FIPE são cruzados na formalização.** O veículo do script
declarava um modelo e uma placa de outro; passou por cotação e preço, e foi
recusado com `vehicle_not_found` na transmissão. Corrigido. O mesmo acontece
em produção se o corretor escolher o modelo errado no seletor FIPE — e o erro
só aparece depois de o preço já ter sido mostrado ao cliente.

**A seguradora recalcula a porcentagem da FIPE coberta entre a cotação e a
transmissão**, recusa com `fipe_price_percentage_covered_changed` e pede
concordância explícita: *"caso esteja de acordo, realize a transmissão
novamente"*. Num veículo 2007 a cobertura caiu de 100% para 70%.

Isso é portão de consentimento, não erro técnico: sem ele, o cliente
compraria cobertura menor que a exibida na tela. O adapter devolve a
divergência para o corretor decidir e **não confirma sozinho** — ver §4.8.

Falta confirmar com a seguradora se o recálculo também ocorre em produção ou
é comportamento do ambiente de staging.

**Uma proposta ativa por chassi.** Repetir o teste com o mesmo veículo devolve
`proposal_already_exists_for_chassis` até a proposta anterior ser cancelada.

## 4. Aderência ao contrato

| # | Item | Estado |
|---|---|---|
| 4.1 | Matriz de requisitos J1–J4 sem pendência no fluxo de cotação e proposta | ✅ |
| 4.2 | Comissão gravada é a devolvida pela seguradora, não a enviada | ✅ |
| 4.3 | `ci_code` exigido pela classe de bônus | ✅ |
| 4.4 | Segurado PF e PJ, CEPs distintos, enums fechados | ✅ |
| 4.5 | Dinheiro em `Decimal`, sem prêmio zero inventado | ✅ |
| 4.6 | Resposta bruta da seguradora não vaza para tela, log ou banco | ✅ |
| 4.7 | Exportação de apólices (E-Retorno) | ⏸️ suspensa a pedido da seguradora |
| 4.8 | Recálculo da cobertura FIPE volta para o corretor decidir, sem confirmação automática | ✅ |
| 4.9 | Validade de 30 dias corridos da cotação, recusada localmente | ✅ |
| 4.10 | Recusa definitiva não bloqueia reenvio; incerteza bloqueia | ✅ |

O item 4.7 **não bloqueia** cotar e transmitir em produção: é importação de
apólices vendidas, posterior ao fluxo de venda. A seguradora pediu para segurar
a construção até o layout fechar (21/09/2026).

## 5. Sequência recomendada

1. ~~Fechar o ciclo completo em staging~~ — feito em 21/09/2026 (§3).
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
