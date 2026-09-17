# E-mail — `convert-formal-quote` falhando em staging

> **Rascunho. Não enviado.** Destinatário: o ponto focal
> (`[e-mail do ponto focal]`). Evidência completa em
> [`prontidao-producao.md`](prontidao-producao.md) §3.
>
> O CPF usado não está escrito aqui de propósito. Se ele pedir, passar por
> canal direto, não no corpo do e-mail nem no repositório.

---

**Para:** [ponto focal Justos]
**Assunto:** Staging — `convert-formal-quote` retorna `failure_on_creating_user`

---

Olá, tudo bom?

Fechamos o E2E em staging e chegamos até a formalização. Duas boas notícias e um
bloqueio que precisa de vocês.

## O que passou

| Etapa | Resultado |
|---|---|
| Autenticação (JWT ES256) | ok |
| `POST /brokers/quote` | ok |
| `POST /pricing` | ok — mensal R$ 921,36, anual R$ 10.516,92 |
| `PUT /coverages` | **ok, HTTP 200** |

O `PUT /coverages` é justamente uma das chamadas que você não encontrou nos
nossos logs em 09/09. Ela está funcionando; o que faltava era a gente chegar até
lá com o fluxo completo.

## O bloqueio

O `convert-formal-quote` responde:

```
400 {"error":"failure_on_creating_user",
     "context":{"title":"Erro ao validar o CPF",
     "description":"Tivemos uma instabilidade temporária ao validar o CPF.
                    Tente novamente em instantes."}}
```

A mensagem sugere algo passageiro, mas não é o que observamos:

| Variação testada | Resultado |
|---|---|
| CPF sintético (dígitos válidos) — cotação `90f10912-cd87-4cd2-924b-9a8cabc823e7` | 400 |
| CPF de pessoa real, válido — cotação `214996d3-584b-473e-b8dd-bae4e078a944` | 400 |
| Mesma cotação, duas tentativas espaçadas em 30 segundos | 400 nas duas |
| Mesmo erro em 09/09/2026 | persiste há mais de uma semana |

Ou seja: **não depende do tipo de CPF, não é transitório, e as etapas anteriores
passam com exatamente os mesmos dados**. Por isso não parece ser o nosso payload.

## O que pedimos

Você se ofereceu a olhar pelo `quote_uuid` — os dois acima são de hoje e
reproduzem o erro. Dá para verificar do lado de vocês se é o serviço de criação
de usuário no staging, algum cadastro pendente da nossa corretora, ou outra
coisa?

Se precisar do CPF usado no segundo teste, me chama que passo direto.

## Por que isso trava a gente

O `convert-formal-quote` é o único passo do fluxo de venda que nunca rodou
contra a API de vocês. Antes de pedir produção, queremos o ciclo fechado em
staging — como você mesmo colocou, produção vocês confirmam antes de a gente
subir pra valer.

Abraço,
**Weslley Gonçalves**
[corretora]
[e-mail do remetente]
