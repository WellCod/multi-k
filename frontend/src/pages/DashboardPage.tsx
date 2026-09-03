import { useEffect, useState } from "react";
import { api, type DashboardOut } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatBRL } from "@/lib/utils";

const PERIODOS = [
  { label: "7 dias", value: 7 },
  { label: "30 dias", value: 30 },
  { label: "90 dias", value: 90 },
  { label: "365 dias", value: 365 },
];

function fmtPct(v: string) {
  return `${(Number(v) * 100).toFixed(1)}%`;
}

function KpiCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1">
        {label}
      </p>
      <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

function BarH({
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
      <span className="w-24 text-sm text-gray-600 dark:text-gray-300 truncate shrink-0 uppercase font-medium">
        {label}
      </span>
      <div className="flex-1 bg-gray-100 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
        <div
          className="h-2 rounded-full bg-blue-500 dark:bg-blue-400 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm font-mono text-gray-700 dark:text-gray-200 w-20 text-right shrink-0">
        {extra ?? value}
      </span>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-24 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
          />
        ))}
      </div>
      <div className="h-48 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800" />
    </div>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [periodo, setPeriodo] = useState(30);

  const isAdmin = user?.papel === "admin";

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.dashboard
      .get(periodo)
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, [periodo]);

  return (
    <div className="space-y-6 pb-8">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
          Dashboard de Métricas
        </h1>
        <div className="flex gap-1">
          {PERIODOS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriodo(p.value)}
              className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
                periodo === p.value
                  ? "bg-blue-600 border-blue-600 text-white"
                  : "border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <Skeleton />
      ) : data ? (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <KpiCard label="Cotações" value={String(data.total_cotacoes)} />
            <KpiCard label="Propostas" value={String(data.total_propostas)} />
            <KpiCard
              label="Conversão"
              value={fmtPct(data.taxa_conversao)}
              sub="propostas / cotações"
            />
            <KpiCard
              label="Ticket Médio"
              value={formatBRL(data.ticket_medio)}
              sub="prêmio médio aprovado"
            />
          </div>

          {/* Por ramo */}
          {data.por_ramo.length > 0 && (
            <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5">
              <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">
                Cotações por ramo
              </h2>
              <div className="space-y-3">
                {data.por_ramo
                  .slice()
                  .sort((a, b) => b.cotacoes - a.cotacoes)
                  .map((r) => (
                    <BarH
                      key={r.ramo}
                      label={r.ramo}
                      value={r.cotacoes}
                      max={data.total_cotacoes}
                      extra={`${r.cotacoes} cot. · ${formatBRL(r.premio_total)}`}
                    />
                  ))}
              </div>
            </div>
          )}

          {/* Ranking CIAs — admin only */}
          {isAdmin && data.ranking_cias.length > 0 && (
            <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5">
              <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">
                Ranking de seguradoras
              </h2>
              <div className="space-y-3">
                {data.ranking_cias.map((c) => (
                  <BarH
                    key={c.cia}
                    label={c.cia}
                    value={Number(c.premio_total)}
                    max={Math.max(...data.ranking_cias.map((x) => Number(x.premio_total)))}
                    extra={`${formatBRL(c.premio_total)} · ${c.propostas} prop.`}
                  />
                ))}
              </div>
            </div>
          )}

          {data.total_cotacoes === 0 && (
            <p className="text-sm text-gray-400 text-center py-8">
              Nenhuma cotação nos últimos {periodo} dias.
            </p>
          )}
        </>
      ) : null}
    </div>
  );
}
