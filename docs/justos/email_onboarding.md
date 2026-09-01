# E-mail de onboarding — Justos

> **Antes de enviar:** execute `scripts/gerar_chaves_ec.sh` e anexe o arquivo `public-key.pem` gerado.
> Nunca suba `private-key.pem` no repositório.

---

**Para:** [ponto focal Justos]
**Assunto:** Integração Klubi × Justos — chave pública EC + perguntas de staging

---

Olá, [nome],

Somos a **Klubi Corretora de Seguros**. Desenvolvemos uma plataforma própria de multicálculo e estamos prontos para a integração com a API da Justos (ramo Auto).

Nossa implementação já cobre o fluxo completo descrito na documentação v2:
autenticação ES256 → cotação → pricing → seleção de coberturas → proposta → checkout link.

**Anexamos neste e-mail a nossa chave pública EC** (`public-key.pem`), gerada com o comando indicado na documentação:

```bash
openssl ecparam -name prime256v1 -genkey -noout -out private-key.pem
openssl ec -in private-key.pem -pubout -out public-key.pem
```

Com ela, pedimos que nos forneçam:

| Campo | Uso na integração |
|---|---|
| `partner_name` | campo `iss` do JWT de autenticação |
| `brokerId` | campo `brokerId` no POST `/brokers/auth/api-token` |

O CNPJ da corretora que usaremos no campo `cpf_cnpj` é: **33.911.704/0001-75** (Klubi Corretora de Seguros Ltda.).

---

## Perguntas para staging

Além das credenciais, temos algumas dúvidas para validar o ambiente de staging
(`https://api.staging.justos.com.br`) antes de avançar para produção:

**1. Dados de teste**
A API de staging aceita qualquer CPF/placa/FIPE ou há dados de teste específicos
que devemos usar para simular uma cotação completa (cotação → proposta → checkout)?

**2. Fluxo de proposta em staging**
A chamada `POST /brokers/quote/convert-formal-quote` executa as validações de risco
reais (consulta Boa Vista, etc.) em staging? Ou o ambiente simula aprovação automática?

**3. `ci_code` em renovações**
Em casos de renovação, de onde o `ci_code` da apólice anterior deve vir?
É um campo retornado pelo endpoint `GET /brokers/policy/export` ou
precisa ser obtido de outra forma?

**4. Comissão mínima**
A documentação indica que `broker_commission_percentage` aceita valores de 10 a 25.
Há alguma restrição adicional por tipo de veículo ou cobertura no staging?

**5. Expiração do token de autorização**
A resposta de `POST /brokers/auth/api-token` retorna `expires_in`?
Nossa implementação usa cache de 60 minutos (conforme a documentação),
mas gostaríamos de confirmar se o campo `expires_in` está disponível para
controle mais preciso.

---

Ficamos à disposição para qualquer dúvida.
Assim que recebermos `partner_name` e `brokerId`, ativamos o ambiente de staging
e iniciamos os testes de paridade.

Atenciosamente,
**Weslley Gonçalves**
Klubi Corretora de Seguros
weslley.goncalves@klubi.com.br
