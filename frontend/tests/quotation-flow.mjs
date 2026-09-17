import { build } from "esbuild";
import assert from "node:assert/strict";
import { test } from "node:test";

const compiled = await build({ entryPoints: ["src/pages/cotacao/types.ts"], bundle: true, write: false, platform: "node", format: "esm" });
const { riskStepSchemas, step4Schema, step1Schema, limitesNascimento } = await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString("base64")}`);

test("auto: objeto e perfil validados separadamente sem perder dados", () => {
  const object = riskStepSchemas.auto.object.parse({ codigo_fipe: "TESTE", cep_pernoite: "00000-000" });
  const profile = riskStepSchemas.auto.profile.parse({ ...object, finalidade: "TESTE" });
  assert.equal(profile.codigo_fipe, undefined);
  assert.equal({ ...object, ...profile }.codigo_fipe, "TESTE");
  assert.equal(riskStepSchemas.auto.profile.safeParse({}).success, false);
});

test("moto: dados salvos podem ser validados novamente ao voltar", () => {
  const saved = riskStepSchemas.moto.object.parse({ codigo_fipe: "TESTE", cep_pernoite: "00000000", cilindrada: "150", categoria: "TESTE" });
  assert.deepEqual(riskStepSchemas.moto.object.parse(saved), saved);
  assert.equal(riskStepSchemas.moto.profile.safeParse({ finalidade: "TESTE" }).success, true);
});

test("coberturas: exige seleção e vigência válida", () => {
  const data = { coberturas: ["TESTE"], plano_pagamento: "TESTE", inicio_vigencia: "2026-09-10", fim_vigencia: "2027-09-10" };
  assert.equal(step4Schema.safeParse(data).success, true);
  assert.equal(step4Schema.safeParse({ ...data, coberturas: [] }).success, false);
  assert.equal(step4Schema.safeParse({ ...data, fim_vigencia: data.inicio_vigencia }).success, false);
  assert.equal(step4Schema.safeParse({ ...data, inicio_vigencia: "2026-02-30" }).success, false);
  assert.equal(step4Schema.safeParse({ ...data, fim_vigencia: "inválida" }).success, false);
  assert.equal(step4Schema.safeParse({ ...data, inicio_vigencia: "2024-02-29" }).success, true);
  assert.equal(step4Schema.safeParse({ ...data, inicio_vigencia: "2025-02-29" }).success, false);
});

test("renovação: exige CI e não transforma seleção vazia em zero", () => {
  const base = { finalidade: "TESTE" };
  assert.equal(riskStepSchemas.auto.profile.safeParse({ ...base, tipo_negocio: "renovacao" }).success, false);

  const renovacao = riskStepSchemas.auto.profile.parse({ ...base, tipo_negocio: "renovacao", ci_code: "CI-1", insurer_code: "6467" });
  assert.equal(renovacao.ci_code, "CI-1");
  assert.equal(renovacao.insurer_code, 6467);

  const semSelecao = riskStepSchemas.auto.profile.parse({ ...base, tipo_negocio: "renovacao", ci_code: "CI-1", insurer_code: "" });
  assert.equal(semSelecao.insurer_code, undefined);
});

test("negócio novo: é o padrão e dispensa CI", () => {
  const novo = riskStepSchemas.auto.profile.parse({ finalidade: "TESTE" });
  assert.equal(novo.tipo_negocio, "novo");
  assert.equal(novo.ci_code, undefined);
});

const identidade = (extra) => ({ nome: "Fulano de Tal", cpf: "39937528801", ...extra });

test("nascimento: limites do input acompanham a regra do schema", () => {
  const { min, max } = limitesNascimento();
  const hoje = new Date();
  assert.match(min, /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(Number(max.slice(0, 4)), hoje.getFullYear());
  assert.equal(Number(min.slice(0, 4)), hoje.getFullYear() - 100);
});

test("nascimento: ano fora da faixa é recusado", () => {
  for (const data of ["275760-02-18", "1800-01-01", "0001-01-01"]) {
    assert.equal(step1Schema.safeParse(identidade({ data_nascimento: data })).success, false, data);
  }
});

test("nascimento: data futura é recusada", () => {
  const amanha = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  assert.equal(step1Schema.safeParse(identidade({ data_nascimento: amanha })).success, false);
});

test("nascimento: data plausível e campo vazio passam", () => {
  assert.equal(step1Schema.safeParse(identidade({ data_nascimento: "1990-05-10" })).success, true);
  assert.equal(step1Schema.safeParse(identidade({})).success, true);
});
