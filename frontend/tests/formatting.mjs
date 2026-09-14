import { build } from "esbuild";
import assert from "node:assert/strict";
import { test } from "node:test";

const compiled = await build({ entryPoints: ["src/lib/utils.ts"], bundle: true, write: false, platform: "node", format: "esm" });
const { formatDate, formatDatetime, formatBRL } = await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString("base64")}`);

test("datas de calendário e timestamps da API são aceitos", () => {
  assert.equal(formatDate("2026-09-11"), "11/09/2026");
  assert.equal(formatDate("2026-09-11T12:30:00-03:00"), "11/09/2026");
  assert.equal(formatDate("inválida"), "—");
  assert.equal(formatDate(null), "—");
  assert.equal(formatDatetime("inválida"), "—");
});

test("formatação monetária não perde centavos em valores grandes", () => {
  assert.equal(formatBRL("900719925474099.91"), "R$\u00a0900.719.925.474.099,91");
  assert.equal(formatBRL("0"), "R$\u00a00,00");
  assert.equal(formatBRL(null), "—");
  assert.equal(formatBRL("10.001"), "Valor com precisão inválida");
});
