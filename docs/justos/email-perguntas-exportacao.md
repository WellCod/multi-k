# E-mail — exportação de apólices e regras de renovação

> **Enviado e respondido em 17/09/2026.** As respostas estão consolidadas em
> [`plano-exportacao-incremental.md`](plano-exportacao-incremental.md) §0, e duas
> delas corrigiram código: o gatilho do `ci_code` e a origem da comissão
> gravada. Mantido como registro do que foi perguntado.
>
> **Rascunho original.** Destinatário: o ponto focal (`[e-mail do ponto focal]`),
> que respondeu as trocas anteriores. As perguntas da parte A vêm de
> [`plano-exportacao-incremental.md`](plano-exportacao-incremental.md) §11 e
> bloqueiam o desenho da importação automática; as da parte B saem de
> divergências entre a resposta dele de 02/09 e a documentação local.
>
> Conferido contra a troca de e-mails até 09/09/2026: nenhuma das perguntas da
> parte A foi respondida antes.

---

**Para:** o ponto focal — Justos
**Assunto:** Integração Klubi × Justos — exportação de apólices e regras de renovação

---

Olá, tudo bom?

Estamos desenhando a **importação automática das apólices vendidas**, a partir da
documentação de busca de apólices (Multicálculo, 19/08). Antes de implementar,
ficaram cinco dúvidas que a documentação não resolve, e mais duas sobre
renovação que surgiram do que você já nos passou.

Nada disso está ligado hoje — nenhuma varredura roda contra o ambiente de vocês.

---

## A. Exportação de apólices (`GET /brokers/policy/export`)

**1. Causa do encerramento em `status: INACTIVE`**

A seção 4.3 diz que `INACTIVE` cobre cancelamento (pelo segurado, pela corretora
ou por vocês), inadimplência e fim de vigência sem renovação — e que não
significa, por si só, cancelamento pela corretora.

Existe hoje, ou está previsto, algum campo que distinga esses casos?

Sem isso não conseguimos separar quem cancelou de quem ficou inadimplente ou de
uma apólice que só chegou ao fim. Muda tratamento de comissão, fila de renovação
e ação comercial. Enquanto não houver o campo, vamos registrar apenas
"encerrada", sem inferir motivo.

**2. O que faz o `updatedAt` mudar**

O `updatedAt` é o campo do filtro `updatedSince` e da ordenação, e é nele que
baseamos o cursor de sincronização.

Ele é atualizado quando muda apenas o `status` de uma cobrança em `installments`
— por exemplo, de `PENDING` para `PAID` — ou só quando muda algo da própria
apólice?

Se a mudança de cobrança não mexe no `updatedAt`, a varredura nunca vê o
pagamento, e precisaremos de outra fonte para conciliar comissão recebida.

**3. Janela e volume da carga inicial**

A seção 4.2 orienta usar "uma data bem antiga" na primeira carga. Há limite para
essa janela? E qual a ordem de grandeza de registros esperada para o brokerId
59764 em produção?

Já entendemos que staging tem banco separado e não traz as apólices que temos com
vocês, então a carga inicial de verdade só acontece em produção — por isso
queremos dimensioná-la antes.

**4. Limite de requisições**

Existe limite de requisições por minuto (ou por hora) nesse endpoint?

Nossa varredura será agendada e paginada. Preferimos respeitar o limite desde o
início a descobri-lo sendo bloqueados.

**5. Alcance do `previousPolicyId`**

A documentação diz que ele vem preenchido nas renovações originadas no canal de
corretor/multicálculo, e que valor preenchido confirma renovação — mas `null` não
prova que não houve apólice anterior por outro canal.

Há previsão de preenchê-lo também em renovações originadas fora desse canal?

Se sim, preferimos aguardar e usar o campo direto, em vez de montar uma
heurística que depois teria de ser desfeita.

---

## B. Renovação

**6. Quando o `ci_code` é obrigatório**

Você nos disse que o CI está no PDF da apólice e que é necessário nos casos em
que a classe de bônus é maior que 0.

Só para não errarmos a validação: a obrigatoriedade é disparada pelo **bônus
maior que 0**, independentemente de ser renovação, ou por ser **renovação**?

Perguntamos porque os dois casos existem separados: negócio novo com bônus
transferido de outro veículo, e renovação com bônus 0. Hoje exigimos o CI quando
o corretor declara renovação — se a regra de vocês é o bônus, ajustamos.

**7. Piso de 15% em renovação de outra corretora**

Você mencionou que a faixa de comissão vai de 0 a 25, com a exceção de renovação
de apólice que hoje pertence a outra corretora, que tem piso de 15%.

Como identificamos esse caso **antes** de enviar a cotação? Dá para deduzir pelo
`insurer_code` da seguradora anterior, ou é algo que só vocês enxergam no
cadastro?

Hoje não temos como saber a qual corretora pertence a apólice anterior, então não
conseguimos aplicar o piso na validação — a cotação só falharia na sua ponta.

---

Ficamos à disposição para uma call rápida, se for mais prático que responder por
escrito — em especial as duas primeiras, que devem depender de alguém que conheça
o modelo de dados.

Abraço,
**Weslley Gonçalves**
Klubi Corretora de Seguros
weslley.goncalves@klubi.com.br
