import { build } from "esbuild";
import { createRequire } from "node:module";
import assert from "node:assert/strict";
import { test } from "node:test";

const compiled = await build({
  stdin: { contents: `
    import React from 'react';
    import { renderToStaticMarkup } from 'react-dom/server';
    import { InsurerResult } from './src/components/InsurerResult';
    import { InsurerComparison } from './src/components/InsurerComparison';
    export function render(items) {
      return renderToStaticMarkup(<><div>{items.map(item => <InsurerResult key={item.cia} result={item} />)}</div><InsurerComparison items={items} /></>);
    }
  `, resolveDir: process.cwd(), loader: "tsx" },
  bundle: true, write: false, platform: "node", format: "cjs",
});
const compiledModule = { exports: {} };
new Function("require", "module", "exports", compiled.outputFiles[0].text)(createRequire(import.meta.url), compiledModule, compiledModule.exports);
const { render } = compiledModule.exports;
const result = (status, index) => ({ cia: `seguradora-${index}`, status, premio_total: status === "sucesso" ? "1234.56" : null, necessita_vistoria: false, restricoes: [], mensagens: [], iniciado_em: "inválida" });

for (const states of [["sucesso"], ["sucesso", "restricao", "erro", "processando"], ["erro", "erro", "erro", "erro"], ["sucesso", "erro", "erro", "erro"]]) {
  test(`renderiza todas as seguradoras: ${states.join(", ")}`, () => {
    const html = render(states.map(result));
    assert.equal((html.match(/<article /g) || []).length, states.length);
    assert.ok(!html.includes("NaN"));
    assert.equal(html.includes("Consultando"), states.includes("processando"));
    if (states.includes("sucesso")) assert.ok(html.includes("1.234,56"));
    if (states.every(state => state === "erro")) assert.ok(!html.includes("Aguardando resultado"));
  });
}

test("cancelamento tem mensagem explícita sem simular carregamento", () => {
  const html = render([result("cancelado", 0)]);
  assert.ok(html.includes("Consulta cancelada"));
  assert.ok(!html.includes("Consultando"));
});

test("comparativo cresce para oito seguradoras sem perder colunas ou resultados", () => {
  const items = Array.from({ length: 8 }, (_, i) => ({
    ...result(i === 7 ? "processando" : "sucesso", i),
    nome: `Seguradora de teste ${i + 1}`,
    coberturas_comparaveis: [{ conceito_id: "danos", nome_canonico: "Danos materiais", nome_original: "Danos materiais", limite: "50000.00" }],
  }));
  const html = render(items);
  assert.equal((html.match(/<article /g) || []).length, 8);
  assert.equal((html.match(/scope="col"/g) || []).length, 9);
  for (const item of items) assert.ok(html.includes(item.nome));
  assert.ok(html.includes("50.000,00"));
  assert.ok(html.includes("Consultando"));
});

const base = (extra) => ({ cia: "justos", status: "sucesso", premio_total: "1234.56", necessita_vistoria: false, restricoes: [], mensagens: [], iniciado_em: "inválida", ...extra });

test("observação da seguradora não aparece duas vezes em cotação antiga", () => {
  const texto = "9% desconto pagando à vista.";
  // Antes da separação do campo, a observação era gravada dentro de mensagens.
  const html = render([base({ mensagens: [texto], info: texto })]);
  assert.equal(html.split(texto).length - 1, 1);
});

test("observação nova aparece rotulada quando não está nas mensagens", () => {
  const html = render([base({ info: "Franquia reduzida disponível." })]);
  assert.ok(html.includes("Observação da seguradora"));
  assert.ok(html.includes("Franquia reduzida disponível."));
});

test("cobertura de 100% da FIPE não vira R$ 0,00 nem traço", () => {
  const html = render([base({
    coberturas_comparaveis: [
      { conceito_id: "casco", nome_canonico: "Casco", nome_original: "Casco", limite: null, limite_descricao: "100% da tabela FIPE" },
    ],
  })]);
  assert.ok(html.includes("100% da tabela FIPE"));
  assert.ok(!html.includes("R$ 0,00"));
});
