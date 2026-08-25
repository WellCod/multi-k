import { useEffect, useState } from "react";
import {
  api,
  type FunilOut,
  type MixOut,
  type ProducaoOut,
} from "@/lib/api";
import { formatBRL } from "@/lib/utils";

const PERIODOS = [
  { label: "15 dias", value: 15 },
  { label: "30 dias", value: 30 },
  { label: "90 dias", value: 90 },
];

function fmtPct(v: string) {
  return `${(Number(v) * 100).toFixed(1)}%`;
}

function BarraH({ label, value, max, extra }: {
  label: string;
  value: number;
  max: number;
  extra?: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 text-xs text-gray-600 dark:text-gray-400 text-right capitalize truncate shrink-0">
        {label}
      </span>
      <div className="flex-1 h-4 bg-gray-100 dark:bg-gray-700 rounded overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded"
          style={{ width: max > 0 ? `${(value / max) * 100}%` : "0%" }}
        />
      </div>
      <span className="text-xs text-gray-700 dark:text-gray-300 w-20 text-right shrink-0">
        {value}{extra ? ` ${extra}` : ""}
      </span>
    </div>
  );
}

function TabelaProducao({ dados }: { dados: ProducaoOut[] }) {
  if (dados.length === 0) {
    return <p className="text-sm text-gray-500 dark:text-gray-400">Sem propostas no período.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 text-left text-xs text-gray-500 dark:text-gray-400">
            <th className="px-3 py-2">Corretor</th>
            <th className="px-3 py-2 text-right">Cotações</th>
            <th className="px-3 py-2 text-right">Propostas</th>
            <th className="px-3 py-2 text-right">Conversão</th>
            <th className="px-3 py-2 text-right">Prêmio total</th>
            <th className="px-3 py-2 text-right">Comissão prevista</th>
          </tr>
        </thead>
        <tbody>
          {dados.map((r) => (
            <tr
              key={r.corretor_id}
              className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
            >
              <td className="px-3 py-2 font-medium text-gray-900 dark:text-white">{r.corretor_nome}</td>
              <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">{r.cotacoes}</td>
              <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">{r.propostas}</td>
              <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">{fmtPct(r.taxa_conversao)}</td>
              <td className="px-3 py-2 text-right font-mono text-gray-900 dark:text-white">{formatBRL(r.premio_total)}</td>
              <td className="px-3 py-2 text-right font-mono text-green-700 dark:text-green-400">
                {formatBRL(r.comissao_prevista)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Funil({ dados }: { dados: FunilOut }) {
  const maxCots = Math.max(...dados.por_ramo.map((r) => r.cotacoes), 1);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600 rounded p-3 text-center">
          <p className="text-2xl font-semibold text-gray-900 dark:text-white">{dados.total_cotacoes}</p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Cotações</p>
        </div>
        <div className="bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600 rounded p-3 text-center">
          <p className="text-2xl font-semibold text-gray-900 dark:text-white">{dados.total_com_proposta}</p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Com proposta</p>
        </div>
        <div className="bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600 rounded p-3 text-center">
          <p className="text-2xl font-semibold text-gray-900 dark:text-white">{fmtPct(dados.taxa_conversao_geral)}</p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Conversão geral</p>
        </div>
      </div>
      {dados.por_ramo.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Por ramo</p>
          {dados.por_ramo
            .sort((a, b) => b.cotacoes - a.cotacoes)
            .map((r) => (
              <BarraH
                key={r.ramo}
                label={r.ramo}
                value={r.cotacoes}
                max={maxCots}
                extra={`— ${fmtPct(r.taxa_conversao)} conv.`}
              />
            ))}
        </div>
      )}
    </div>
  );
}

function Mix({ dados }: { dados: MixOut[] }) {
  const maxCount = Math.max(...dados.map((d) => d.count), 1);
  if (dados.length === 0) {
    return <p className="text-sm text-gray-500 dark:text-gray-400">Sem propostas no período.</p>;
  }
  return (
    <div className="space-y-2">
      {dados
        .sort((a, b) => b.count - a.count)
        .map((d) => (
          <BarraH
            key={d.ramo}
            label={d.ramo}
            value={d.count}
            max={maxCount}
            extra={`(${Number(d.pct).toFixed(1)}%)`}
          />
        ))}
    </div>
  );
}

export function RelatoriosPage() {
  const [periodo, setPeriodo] = useState(30);
  const [producao, setProducao] = useState<ProducaoOut[] | null>(null);
  const [funil, setFunil] = useState<FunilOut | null>(null);
  const [mix, setMix] = useState<MixOut[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setErr(null);
    Promise.all([
      api.relatorios.producao(periodo),
      api.relatorios.funil(periodo),
      api.relatorios.mix(periodo),
    ])
      .then(([p, f, m]) => {
        setProducao(p);
        setFunil(f);
        setMix(m);
      })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Erro"))
      .finally(() => setLoading(false));
  }, [periodo]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Relatórios</h1>
        <div className="flex items-center gap-1">
          {PERIODOS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriodo(p.value)}
              className={`px-3 py-1.5 text-xs rounded transition-colors ${
                periodo === p.value
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <p className="text-sm text-gray-500 dark:text-gray-400">Carregando…</p>}
      {err && <p className="text-sm text-red-600">{err}</p>}

      {!loading && !err && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200">
                Produção por corretor
              </h2>
              <div className="flex gap-2">
                <a
                  href={api.relatorios.exportUrl("producao", periodo, "csv")}
                  className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                >
                  CSV
                </a>
                <a
                  href={api.relatorios.exportUrl("producao", periodo, "xlsx")}
                  className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                >
                  XLSX
                </a>
              </div>
            </div>
            {producao && <TabelaProducao dados={producao} />}
          </div>

          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
              Funil de conversão
            </h2>
            {funil && <Funil dados={funil} />}
          </div>

          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
              Mix por ramo
            </h2>
            {mix && <Mix dados={mix} />}
          </div>
        </div>
      )}
    </div>
  );
}
