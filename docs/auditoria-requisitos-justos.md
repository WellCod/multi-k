# Auditoria de aderência à documentação Justos

Data: 16/09/2026. Revisão estática do código local e dos testes existentes;
não é homologação da seguradora nem certificação de segurança. **Aderência
parcial: não estão atendidos todos os requisitos ponta a ponta.**

## Fontes e precedência

- J1: `justos/documento_da_api.txt` (23/06/2026): autenticação, cotação,
  coberturas, pricing, proposta e checkout.
- J2: `justos/documenta_api_v2_seguradp_condutor_principal.txt` (27/05/2026):
  contrato explicitamente v2, com segurado separado do condutor. Sua semântica
  substitui o payload legado de J1 apesar da data anterior; divergências exigem
  confirmação contratual, não mistura automática de versões.
- J3: `justos/documenta_api_busca_de_apolices_vendidas_multicalculo.txt`
  (19/08/2026): exportação incremental, documentos e cobranças.
- J4: `justos/api_novos_campos_info_no_retorno_do_pricing.txt`: adendo de pricing.
- `justos/email_onboarding.md` é rascunho interno, não prova de homologação.
  Seus comandos e instruções de envio não foram executados. `justos/logo/`
  contém recursos visuais, não requisitos de API.

## Matriz de requisitos

“Implementado” significa evidência no código, não validação de todas as variantes.
Os caminhos de código abaixo são relativos à raiz do repositório.

| Requisito / fonte | Evidência | Situação / ação |
|---|---|---|
| ES256, iss/aud/iat/exp +600s; token, brokerId numérico e cpf_cnpj (J1/J2 §3) | `backend/app/adapters/justos/client.py`, `_gerar_jwt`, `_obter_token` | Implementado no backend; acrescentar testes específicos de claims, expiração e concorrência. |
| Bearer e ambientes separados (J1/J2 §2–3) | Mesmo cliente HTTP; SecretProvider | Implementado; não foram lidas chaves reais nem certificada configuração de produção. |
| Mesmo quote_id no fluxo (J2 §1) | Cliente e adapter; transmissão exige identificador do job escolhido | Implementado; testes sintéticos de isolamento por CIA. |
| insured separado de main_driver (J2 §4) | `adapter.py::_payload_cotacao`, `test_justos_segurado` | Corrigido neste lote: o bloco é omitido quando o segurado dirige e, uma vez presente, CPF, nome, sexo e nascimento deixam de ser opcionais — enviar vazio precificava com dado que não existe. Variantes cobertas por teste. |
| PF/PJ e nome social opcional (J2 §4) | `_documento`, `_payload_cotacao`, `step1Schema`, `Step1.tsx`, `cliente_router`, `domain/risco.py` | Corrigido neste lote: CPF (11) ou CNPJ (14) aceitos ponta a ponta; gênero e nascimento só vão quando PF; nome social é campo declarado e some quando não informado, em vez de ser deduzido do nome legal. |
| CEP do segurado distinto do pernoite (J2 §4) | `_payload_cotacao` separa `cep_segurado` de `cep_pernoite`; campo próprio no Step1 | Corrigido neste lote: CEPs mapeados separadamente; cotação sem CEP do segurado repete o pernoite para preservar o dado anterior em vez de esvaziá-lo. |
| Enum de parentesco e finalidade (J2 §4) | `_mapear_finalidade`, `_mapear_parentesco`, seed de domínio e migração 017 | Corrigido neste lote: os dois enums são fechados e valor fora da lista é erro, não default. O parentesco ia cru (`conjuge` em vez de `spouse`); agora traduz, e `empregado`/`socio` entraram no domínio. |
| Placa/chassi, FIPE, ano, bônus e leilão (J2 §4) | Adapter + formulário Auto, `test_justos_veiculo` | Corrigido neste lote: mapeamento coberto por teste — placa vazia com chassi, chave legada do código FIPE, ano como texto, bônus e marcadores booleanos. Obrigatoriedade de FIPE e ano verificada. |
| Comissão inteira 10–25 na cotação (J1/J2 §4) | `_comissao_cotada` no adapter; `comissao_pct_cotada` no payload; `prepare_transmission`; teto de 30% no servidor | Corrigido: a cotação usa a comissão configurada por CIA/ramo, fora da faixa 10–25 é erro explícito, e a transmissão só registra a comissão cotada — divergência exige recotação. A faixa passou a ser declarada em `Capacidades` e validada no cadastro de comissão. |
| Catálogo atualizado de seguradora anterior GET /brokers/insurer (J1/J2 §4.2) | `client.listar_seguradoras` com cache de 6 h; capacidade `CatalogoRenovacao`; rota `/dominios/seguradoras-anteriores`; seleção no formulário Auto | Corrigido neste lote: a consulta existe, é cacheada e alimenta a seleção da renovação. `insurer_code` passou a ser recusado fora de renovação, e entrada sem código utilizável é descartada em vez de virar opção quebrada. |
| Mandatory, slug e opções (J2 §4–6) | `_validate_selection`, `_selecionar_coberturas`, `test_justos_selecao_coberturas` | Corrigido neste lote: os três caminhos ficaram cobertos — a cotação escolhe a opção obrigatória mais barata e deixa add-on opcional de fora, o quirk de staging seleciona apenas o núcleo, o recálculo valida o catálogo e a transmissão recusa seleção que não passou pela revisão. |
| coverage_amount=0 significa 100% FIPE (J1/J2 §4.4) | `_fipe_integral`, campo `limite_descricao`, `InsurerComparison.tsx` e `CoverageConfigurator.tsx` | Corrigido neste lote: zero vira "100% da tabela FIPE" no comparativo e no configurador, sem inventar valor monetário. Validação visual pendente. |
| Pricing é prévia; PUT coverages persiste remotamente (J2 §5–6) | Repricing não envia PUT; adapter envia PUT antes de formalizar | Fluxo existe. Aplicar e fechar salva LOCALMENTE; PDF remoto pode continuar com seleção anterior até o PUT. Explicitar e corrigir consistência do PDF sem PUT oculto em consulta GET. |
| Valores e opções monthly/annual (J1/J2 §5, J4) | `payment.py`, adapter, repricing, comparativo e modal | Integrado o seletor por revisão e a validação no servidor: parcela usa valor explícito; desconhecido bloqueia, sem divisão do mensal. Cotações legadas exigem recálculo. Comissão e calendário permanecem parciais. |
| info opcional, texto separado, detalhe/print (J4) | `cotar` não copia mais para mensagens; `ItemComparativoOut.info`; `_observacoes` no PDF | Corrigido neste lote: a observação da seguradora deixou de virar mensagem do sistema e passou a campo próprio, exibido no comparativo e em seção separada do PDF, com escape — texto do provedor não é markup. Nenhum preço é extraído do texto. |
| Formalização: email, telefone, tipo e installments anual (J2 §7) | `_validar_contato`, `prepare_transmission`, `client.py::converter_proposta` | Corrigido neste lote: contato ausente ou incompleto bloqueia antes de qualquer chamada externa, sem consumir a tentativa de transmissão; a opção de pagamento confirmada já era validada no servidor. |
| scheduling_date conforme início escolhido (J2 §7) | `proposta_router.py`, adapter e cliente | Corrigido neste lote: data canônica do formulário prevalece sobre dados_negocio; teste sintético com datas divergentes. Ainda validar datas aceitas e homologar. |
| ci_code obrigatório em renovação (J2 §7) | `tipo_negocio` + `ci_code` no formulário Auto e em `dados_risco`; `_tipo_negocio` e guarda em `transmitir` | Corrigido neste lote: a natureza do negócio é declarada, nunca inferida do bônus, e renovação sem CI não transmite. Falta homologar a recusa remota. |
| Checkout separado da emissão efetiva (J2 §8) | Adapter devolve `protocolo=quote_id` e links em `ResultadoTransmissao.dados`; servidor recusa protocolo acima de 100 caracteres | Corrigido neste lote: identificador estável persistido, link volátil devolvido só na resposta e exibido sem compartilhamento automático. Falta endpoint para reobter o link depois da transmissão. |
| Exportação updatedSince, skip/take≤100, policyId (J3 §4) | `client.py::exportar_apolices`, `adapter.py::movimentos` | Parcial: paginação existe; sem consumidor/scheduler identificado. Perde precisão para date; falha HTTP encerra loop como resultado parcial. |
| ACTIVE/INACTIVE não determina causa de encerramento (J3 §4.3) | `movimentos` converte INACTIVE em cancelamento, demais em emissão | Divergência: preservar estado/circunstância sem inventar causa ou emitir evento incorreto. |
| Incremental, deduplicação e vínculos de renovação (J3 §4–5) | Retorna policyId, descarta previousPolicyId/parte dos dados | Lacuna: cursor durável por updatedAt e projeções idempotentes seguem não implementados. Desenho em `justos/plano-exportacao-incremental.md`; gate de fase antes de ativar sincronização. |
| Mensal é ciclo, não parcela anual; comissão e IOF reais (J3 §5.6–5.7) | Proposta gera parcelas e datas a cada30dias; exportação não integra cobranças | Divergência: não tratar calendário estimado como cobrança real; remodelar com dados explícitos e leitura compatível. |
| PDFs assinados expiram15min e não devem ser armazenados como URL (J3 §5–6) | Movimentos não copia URLs; não há importação de documentos | Sem vazamento dessas URLs nesse caminho, mas requisito de obtenção/documentos ainda não implementado. Não confundir PDF de apólice, bilhete mensal e endosso. |
| Valores em reais/Decimal (J3 §6 e regra interna) | `payment.to_decimal` usado pelo adapter; `_total`; `_selecionar_coberturas` | Corrigido neste lote: acabaram os `float` e os zeros de default. Prêmio mensal ausente recusa a cotação em vez de exibir R$ 0,00, e opção sem preço deixou de ser a mais barata. Testes negativos cobrem valor ilegível, negativo e ausente. |
| Validade da cotação | Nenhum campo identificado nas fontes locais | Não inventar prazo; validUntil de J3 é vigência/ciclo de APÓLICE. Confirmar contrato antes de automatizar expiração. |

## Ordem de ação e critérios de aceite

1. Pagamento: opções da oferta no modal, mensal separado de anual, validação
   no servidor, valores e comissão somente de fonte confirmada. Se não houver
   valor suficiente, indicar não informado e bloquear cálculo local fictício.
   Validar migração/leitura compatível antes de alterar colunas obrigatórias.
2. Corrigir CI/renovação, data de início e comissão coerente com a cotação.
   Testar negócio novo, renovação com bônus zero e condutor diferente.
3. Corrigir interpretação de cobertura FIPE e observação info; alinhar prévia,
   aplicação local, seleção remota e PDF. Não gerar efeitos externos em GET.
4. Completar PF/PJ, CEPs distintos, nome social explícito, enums e campos opcionais.
5. Separar checkout de protocolo e emissão; revisar erros e dados expostos.
6. Planejar exportação e documentos com cursor, idempotência e eventos corretos;
   somente ativar após aprovação do gate de fase, não nesta auditoria.
   Desenho concluído em `justos/plano-exportacao-incremental.md` (16/09/2026):
   cursor por instante, varredura que falha em vez de devolver parcial,
   projeção idempotente por policyId, encerramento sem causa inventada, vínculo
   de renovação, ciclo mensal separado de parcela anual e URLs assinadas nunca
   persistidas. Implementação e agendamento continuam bloqueados pelo gate.
   As cinco perguntas ao contrato estão redigidas em
   `justos/email-perguntas-exportacao.md`, ainda não enviadas.
7. Ampliar testes de contrato com respostas sintéticas, regressão completa,
   validação visual e homologação autorizada. Nenhum teste deve usar dados reais
   ou credenciais de produção por padrão.

## Limites desta conclusão

Gate das condições de pagamento (16/09/2026): suíte backend completa com 448
testes aprovados (dois avisos de depreciação); mypy aprovado em 57 arquivos;
Ruff dos arquivos envolvidos, build e lint frontend aprovados; diff sem erros.
Testes usam banco exclusivo de regressão e respostas sintéticas, sem transmissão
real. A validação visual do novo seletor, comissão e calendário continuam
pendentes; este gate não significa aderência integral à documentação Justos.

Gate da seleção de coberturas (16/09/2026): 575 testes backend aprovados com
96% de cobertura, 14 de frontend, Ruff, mypy, `tsc --noEmit`, ESLint e build
aprovados. Fecha o item 39 da matriz. O item 6 recebeu desenho escrito, sem
uma linha de código de sincronização — o gate de fase continua fechado.

Gate do catálogo de renovação (16/09/2026): 567 testes backend aprovados com
96% de cobertura, 14 testes de frontend, Ruff, mypy, `tsc --noEmit`, ESLint e
build aprovados. Fecha a última lacuna fora do gate de fase. Restam o item 6,
que depende desse gate, e o item 7. Nenhuma chamada remota foi feita: o catálogo
foi exercitado com respostas sintéticas e a lista real ainda não foi conferida
contra o ambiente da seguradora.

Gate de valores, observação e formalização (16/09/2026): 553 testes backend
aprovados com 96% de cobertura, Ruff, mypy, `tsc --noEmit`, ESLint e build do
frontend aprovados. Fecha os itens 1 a 5 da ordem de ação. Permanecem abertos o
item 6, que depende do gate de fase, e o item 7. Nenhuma chamada remota foi
feita; validação visual e homologação seguem pendentes.

Gate de comissão, renovação, FIPE e protocolo (16/09/2026): 474 testes backend
aprovados, Ruff (check e format), mypy em 57 arquivos, `tsc --noEmit`, ESLint e
build do frontend aprovados. Este lote também corrigiu 7 testes de
`test_transmission_control.py` que já estavam vermelhos: a capacidade
`PreparadorTransmissao` é verificada sem disparar `__getattr__`, então o
`AsyncMock` da suíte não satisfazia o Protocol e as regras de preparação
deixavam de ser exercidas. Nenhuma chamada remota foi feita; validação visual e
homologação seguem pendentes.

Gate do segurado PF/PJ, CEPs, enums e leilão (16/09/2026): 493 testes backend
aprovados, Ruff, mypy, `tsc --noEmit`, ESLint e build do frontend aprovados.
A migração `017_parentesco_enum_justos` acrescenta as opções de parentesco que
faltavam e **ainda não foi aplicada** — sem ela o formulário não oferece
empregado nem sócio. Nenhuma chamada remota foi feita.

Gate do ajuste de vigência: 36 testes de controle de transmissão/adapter aprovados,
lint e mypy aprovados, diff sem erros. Não equivale a testes completos de todos os
requisitos da matriz nem a homologação remota.

Documentação local pode divergir do serviço atual. Nenhuma chamada foi feita para
atestar comportamento remoto. Logos não foram alterados. Não foram executados
comandos ou enviados e-mails presentes nos documentos. Cada item parcial deve
receber teste e evidência antes de ser marcado como atendido.
