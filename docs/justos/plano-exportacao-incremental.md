# Plano — exportação incremental de apólices e documentos (J3)

Data: 16/09/2026. Cobre o item 6 da ordem de ação de
[`../auditoria-requisitos-justos.md`](../auditoria-requisitos-justos.md).

**Este documento é desenho, não implantação.** A auditoria pede "planejar
exportação e documentos com cursor, idempotência e eventos corretos; somente
ativar após aprovação do gate de fase". Nada aqui autoriza ligar a
sincronização, criar agendamento ou emitir eventos de domínio a partir da
seguradora. Cada seção termina no critério de aceite que o gate deve cobrar.

Fonte: `documenta_api_busca_de_apolices_vendidas_multicalculo.txt` (19/08/2026),
referida como J3.

## 1. O que existe hoje

`JustosSeguradora.movimentos(desde)` pagina `GET /brokers/policy/export` e
converte cada apólice em `MovimentoCanonico`. **Nenhum código chama esse
método**: não há agendador, consumidor nem persistência. Na prática a
exportação é uma função pronta e desligada.

Cinco divergências entre o que o método faz e o que J3 descreve:

| # | Hoje | J3 |
|---|---|---|
| D1 | Recebe `date` e monta `datetime` à meia-noite UTC | O filtro é `updatedAt >= updatedSince` em ISO 8601; truncar para o dia reprocessa o dia inteiro a cada varredura |
| D2 | Falha HTTP faz `break` e devolve o que já tinha | O parcial fica indistinguível do completo; a próxima varredura não sabe que faltou página |
| D3 | `INACTIVE` vira `tipo="cancelamento"`, o resto vira `"emissao"` | §4.3: `INACTIVE` é "fora de vigência por qualquer motivo — **não significa, por si só, cancelamento pela corretora**" |
| D4 | `previousPolicyId` é descartado | §5: valor preenchido **confirma** renovação |
| D5 | Não há cursor nem deduplicação | §4.4 e §6: guardar o maior `updatedAt`, correlacionar por `policyId`, atualizar em vez de duplicar |

## 2. Cursor durável

J3 §4.4: os resultados vêm ordenados por `updatedAt` crescente; guarde o maior
`updatedAt` recebido e use-o como `updatedSince` na varredura seguinte.

- Cursor persistido por CIA, com precisão de instante (`timestamptz`), não de
  dia. `movimentos(desde: date)` precisa virar `datetime`.
- Guardar o cursor **apenas quando a varredura terminou inteira**. Com falha no
  meio, o cursor não avança e a varredura seguinte repete o intervalo — repetir
  é seguro porque a projeção é idempotente (§4); pular não é.
- `updatedSince` é inclusivo (`>=`). Reprocessar a última apólice a cada
  varredura é esperado e inofensivo; não compensar com um microssegundo a mais,
  porque isso perde registros que compartilham o mesmo `updatedAt`.
- Carga inicial: data bem antiga, conforme §4.2.

**Aceite:** varredura interrompida não avança o cursor; duas varreduras
seguidas sobre o mesmo intervalo produzem o mesmo estado final.

## 3. Paginação e falha parcial

- `take` máximo é 100 (§4.2) — o valor atual já está no limite.
- Falha em qualquer página **aborta a varredura com erro**, em vez de devolver
  lista curta. O chamador precisa distinguir "acabou" de "parou no meio".
- Página curta (`len(data) < take`) continua sendo o fim.
- Teto de páginas por varredura para não girar indefinidamente se o serviço
  devolver sempre página cheia.

**Aceite:** teste com falha na segunda página falha a varredura inteira e
mantém o cursor onde estava.

## 4. Identidade e idempotência

- `policyId` é a chave estável (§6). `insurerPolicyNumber` **não** serve:
  é `null` enquanto não há documento emitido.
- A projeção é um *upsert* por `(cia, policyId)`, não um append. §6 avisa que
  mudanças de status reaparecem na varredura.
- Registrar `updatedAt` junto e ignorar payload com `updatedAt` menor que o
  gravado — protege contra reordenação e reprocessamento fora de ordem.

**Aceite:** aplicar a mesma página duas vezes não cria segundo registro nem
segundo evento.

## 5. Estado e causa de encerramento

Esta é a correção de D3 e não pode ser resolvida inventando causa.

- Persistir `status` (`ACTIVE`/`INACTIVE`) e `cancellationDate` como vieram.
- `INACTIVE` cobre cancelamento pelo segurado, pela corretora ou pela Justos,
  inadimplência e fim de vigência sem renovação. O contrato **não distingue**
  esses casos, então o sistema também não pode.
- Enquanto não houver campo de causa, o evento canônico deve dizer o que se
  sabe — "apólice encerrada" — e não o que se supõe — "cancelada". Isso pede
  um tipo novo em `MovimentoCanonico.tipo`, hoje limitado a
  `emissao|parcela|comissao|sinistro|cancelamento`.
- `insurerPolicyNumber`, `policyPdfUrl` e `endorsementPdfUrl` vêm `null` em
  apólice que ficou inativa sem nunca emitir documento (§4.3). Ausência de
  documento não é falha de importação.

**Aceite:** apólice `INACTIVE` não gera evento de cancelamento; o estado bruto
e a data chegam ao domínio sem reinterpretação.

## 6. Vínculo de renovação

- `previousPolicyId` preenchido **confirma** renovação e deve ser gravado.
- `null` **não prova** negócio novo: J3 §5 diz que só vem preenchido nas
  renovações originadas no canal de corretor/multicálculo. Não inferir negócio
  novo a partir da ausência, pelo mesmo motivo que não se infere renovação a
  partir do bônus.

**Aceite:** vínculo gravado quando presente; ausência não marca nada.

## 7. Ciclo mensal não é parcela anual

Correção da divergência registrada na matriz (J3 §5.7).

- Em apólice mensal **não existe parcelamento**: cada item de `installments` é
  a cobrança de um ciclo, e `number` é o número do ciclo.
- `validUntil` em mensal é o fim da cobertura do ciclo vigente, não fim de
  vigência contratual (§5). Não usar como data de término do contrato.
- Hoje a proposta gera parcelas locais a cada 30 dias. Esse calendário é
  estimativa e **não pode** ser exibido ao lado da cobrança real, nem
  sobrescrito por ela sem uma leitura compatível para registros antigos.
- `status` da cobrança é `PAID`, `PENDING`, `FAILED`, `CANCELLED` ou
  `REFUNDED`; `paymentMethod` é `CARD` ou `PIX`. Não existe boleto — a
  interface não deve oferecer essa opção.

**Aceite:** cobrança real e calendário estimado ficam distinguíveis na leitura;
migração preserva o que já foi gravado.

## 8. Comissão e IOF

- `commission.percentage` é a taxa contratada, e J3 §5.6 avisa que **não** é a
  razão entre `commission.amount` e `premium.grossPremium`, porque o bruto
  inclui IOF. Não recalcular o percentual a partir dos valores.
- Quando a cotação de origem não é mais resolvível, o próprio campo cai na
  razão sobre o bruto — ou seja, o valor pode mudar de significado sem aviso.
  Gravar como veio e não usar para conferir a comissão local.
- `premium.netPremium`, `grossPremium`, `iof` e `totalPremium` entram em
  `Decimal`, como o resto do sistema.

**Aceite:** nenhum percentual de comissão é derivado de divisão local.

## 9. Documentos

- `policyPdfUrl` e `endorsementPdfUrl` são assinadas e **expiram em 15
  minutos** (§6). Baixar no momento da consulta; **nunca** persistir a URL.
- São documentos distintos: `policyPdfUrl` é a apólice ou bilhete;
  `endorsementPdfUrl` é o comprovante do último endosso. Em mensal, o
  `policyPdfUrl` é o bilhete do ciclo mais recente — o arquivo muda ao longo
  do tempo sob o mesmo `policyId`.
- `endorsementCount` indica endosso em anual; `null` quando não há documento.
- Guardar o arquivo exige decidir onde e por quanto tempo, com retenção e
  controle de acesso. **Fora do escopo deste plano.**

**Aceite:** nenhuma URL assinada aparece em banco, log ou payload de API.

## 10. Ordem sugerida

1. Cursor e varredura com falha explícita (§2 e §3) — sem persistir apólice.
2. Projeção idempotente por `policyId` (§4), ainda sem emitir evento.
3. Estado e encerramento (§5), incluindo o tipo canônico novo.
4. Vínculo de renovação (§6).
5. Cobranças reais e leitura compatível do calendário estimado (§7 e §8).
6. Documentos (§9), depois de decidir retenção.
7. Agendamento — **só aqui a sincronização liga**, e só com o gate aprovado.

## 11. A confirmar com a seguradora

1. Existe campo, atual ou planejado, que distinga a causa do `INACTIVE`?
2. `updatedAt` muda em alteração de cobrança, ou só em mudança de apólice?
3. Qual a janela máxima aceita em `updatedSince` na carga inicial?
4. Há limite de requisições por minuto no `/policy/export`?
5. `previousPolicyId` passa a ser preenchido em renovação originada fora do
   canal de multicálculo?

## 12. Fora deste plano

Validade da cotação continua sem fonte: `validUntil` de J3 é vigência de
**apólice**, não prazo de cotação. Não automatizar expiração antes de
confirmação contratual.
