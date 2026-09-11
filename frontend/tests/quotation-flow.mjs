import { build } from "esbuild";
import assert from "node:assert/strict";
import { test } from "node:test";

const compiled = await build({ entryPoints: ["src/pages/cotacao/types.ts"], bundle: true, write: false, platform: "node", format: "esm" });
const { riskStepSchemas, step4Schema } = await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString("base64")}`);

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

test("imóvel: dinheiro preservado exatamente ao salvar e voltar", () => {
  const data = { cep: "00000000", tipo_imovel: "TESTE", tipo_construcao: "TESTE", valor_imovel: "900.719.925.474.099,91" };
  const saved = riskStepSchemas.imovel.object.parse(data);
  assert.equal(saved.valor_imovel, "900719925474099.91");
  assert.deepEqual(riskStepSchemas.imovel.object.parse(saved), saved);
  assert.equal(riskStepSchemas.imovel.object.safeParse({ ...data, valor_imovel: "0" }).success, false);
  assert.equal(riskStepSchemas.imovel.object.safeParse({ ...data, valor_imovel: "1,001" }).success, false);
  assert.equal(riskStepSchemas.imovel.profile.safeParse({ alarme: true }).success, true);
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
