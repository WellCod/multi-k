# Plano — exportação incremental de apólices e documentos (J3)

Data: 16/09/2026. Revisado em 17/09/2026 com as respostas da seguradora.
Cobre o item 6 da ordem de ação de
[`../auditoria-requisitos-justos.md`](../auditoria-requisitos-justos.md).

**Este documento é desenho, não implantação.** A auditoria pede "planejar
exportação e documentos com cursor, idempotência e eventos corretos; somente
ativar após aprovação do gate de fase". Nada aqui autoriza ligar a
sincronização ou criar agendamento.

Fonte: `documenta_api_busca_de_apolices_vendidas_multicalculo.txt` (19/08/2026),
referida como J3, e as respostas de Leonardo Cardoso em 17/09/2026.

## 0. Respostas da seguradora (17/09/2026)

> **A API de exportação ainda está em homologação, não é um layout fechado.
> Podem integrar, mas contem com ajustes e acompanhem o changelog.**

Isso muda o peso do investimento: vale construir o que é estável — cursor,
idempotência, projeção — e evitar amarrar o domínio a campos que podem mudar.

| # | Pergunta | Resposta | Efeito |
|---|---|---|---|
| 1 | Campo com a causa do `INACTIVE` | **Não existe hoje.** Pode ser avaliado; a seguradora pergunta se é bloqueante para nós | §5 mantido: registrar encerramento sem causa. **Devemos uma resposta a eles** |
| 2 | `updatedAt` muda com mudança de cobrança | **Muda.** Status de cobrança move o `updatedAt` da apólice | §2 confirmado; a exportação **serve** como fonte de comissão recebida |
| 3 | Janela da carga inicial | **Sem limite.** Em produção são **54 apólices** | §3 simplificado: a carga inicial cabe em uma página |
| 4 | Limite de requisições | **Sem limite rígido**, mas o endpoint é custoso: **uma varredura por hora** | §10 passo 7: cadência definida |
| 5 | `previousPolicyId` fora do canal | **Não previsto.** O campo cobre só renovação **dentro da Justos** — apólice deles renovada com eles | §6 corrigido: `null` não distingue negócio novo de renovação de outra seguradora |
| 6 | Quando o `ci_code` é obrigatório | **Pelo bônus.** Classe de bônus maior que zero exige o CI | **Corrigido no código**: o gatilho era a renovação declarada |
| 7 | Piso de 15% em renovação de outra corretora | **Não precisamos identificar.** O piso é aplicado na criação da cotação e a comissão **volta na resposta**; basta ler em vez de assumir a enviada. Só existe quando a apólice anterior é da Justos | **Corrigido no código**: gravávamos a comissão enviada |

## 1. O que existe hoje

`JustosSeguradora.movimentos(desde)` pagina `GET /brokers/policy/export` e
converte cada apólice em `MovimentoCanonico`. **Nenhum código chama esse
método**: não há agendador, consumidor nem persistência.

| # | Hoje | J3 |
|---|---|---|
| D1 | Recebe `date` e monta `datetime` à meia-noite UTC | O filtro é `updatedAt >= updatedSince`; truncar para o dia reprocessa o dia inteiro |
| D2 | Falha HTTP faz `break` e devolve o que já tinha | O parcial fica indistinguível do completo |
| D3 | `INACTIVE` vira `tipo="cancelamento"` | §4.3: `INACTIVE` é "fora de vigência por qualquer motivo" |
| D4 | `previousPolicyId` é descartado | Valor preenchido confirma renovação na Justos |
| D5 | Não há cursor nem deduplicação | §4.4 e §6: guardar o maior `updatedAt`, correlacionar por `policyId` |

## 2. Cursor durável

- Cursor persistido por CIA, com precisão de instante (`timestamptz`).
  `movimentos(desde: date)` precisa virar `datetime`.
- Guardar o cursor **apenas quando a varredura terminou inteira**. Repetir é
  seguro porque a projeção é idempotente (§4); pular não é.
- `updatedSince` é inclusivo (`>=`). Não compensar com um microssegundo a mais:
  isso perde registros que compartilham o mesmo `updatedAt`.
- **Confirmado (resposta 2):** mudança de status de cobrança move o `updatedAt`.
  A varredura enxerga pagamento, então a exportação pode alimentar comissão
  recebida sem outra fonte.

**Aceite:** varredura interrompida não avança o cursor; duas varreduras
seguidas sobre o mesmo intervalo produzem o mesmo estado final.

## 3. Paginação e falha parcial

- `take` máximo é 100 (§4.2) — o valor atual já está no limite.
- **Confirmado (resposta 3):** não há limite de janela e a carteira em produção
  tem **54 apólices**. A carga inicial cabe em uma página; não é preciso
  estratégia especial de primeira execução.
- Falha em qualquer página **aborta a varredura com erro**, em vez de devolver
  lista curta. O chamador precisa distinguir "acabou" de "parou no meio".
- Teto de páginas por varredura, para não girar se o serviço devolver sempre
  página cheia.

**Aceite:** teste com falha na segunda página falha a varredura inteira e
mantém o cursor onde estava.

## 4. Identidade e idempotência

- `policyId` é a chave estável (§6). `insurerPolicyNumber` **não** serve: é
  `null` enquanto não há documento emitido.
- A projeção é um *upsert* por `(cia, policyId)`, não um append.
- Registrar `updatedAt` junto e ignorar payload com `updatedAt` menor que o
  gravado.

**Aceite:** aplicar a mesma página duas vezes não cria segundo registro nem
segundo evento.

## 5. Estado e encerramento

- **Confirmado (resposta 1):** não existe campo com a causa do encerramento.
- Persistir `status` e `cancellationDate` como vieram.
- O evento canônico diz o que se sabe — "apólice encerrada" — e não o que se
  supõe — "cancelada". Isso pede um tipo novo em `MovimentoCanonico.tipo`, hoje
  limitado a `emissao|parcela|comissao|sinistro|cancelamento`.
- **Pendência nossa:** a seguradora perguntou se a falta do campo é bloqueante.
  Avaliação: **não bloqueia integrar**, porque registramos o estado bruto; mas
  **bloqueia automatizar** estorno de comissão e ação de retenção, que dependem
  de separar cancelamento de inadimplência. Decisão do responsável antes de
  responder.

**Aceite:** apólice `INACTIVE` não gera evento de cancelamento.

## 6. Vínculo de renovação

- **Corrigido (resposta 5):** `previousPolicyId` cobre apenas renovação **dentro
  da Justos** — apólice deles renovada com eles. Não é sobre canal de venda,
  como a documentação sugeria.
- Preenchido, confirma renovação de apólice Justos e deve ser gravado.
- `null` **não distingue** negócio novo de renovação de apólice de outra
  seguradora. Não inferir nada da ausência, e não há previsão de mudar.

**Aceite:** vínculo gravado quando presente; ausência não marca nada.

## 7. Ciclo mensal não é parcela anual

- Em apólice mensal **não existe parcelamento**: cada item de `installments` é a
  cobrança de um ciclo, e `number` é o número do ciclo (§5.7).
- `validUntil` em mensal é o fim da cobertura do ciclo vigente, não fim de
  vigência contratual.
- O calendário local de 30 em 30 dias é estimativa e **não pode** ser exibido ao
  lado da cobrança real nem sobrescrito sem leitura compatível.
- `status` da cobrança: `PAID`, `PENDING`, `FAILED`, `CANCELLED` ou `REFUNDED`.
  `paymentMethod`: `CARD` ou `PIX`. Não existe boleto.

**Aceite:** cobrança real e calendário estimado ficam distinguíveis na leitura.

## 8. Comissão e IOF

- **Corrigido (resposta 7):** a Justos aplica piso próprio quando a apólice
  anterior é dela, na criação da cotação, sem erro. A comissão volta na resposta
  e é ela que vale — assumir a enviada registra percentual errado.
- `commission.percentage` não é a razão entre `amount` e `grossPremium`, porque
  o bruto inclui IOF (§5.6). Não recalcular.
- Quando a cotação de origem não é mais resolvível, o campo cai na razão sobre o
  bruto — o valor pode mudar de significado sem aviso.
- `netPremium`, `grossPremium`, `iof` e `totalPremium` entram em `Decimal`.

**Aceite:** nenhum percentual de comissão é derivado de divisão local.

## 9. Documentos

- `policyPdfUrl` e `endorsementPdfUrl` são assinadas e **expiram em 15 minutos**.
  Baixar no momento da consulta; **nunca** persistir a URL.
- São documentos distintos: apólice/bilhete e comprovante do último endosso. Em
  mensal, o `policyPdfUrl` é o bilhete do ciclo mais recente.
- Guardar o arquivo exige decidir retenção e controle de acesso. **Fora do
  escopo deste plano.**

**Aceite:** nenhuma URL assinada aparece em banco, log ou payload de API.

## 10. Etapas

Com as respostas, o desenho está fechado. A ordem abaixo é a de execução; cada
etapa é um lote com gate próprio, como manda o plano da fase 5.

| # | Etapa | Depende de |
|---|---|---|
| 1 | Cursor por instante e varredura que falha em vez de devolver parcial (§2 e §3). Sem persistir apólice | — |
| 2 | Projeção idempotente por `policyId` (§4), ainda sem emitir evento de domínio | 1 |
| 3 | Estado e encerramento (§5), incluindo o tipo canônico novo | 2 · decisão sobre a resposta 1 |
| 4 | Vínculo de renovação por `previousPolicyId` (§6) | 2 |
| 5 | Cobranças reais e leitura compatível do calendário estimado (§7 e §8) | 2 |
| 6 | Documentos (§9), depois de decidir retenção | 5 |
| 7 | Agendamento **a cada hora** (resposta 4) — **só aqui a sincronização liga** | gate de fase |

As etapas 1 e 2 não tocam o domínio nem ligam nada: constroem a varredura e a
persistência com o agendador desligado. É o maior avanço possível sem o gate.

## 11. Em aberto

1. **Responder à seguradora** se a ausência do campo de causa do `INACTIVE` é
   bloqueante (§5).
2. **Layout em homologação:** acompanhar o changelog da documentação. Evitar
   amarrar o domínio a campos que ainda podem mudar.
3. Validade da cotação continua sem fonte: `validUntil` de J3 é vigência de
   **apólice**, não prazo de cotação. Não automatizar expiração antes de
   confirmação contratual.
