import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type DashboardOut, type RenovacaoCount } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatBRL } from "@/lib/utils";
import { KpiCard } from "@/components/KpiCard";

const PERIODOS = [
  { label: "7 dias", value: 7 },
  { label: "30 dias", value: 30 },
  { label: "90 dias", value: 90 },
  { label: "365 dias", value: 365 },
];

function fmtPct(v: string) {
  return `${(Number(v) * 100).toFixed(1)}%`;
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
      <span className="w-24 text-sm text-muted truncate shrink-0 uppercase font-medium">
        {label}
      </span>
      <div className="flex-1 bg-canvas rounded-full h-2 overflow-hidden">
        <div
          className="h-2 rounded-full bg-action transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm font-mono text-ink w-20 text-right shrink-0">
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
            className="h-24 rounded border border-line bg-surface "
          />
        ))}
      </div>
      <div className="h-48 rounded border border-line bg-surface " />
    </div>
  );
}

const JANELA_STYLE = {
  D30: { bar: "bg-danger ", label: "≤ 30 dias", text: "text-danger " },
  D45: { bar: "bg-warning ", label: "31–45 dias", text: "text-warning " },
  D60: { bar: "bg-warning ", label: "46–60 dias", text: "text-warning " },
};

export function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [periodo, setPeriodo] = useState(30);
  const [renovCount, setRenovCount] = useState<RenovacaoCount | null>(null);

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

  useEffect(() => {
    api.renovacoes.count().then(setRenovCount).catch(() => undefined);
  }, []);

  return (
    <div className="space-y-6 pb-8">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-semibold text-ink ">
          Dashboard de Métricas
        </h1>
        <div className="flex gap-1">
          {PERIODOS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriodo(p.value)}
              className={`px-3 py-2 text-xs rounded border transition-colors ${
                periodo === p.value
                  ? "bg-action border-line text-ink"
                  : "border-line text-muted hover:bg-canvas "
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded border border-line bg-canvas p-4 text-sm text-danger ">
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

          {/* Renovações a vencer */}
          {renovCount && renovCount.total > 0 && (
            <div className="rounded border border-line bg-surface p-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-ink ">
                  Renovações a vencer (próximos 60 dias)
                </h2>
                <button
                  onClick={() => navigate("/renovacoes")}
                  className="text-xs text-action hover:underline"
                >
                  Ver todas →
                </button>
              </div>
              <div className="space-y-3">
                {(["D30", "D45", "D60"] as const).map((j) => {
                  const count = renovCount[j];
                  const style = JANELA_STYLE[j];
                  const pct = renovCount.total > 0 ? Math.round((count / renovCount.total) * 100) : 0;
                  return (
                    <div key={j} className="flex items-center gap-3">
                      <span className={`w-24 text-xs font-medium shrink-0 ${style.text}`}>
                        {style.label}
                      </span>
                      <div className="flex-1 bg-canvas rounded-full h-2 overflow-hidden">
                        <div
                          className={`h-2 rounded-full transition-all ${style.bar}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-sm font-mono text-ink w-10 text-right shrink-0">
                        {count}
                      </span>
                    </div>
                  );
                })}
              </div>
              <p className="mt-3 text-xs text-muted ">
                Total: {renovCount.total} apólice{renovCount.total !== 1 ? "s" : ""}
              </p>
            </div>
          )}

          {/* Por ramo */}
          {data.por_ramo.length > 0 && (
            <div className="rounded border border-line bg-surface p-4">
              <h2 className="text-sm font-semibold text-ink mb-4">
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
            <div className="rounded border border-line bg-surface p-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-ink ">
                  Ranking de seguradoras
                </h2>
                {data.ranking_truncado && (
                  <span className="text-xs text-warning bg-canvas border border-line rounded px-2 py-1">
                    Volume alto — dados parciais
                  </span>
                )}
              </div>
              <div className="space-y-3">
                {data.ranking_cias.map((c) => (
                  <div key={c.cia}>
                    <BarH
                      label={c.cia}
                      value={Number(c.barra_pct ?? "0")}
                      max={100}
                      extra={`${formatBRL(c.premio_total)} · ${c.propostas} prop.`}
                    />
                    {c.latencia_media_s !== null && (
                      <p className="text-xs text-muted ml-28 mt-1">
                        SLA médio: {c.latencia_media_s < 60
                          ? `${c.latencia_media_s}s`
                          : `${(c.latencia_media_s / 60).toFixed(1)}min`}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {data.total_cotacoes === 0 && (
            <p className="text-sm text-muted text-center py-8">
              Nenhuma cotação nos últimos {periodo} dias.
            </p>
          )}
        </>
      ) : null}
    </div>
  );
}
