# Plano de ação — segurança e fluxo atual (fase 5)

Data: 14/09/2026. Escopo confirmado pelo responsável: manter fase 5; priorizar
o fluxo atual. Compartilhamento, lembretes e painel operacional ficam para uma
etapa posterior com requisitos definidos. Não há autorização para produção,
transmissões reais de teste ou mudança de fase.

## Regra de execução

Não existe garantia antecipada de zero regressões. Cada lote deve preservar os
contratos necessários, adicionar testes negativos e positivos e ter um gate
antes de continuar. Não aplicar migrações no banco em uso durante a validação.
Preservar alterações de logos e comparação já presentes no diretório.

## Passos e critérios de aceite

1. **Segurança de sessão e baseline** — remover sessão/IP dos logs; revogar
   sessões ao redefinir senha, desativar conta ou alterar papel; verificar conta
   e IP também na renovação; mostrar erro real de logout. Testar usuário válido,
   bloqueado, duas sessões do mesmo usuário e isolamento de outro usuário.
   Definir limite absoluto e inatividade explicitamente antes de mudar a política.
2. **Minimização e autorização** — resumo do histórico sem CPF/contato/endereço;
   detalhe preservado somente para proprietário; validar proprietário do cliente
   e versão anterior na criação. Cobrir acesso cruzado e contratos da interface.
3. **Transmissão consistente** — exigir resultado elegível da seguradora; tipar
   campos editáveis; preço, coberturas, plano e comissão validados no servidor;
   persistir revisão aceita. Testar com duas seguradoras com preços diferentes,
   mudança simultânea em outra aba e seleção inválida.
4. **Idempotência e recuperação** — persistir tentativa antes da chamada externa,
   chave única, estado de resultado incerto e reconciliação; não repetir chamadas
   ambíguas automaticamente. Testar concorrência, timeout e falha de commit.
5. **Banco e privacidade** — reproduzir RLS usando migrações reais e papel sem
   superusuário. Preparar migração de dados sensíveis com leitura compatível,
   backup e reversão; preservar busca por nome e índice cego. Não apenas alterar
   o tipo ORM sobre dados existentes. Revisar isolamento por empresa antes de
   qualquer oferta multiempresa.
6. **Concorrência e desempenho** — limitar tarefas e chamadas por seguradora;
   recuperar jobs interrompidos; publicar eventos após commit; testes concorrentes
   para o status agregado. Medir polling, exportação em lotes e planos SQL.
   Distribuição de eventos entre instâncias depende do gate de infraestrutura.
7. **UX e features do fluxo atual** — revisão antes de transmitir, validade vinda
   da seguradora (não inventar prazo), comparação de 2–4 opções equivalentes,
   unidades de preço/cobertura claras, nova tentativa somente de falhas seguras,
   rascunhos e erros acionáveis. Validar ambos os temas, teclado e toque.
8. **Regressão integrada** — lint, tipos, testes backend, build frontend; cenário
   isolado de login → cotação fake → comparação → proposta; integração Justos
   apenas mockada nesta execução. Homologação externa depende de autorização.
9. **Aderência à documentação Justos** — conferir todos os documentos de
   `docs/justos`, registrar requisito → código → teste → lacuna e priorizar
   correções. Matriz: [auditoria-requisitos-justos.md](auditoria-requisitos-justos.md).
   Não confundir implementação parcial com homologação. Exportação automática
   continua sujeita ao gate de fase; não avançar para E-Retorno por inferência.

## Estado desta execução

Atualização de 16/09/2026:

- Pagamento Justos integrado: o modal consulta as opções da revisão exibida,
  distingue ciclo mensal de anual e não usa o catálogo fixo para essa CIA.
  Condições sem valor de parcela/total são indisponíveis. Cotações legadas sem
  opções devem ser recalculadas, sem fallback para parcelas inventadas.
- Transmissão valida índice e quantidade da opção sob a revisão atual; define
  policy_type/installments a partir do servidor, usa o valor explícito da parcela
  e registra a condição completa na auditoria. Outros adapters preservados.
  Comissão local e calendário de vencimentos não foram homologados nem alterados
  neste lote; são pendências separadas, não valores confirmados pela seguradora.

- Auditoria documental Justos adicionada ao plano e executada estaticamente:
  aderência parcial, com lacunas de pagamento, renovação/CI, comissão, PF/PJ,
  CEPs, semântica FIPE, PDF, checkout e exportação. Fontes, evidências e prioridades
  registradas na matriz. Corrigido envio de inicio_vigencia para scheduling_date;
  não foram alteradas regras comerciais, ativada sincronização ou feitas chamadas reais.

- Condições de pagamento documentadas em `docs/justos/documento_da_api.txt`
  (monthly/annual.installments) e no adendo de pricing agora são normalizadas
  no adapter, preservadas ao aplicar revisão e retornadas pelo comparativo.
  Somente periodicidade, quantidade, valor explícito da parcela e total são
  expostos; nenhum valor é derivado do texto info ou calculado por divisão.
  Campo ausente ou inválido permanece nulo; legado sem opções retorna lista vazia.
- Gate deste lote: **75 testes específicos aprovados**, lint, mypy e diff limpos.
  Nenhuma chamada real. O seletor de pagamento e a persistência financeira da
  transmissão ainda precisam consumir essas condições; não estão concluídos.
  Não foi identificado campo de validade da cotação no contrato local consultado
  (validUntil da exportação de apólices não é validade de cotação).

- Transmissão compara, sob bloqueio da cotação, a revisão capturada ao abrir
  Revisar proposta com a oferta atual da seguradora. Mudança de preço ou cobertura
  impede envio antes da chamada externa; ausência de revisão também bloqueia
  seguradoras reais. Compatibilidade sem revisão mantida apenas para o simulador.
- Revisão propagada pelos dois comparativos e por Aplicar e fechar. O modal não
  troca silenciosamente a revisão exibida por uma mais recente. Alteração em outra
  seguradora não invalida a oferta selecionada; repetição idempotente preservada.
- Gate: **430 testes aprovados**, dois avisos de depreciação; lint backend,
  mypy (56 arquivos), build e lint frontend aprovados. Nenhuma chamada real ou
  transmissão externa. Validação visual do novo fluxo permanece pendente.
- Próximos itens: condições confirmadas de pagamento/validade, regularização de
  aceite externo sem registro local, recuperação de jobs e demais gates de banco.

Atualização de 15/09/2026:

- **Lote atual — revisão persistida de coberturas:** Recalcular permanece uma
  prévia sem gravação. Aplicar e fechar reconfirma os preços na seguradora,
  compara com os valores exibidos e a impressão da revisão original; grava
  seleção, valores mensal/anual e auditoria em uma transação. Revisão antiga,
  preço alterado ou transmissão registrada impedem aplicar. O lock de cotação
  impede aplicação simultânea à transmissão. Não há envio automático de proposta.
- Comparativo passa a recuperar a revisão salva; a transmissão usa essa seleção
  e rejeita substituição direta por coberturas diferentes em dados_negocio.
  Auditoria registra autor, empresa, seleção e revisões, sem risco ou credenciais.
- Validação atual: **425 testes aprovados**, dois avisos de depreciação;
  lint backend, mypy, build e lint frontend aprovados. Testes incluem prévia sem
  gravação, aplicação, preço alterado, revisão obsoleta, bloqueio por transmissão
  e envio simulado com seleção salva. Nenhuma chamada real à seguradora.
- Permanecem pendentes: validação visual deste botão, confirmação da revisão
  exibida ao transmitir a partir de outra aba e condições de pagamento/validade.
  A gravação mensal/anual não equivale a validar juros, parcelas ou comissão.
  Registros abaixo descrevem lotes anteriores e seus gates à época.

- Corrigida a origem do prêmio no registro da transmissão: usa o job da CIA
  selecionada, não o agregado de outra seguradora. Teste com duas CIAs e prêmios
  diferentes confirma valor e comissão locais. 43 testes de proposta/controle
  aprovados, lint e mypy aprovados. Não altera a semântica legada das parcelas;
  mensalidade versus anual parcelado e revisão persistida seguem pendentes.

- Transmissão exige resultado concluído e elegível da CIA selecionada, com
  identificador e prêmio próprios. Removido fallback para identificador agregado
  de outra seguradora. Rejeição ocorre antes de registrar tentativa externa.
  Neste lote, 42 testes de proposta/controle passaram, incluindo quatro novos
  casos negativos; lint, mypy e diff aprovados. A revisão financeira persistida
  e a origem dos valores das parcelas continuam pendentes. A suíte completa de
  416 testes abaixo corresponde ao lote anterior, não a esta alteração.

- Recálculo valida o catálogo armazenado da cotação: rejeita cobertura desconhecida,
  opção de outra cobertura, omissão de obrigatória e resultado não elegível antes
  de chamar a seguradora. Não inventa obrigatoriedade ausente no catálogo.
- Suíte completa reexecutada após os dois lotes de recálculo: **416 testes
  aprovados**, dois avisos de depreciação. Lint e mypy aprovados. Sem chamadas
  reais à seguradora, migrações ou transmissão. A validação acima pertence ao
  endpoint de recálculo; integração com a revisão persistida e transmissão
  permanece pendente.

- Recálculo: outras seguradoras não são mais encaminhadas à Justos. Valores
  ausentes, negativos, não finitos ou malformados são recusados com erro seguro,
  sem fabricar prêmio zero. Dezesseis testes específicos aprovados, sem chamada
  externa real. Este lote não conclui validação de coberturas, persistência da
  revisão nem cálculo de parcelas; a suíte completa foi reexecutada no lote
  seguinte, conforme registro acima.

- Finalização do multicálculo em transação separada, após gravar os jobs;
  serialização da agregação por cotação para conclusão concorrente consistente.
- Notificação somente após commit, com prêmio atualizado. Falha de commit não
  publica sucesso; repetição da agregação sem alteração não duplica a notificação.
- Logs de exceção do worker substituídos por códigos de falha sem corpo externo.
- Endpoint autenticado de status retorna cinco campos, sem carregar o JSON de
  risco na consulta SQL; o comparativo carrega o detalhe uma vez e usa o status
  nas atualizações seguintes.
- Suíte completa incluindo o controle de transmissão: 391 testes aprovados, com dois
  avisos de depreciação de dependências. Ruff e mypy aprovados; build e lint
  frontend aprovados na execução anterior. Validação autenticada da seção
  Histórico → Conferir transmissões concluída: lista carregada sem erro e sem
  pendências. Nenhuma transmissão ou liberação real foi realizada. Formulário
  preenchido, temas, toque e fluxo completo ainda não validados no navegador.
- Conflito local de duas APIs na porta 8000 resolvido com autorização: encerrada
  a instância Python antiga; Docker preservado. O proxy do frontend alcança agora
  o endpoint novo, que exige autenticação.
- Tentativa registrada na auditoria antes da chamada externa; resultado incerto
  bloqueia reenvio. Chave de idempotência, bloqueio por cotação e versão da
  conferência protegem contra duplicação e decisões concorrentes.
- Corretor responsável e administrador da mesma empresa podem conferir, sempre
  com auditoria de autor, justificativa e resultado. Liberação exige confirmação
  de não aceite na seguradora e não dispara envio automático. Aceite confirmado
  mantém bloqueio e não inventa proposta ou parcelas locais; regularização do
  registro financeiro continua pendente de contrato operacional.
- O controle usa registros append-only da tabela de auditoria existente, sem
  migração no banco em uso e sem guardar risco ou resposta bruta da seguradora.
  Testes cobrem isolamento, concorrência, repetição, falha de persistência após
  aceite externo e restauração do contexto RLS após commit.
- Migrações, transmissão real e deploy não executados.

- Implementados: logs de sessão sem identificadores/IP; revogação na mudança de
  senha/acesso; limite absoluto de oito horas confirmado pelo responsável;
  renovação com verificação de usuário/IP; logout com erro explícito;
  histórico com resumo do risco; validação de vínculos por proprietário;
  allowlist de cobertura; erros da Justos/PDF sem corpo bruto; logos locais;
  respostas autenticadas sem cache; correção de cabeçalhos CSRF na composição
  de requisições; mensagens de conflito contextualizadas.
- Worker limitado ao lote de cinco tarefas simultâneas por processo. Não equivale
  a um limite global entre múltiplas instâncias nem a recuperação de jobs.
- Acrescentados testes sintéticos de regressão, trava de banco exclusivo e
  remoção da latência artificial do simulador somente nos testes.
- Condição comercial confirmada: não inventar valores de parcelamento ou validade
  ausentes; mostrar ausência e exigir revisão. Implementação do fluxo pendente.
- Demais passos pendentes; nenhum deve ser considerado concluído por constar
  neste plano.
- Banco exclusivo de regressão: `multik_security_regression_20260914`.
- Não substituir o banco local `multik` pelos fixtures destrutivos do pytest.

## Decisões necessárias para evitar regressões comerciais

Evidência incremental de 16/09/2026 — condições de pagamento Justos: 448 testes
backend aprovados no banco exclusivo de regressão, com dois avisos de depreciação;
mypy (57 arquivos), Ruff dos arquivos envolvidos, build e lint frontend aprovados.
Diff sem erros. Sem transmissão real, migração no banco em uso ou deploy.
Validação visual do seletor novo, comissão e calendário ainda pendentes.

- Prazo absoluto confirmado: oito horas. Política adicional de inatividade pendente.
- Semântica de mensalidade recorrente versus prêmio anual parcelado; fonte
  canônica dos juros, descontos e parcelas na resposta de cada seguradora.
- Operação de consulta/reconciliação de transmissão aceita sem resposta local.
- Confirmado e implementado: corretor responsável e administrador da mesma
  empresa podem liberar após conferência explícita, sempre com auditoria.
- Origem contratual da validade por seguradora ainda precisa ser mapeada; na
  ausência, foi aprovado mostrar “não informado” e exigir revisão, sem inventar prazo.

Essas decisões não devem ser preenchidas por suposição nem com preços calculados
no navegador. Novas regras precisam de exemplos de contrato e testes de aceite.
