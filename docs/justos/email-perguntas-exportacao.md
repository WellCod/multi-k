# E-mail — perguntas sobre a exportação de apólices vendidas

> **Rascunho. Não enviado.** Confirme o destinatário antes de enviar: o contato
> registrado no projeto é `[e-mail do ponto focal]`, usado para a chave pública EC.
> As cinco perguntas vêm de [`plano-exportacao-incremental.md`](plano-exportacao-incremental.md)
> §11 e bloqueiam o desenho da importação automática.

---

**Para:** [ponto focal Justos]
**Assunto:** Integração [corretora] × Justos — dúvidas sobre `GET /brokers/policy/export`

---

Olá, [nome],

Aqui é a **[corretora]**. Nossa integração com a API de vocês já
cobre o fluxo de cotação em staging — autenticação ES256, cotação, pricing,
seleção de coberturas, proposta e checkout link.

Estamos agora desenhando a **importação automática das apólices vendidas**, a
partir da documentação de busca de apólices (Multicálculo, 19/08/2026). Antes de
implementar, temos cinco dúvidas que a documentação não resolve e que preferimos
confirmar com vocês a decidir por conta própria — em especial as duas primeiras,
que afetam como registramos encerramento e comissão.

---

## 1. Causa do encerramento em `status: INACTIVE`

A seção 4.3 diz que `INACTIVE` cobre "cancelamento (pelo segurado, pela corretora
ou pela Justos), inadimplência, ou fim de vigência sem renovação", e que não
significa, por si só, cancelamento pela corretora.

**Existe hoje, ou está previsto, algum campo que distinga esses casos?**

Sem essa distinção não conseguimos separar um cliente que cancelou de um que
ficou inadimplente ou de uma apólice que simplesmente chegou ao fim. A diferença
muda o tratamento de comissão, a fila de renovação e a ação comercial. Enquanto
não houver o campo, vamos registrar apenas "encerrada", sem inferir o motivo.

## 2. O que faz o `updatedAt` mudar

O `updatedAt` é o campo usado pelo filtro `updatedSince` e pela ordenação, e é
nele que baseamos o cursor de sincronização.

**O `updatedAt` da apólice é atualizado quando muda apenas o `status` de uma
cobrança em `installments` — por exemplo, de `PENDING` para `PAID` — ou só
quando muda algo da própria apólice?**

Se a mudança de cobrança não altera o `updatedAt`, a varredura incremental nunca
verá o pagamento, e precisaremos de outra fonte para conciliar comissão recebida.

## 3. Janela da carga inicial

A seção 4.2 orienta usar "uma data bem antiga" em `updatedSince` na primeira
carga.

**Há limite para essa janela? E, para a nossa corretora, qual a ordem de grandeza
de registros esperada na carga inicial?**

Precisamos dimensionar a primeira execução — se são centenas ou dezenas de
milhares de apólices, a estratégia de paginação e retomada muda.

## 4. Limite de requisições

**Existe limite de requisições por minuto (ou por hora) no
`GET /brokers/policy/export`?**

Nossa varredura será agendada e paginada. Queremos respeitar o limite desde o
início, em vez de descobri-lo sendo bloqueados.

## 5. Alcance do `previousPolicyId`

A documentação diz que o `previousPolicyId` vem preenchido nas renovações
originadas no canal de corretor/multicálculo, e que um valor preenchido confirma
renovação — mas `null` não prova que não houve apólice anterior por outro canal.

**Há previsão de preencher o `previousPolicyId` também em renovações originadas
fora desse canal?**

Se sim, preferimos aguardar e usar o campo direto, em vez de construir uma
heurística que depois precisaria ser desfeita.

---

Duas observações para contexto: todos os nossos testes até aqui usam respostas
sintéticas, sem nenhuma chamada real ao ambiente de vocês, e ainda não ligamos
nenhuma sincronização automática. Também registramos que as URLs de
`policyPdfUrl` e `endorsementPdfUrl` expiram em 15 minutos — nosso desenho baixa
o arquivo na hora da consulta e não armazena a URL.

Ficamos à disposição para uma conversa rápida, se for mais prático que responder
por escrito.

Atenciosamente,
**Weslley Gonçalves**
[corretora]
[e-mail do remetente]
