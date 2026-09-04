import { useEffect, useState } from "react";
import {
  api,
  type ComissaoRamoOut,
  type FunilOut,
  type MixOut,
  type ProducaoOut,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatBRL } from "@/lib/utils";

const PERIODOS = [
  { label: "15 dias", value: 15 },
  { label: "30 dias", value: 30 },
  { label: "90 dias", value: 90 },
  { label: "Personalizado", value: 0 },
];

function fmtPct(v: string) {
  return `${(Number(v) * 100).toFixed(1)}%`;
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 ${className}`}
    />
  );
}

function RelatoriosSkeleton() {
  return (
    <div className="space-y-4">
      <SkeletonCard className="h-32" />
      <SkeletonCard className="h-52" />
      <SkeletonCard className="h-44" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Barra horizontal aprimorada
// ---------------------------------------------------------------------------

function BarraH({
  label,
  value,
  max,
  extra,
}: {
  label: string;
  value: number;
  max: number;
  extra?: string;
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 text-xs text-gray-600 dark:text-gray-400 text-right capitalize truncate shrink-0">
        {label}
      </span>
      <div className="flex-1 h-5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-700 dark:text-gray-300 w-28 text-right shrink-0">
        <span className="font-semibold">{value}</span>
        {extra ? (
          <span className="text-gray-400 ml-1">{extra}</span>
        ) : (
          <span className="text-gray-400 ml-1">({pct}%)</span>
        )}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tabela de produção
// ---------------------------------------------------------------------------

function TabelaProducao({ dados }: { dados: ProducaoOut[] }) {
  if (dados.length === 0) {
    return (
      <div className="py-12 text-center">
        <span className="text-3xl">📋</span>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-3">
          Sem propostas no período.
        </p>
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 text-left text-xs text-gray-500 dark:text-gray-400">
            <th className="px-4 py-2.5">Corretor</th>
            <th className="px-4 py-2.5 text-right">Cotações</th>
            <th className="px-4 py-2.5 text-right">Propostas</th>
            <th className="px-4 py-2.5 text-right">Conversão</th>
            <th className="px-4 py-2.5 text-right">Prêmio total</th>
            <th className="px-4 py-2.5 text-right">Comissão prevista</th>
          </tr>
        </thead>
        <tbody>
          {dados.map((r) => (
            <tr
              key={r.corretor_id}
              className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/40 transition-colors"
            >
              <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{r.corretor_nome}</td>
              <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-300">{r.cotacoes}</td>
              <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-300">{r.propostas}</td>
              <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-300">{fmtPct(r.taxa_conversao)}</td>
              <td className="px-4 py-3 text-right font-mono text-gray-900 dark:text-white">{formatBRL(r.premio_total)}</td>
              <td className="px-4 py-3 text-right font-mono text-green-700 dark:text-green-400">
                {formatBRL(r.comissao_prevista)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Funil
// ---------------------------------------------------------------------------

function StatFunil({
  icon,
  label,
  value,
}: {
  icon: string;
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/40 p-5 text-center flex flex-col items-center gap-1">
      <span className="text-2xl">{icon}</span>
      <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{value}</p>
      <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
    </div>
  );
}

function Funil({ dados }: { dados: FunilOut }) {
  const maxCots = Math.max(...dados.por_ramo.map((r) => r.cotacoes), 1);
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-3">
        <StatFunil icon="📊" label="Cotações" value={dados.total_cotacoes} />
        <StatFunil icon="📋" label="Com proposta" value={dados.total_com_proposta} />
        <StatFunil icon="📈" label="Conversão geral" value={fmtPct(dados.taxa_conversao_geral)} />
      </div>

      {dados.por_ramo.length > 0 ? (
        <div className="space-y-2.5">
          <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            Por ramo
          </p>
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
      ) : (
        <div className="py-8 text-center">
          <p className="text-sm text-gray-400 dark:text-gray-500">Sem dados por ramo.</p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mix
// ---------------------------------------------------------------------------

function Mix({ dados }: { dados: MixOut[] }) {
  const maxCount = Math.max(...dados.map((d) => d.count), 1);
  if (dados.length === 0) {
    return (
      <div className="py-12 text-center">
        <span className="text-3xl">📂</span>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-3">
          Sem propostas no período.
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-2.5">
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

// ---------------------------------------------------------------------------
// Comissões por ramo
// ---------------------------------------------------------------------------

function TabelaComissoes({ dados }: { dados: ComissaoRamoOut[] }) {
  if (dados.length === 0) {
    return (
      <div className="py-12 text-center">
        <span className="text-3xl">💰</span>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-3">
          Sem comissões no período.
        </p>
      </div>
    );
  }
  const totalComissao = dados.reduce((s, r) => s + Number(r.comissao_total), 0);
  const totalPremio = dados.reduce((s, r) => s + Number(r.premio_total), 0);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 text-left text-xs text-gray-500 dark:text-gray-400">
            <th className="px-4 py-2.5">Ramo</th>
            <th className="px-4 py-2.5 text-right">Propostas</th>
            <th className="px-4 py-2.5 text-right">Prêmio total</th>
            <th className="px-4 py-2.5 text-right">Comissão total</th>
          </tr>
        </thead>
        <tbody>
          {dados.map((r) => (
            <tr
              key={r.ramo}
              className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/40 transition-colors"
            >
              <td className="px-4 py-3 font-medium capitalize text-gray-900 dark:text-white">{r.ramo}</td>
              <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-300">{r.n_propostas}</td>
              <td className="px-4 py-3 text-right font-mono text-gray-900 dark:text-white">{formatBRL(r.premio_total)}</td>
              <td className="px-4 py-3 text-right font-mono text-green-700 dark:text-green-400 font-semibold">{formatBRL(r.comissao_total)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="bg-gray-50 dark:bg-gray-700/50 border-t-2 border-gray-200 dark:border-gray-700 font-semibold text-xs text-gray-600 dark:text-gray-300">
            <td className="px-4 py-2.5">Total</td>
            <td className="px-4 py-2.5 text-right">{dados.reduce((s, r) => s + r.n_propostas, 0)}</td>
            <td className="px-4 py-2.5 text-right font-mono">{formatBRL(String(totalPremio))}</td>
            <td className="px-4 py-2.5 text-right font-mono text-green-700 dark:text-green-400">{formatBRL(String(totalComissao))}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Página principal
// ---------------------------------------------------------------------------

export function RelatoriosPage() {
  const { user } = useAuth();
  const isAdmin = user?.papel === "admin";
  const [periodo, setPeriodo] = useState(30);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [producao, setProducao] = useState<ProducaoOut[] | null>(null);
  const [funil, setFunil] = useState<FunilOut | null>(null);
  const [mix, setMix] = useState<MixOut[] | null>(null);
  const [comissoes, setComissoes] = useState<ComissaoRamoOut[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const fromParam = periodo === 0 ? dateFrom || undefined : undefined;
  const toParam = periodo === 0 ? dateTo || undefined : undefined;
  const periodoParam = periodo === 0 ? 30 : periodo;

  useEffect(() => {
    if (periodo === 0 && !dateFrom && !dateTo) return;
    setLoading(true);
    setErr(null);
    const requests = isAdmin
      ? Promise.all([
          api.relatorios.producao(periodoParam, fromParam, toParam),
          api.relatorios.funil(periodoParam, fromParam, toParam),
          api.relatorios.mix(periodoParam, fromParam, toParam),
          api.relatorios.comissoes(periodoParam, fromParam, toParam),
        ]).then(([p, f, m, c]) => {
          setProducao(p);
          setFunil(f);
          setMix(m);
          setComissoes(c);
        })
      : Promise.all([
          api.relatorios.funil(periodoParam, fromParam, toParam),
          api.relatorios.mix(periodoParam, fromParam, toParam),
          api.relatorios.comissoes(periodoParam, fromParam, toParam),
        ]).then(([f, m, c]) => {
          setFunil(f);
          setMix(m);
          setComissoes(c);
        });
    requests
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Erro"))
      .finally(() => setLoading(false));
  }, [periodo, dateFrom, dateTo, isAdmin, periodoParam, fromParam, toParam]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Relatórios</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
          Análise de produção, funil e mix de ramos
        </p>
      </div>

      {/* Card de filtros */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
        <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
          Período
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {PERIODOS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriodo(p.value)}
              className={`px-3 py-1.5 text-xs rounded-lg font-medium transition-colors ${
                periodo === p.value
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
              }`}
            >
              {p.label}
            </button>
          ))}
          {periodo === 0 && (
            <div className="flex items-center gap-2 ml-1">
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="border border-gray-300 dark:border-gray-600 rounded-lg px-2.5 py-1.5 text-xs bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-xs text-gray-400">até</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="border border-gray-300 dark:border-gray-600 rounded-lg px-2.5 py-1.5 text-xs bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}
        </div>
      </div>

      {/* Erro */}
      {err && (
        <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-400">
          {err}
        </div>
      )}

      {/* Skeleton durante loading */}
      {loading && <RelatoriosSkeleton />}

      {/* Conteúdo */}
      {!loading && !err && (
        <div className="space-y-6">
          {/* Produção por corretor — só admin */}
          {isAdmin && (
            <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-700">
                <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200">
                  Produção por corretor
                </h2>
                <div className="flex gap-2">
                  <a
                    href={api.relatorios.exportUrl("producao", periodoParam, "csv", fromParam, toParam)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
                  >
                    ↓ CSV
                  </a>
                  <a
                    href={api.relatorios.exportUrl("producao", periodoParam, "xlsx", fromParam, toParam)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
                  >
                    ↓ XLSX
                  </a>
                </div>
              </div>
              {producao && <TabelaProducao dados={producao} />}
            </div>
          )}

          {/* Funil de conversão */}
          <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
              <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200">
                Funil de conversão
              </h2>
            </div>
            <div className="p-4">
              {funil ? (
                <Funil dados={funil} />
              ) : (
                <div className="py-10 text-center">
                  <span className="text-3xl">📊</span>
                  <p className="text-sm text-gray-400 dark:text-gray-500 mt-3">
                    Sem dados no período.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Mix por ramo */}
          <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
              <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200">
                Mix por ramo
              </h2>
            </div>
            <div className="p-4">
              {mix ? (
                <Mix dados={mix} />
              ) : (
                <div className="py-10 text-center">
                  <span className="text-3xl">📂</span>
                  <p className="text-sm text-gray-400 dark:text-gray-500 mt-3">
                    Sem dados no período.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Comissões por ramo */}
          <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-700">
              <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200">
                Comissões por ramo
              </h2>
              <a
                href={api.relatorios.comissoesExportUrl(periodoParam, fromParam, toParam)}
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
              >
                ↓ CSV
              </a>
            </div>
            {comissoes ? (
              <TabelaComissoes dados={comissoes} />
            ) : (
              <div className="py-10 text-center">
                <span className="text-3xl">💰</span>
                <p className="text-sm text-gray-400 dark:text-gray-500 mt-3">
                  Sem dados no período.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
