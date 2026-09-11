import { DataTable } from "@/components/DataTable";
import { useEffect, useState } from "react";
import {
  api,
  type ComissoesResumoOut,
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
      className={`animate-pulse rounded border border-line bg-surface ${className}`}
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
      <span className="w-28 text-xs text-muted text-right capitalize truncate shrink-0">
        {label}
      </span>
      <div className="flex-1 h-5 bg-canvas rounded-full overflow-hidden">
        <div
          className="h-full bg-action rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-ink w-28 text-right shrink-0">
        <span className="font-semibold">{value}</span>
        {extra ? (
          <span className="text-muted ml-1">{extra}</span>
        ) : (
          <span className="text-muted ml-1">({pct}%)</span>
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
      <div className="py-8 text-center">
        <span className="text-xl">📋</span>
        <p className="text-sm text-muted mt-3">
          Sem propostas no período.
        </p>
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <DataTable className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-canvas border-b border-line text-left text-xs text-muted ">
            <th className="px-4 py-3">Corretor</th>
            <th className="px-4 py-3 text-right">Cotações</th>
            <th className="px-4 py-3 text-right">Propostas</th>
            <th className="px-4 py-3 text-right">Conversão</th>
            <th className="px-4 py-3 text-right">Prêmio total</th>
            <th className="px-4 py-3 text-right">Comissão prevista</th>
          </tr>
        </thead>
        <tbody>
          {dados.map((r) => (
            <tr
              key={r.corretor_id}
              className="border-b border-line hover:bg-canvas transition-colors"
            >
              <td className="px-4 py-3 font-medium text-ink ">{r.corretor_nome}</td>
              <td className="px-4 py-3 text-right text-ink ">{r.cotacoes}</td>
              <td className="px-4 py-3 text-right text-ink ">{r.propostas}</td>
              <td className="px-4 py-3 text-right text-ink ">{fmtPct(r.taxa_conversao)}</td>
              <td className="px-4 py-3 text-right font-mono text-ink ">{formatBRL(r.premio_total)}</td>
              <td className="px-4 py-3 text-right font-mono text-success ">
                {formatBRL(r.comissao_prevista)}
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
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
    <div className="rounded border border-line bg-canvas p-4 text-center flex flex-col items-center gap-1">
      <span className="text-xl">{icon}</span>
      <p className="text-xl font-bold text-ink mt-1">{value}</p>
      <p className="text-xs text-muted ">{label}</p>
    </div>
  );
}

function Funil({ dados }: { dados: FunilOut }) {
  const maxCots = Math.max(...dados.por_ramo.map((r) => r.cotacoes), 1);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <StatFunil icon="📊" label="Cotações" value={dados.total_cotacoes} />
        <StatFunil icon="📋" label="Com proposta" value={dados.total_com_proposta} />
        <StatFunil icon="📈" label="Conversão geral" value={fmtPct(dados.taxa_conversao_geral)} />
      </div>

      {dados.por_ramo.length > 0 ? (
        <div className="space-y-3">
          <p className="text-xs font-semibold text-muted uppercase tracking-wide">
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
          <p className="text-sm text-muted ">Sem dados por ramo.</p>
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
      <div className="py-8 text-center">
        <span className="text-xl">📂</span>
        <p className="text-sm text-muted mt-3">
          Sem propostas no período.
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-3">
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

function TabelaComissoes({ dados: resumo }: { dados: ComissoesResumoOut }) {
  const dados = resumo.itens;
  if (dados.length === 0) {
    return (
      <div className="py-8 text-center">
        <span className="text-xl">💰</span>
        <p className="text-sm text-muted mt-3">
          Sem comissões no período.
        </p>
      </div>
    );
  }
  const totalComissao = resumo.comissao_total;
  const totalPremio = resumo.premio_total;
  return (
    <div className="overflow-x-auto">
      <DataTable className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-canvas border-b border-line text-left text-xs text-muted ">
            <th className="px-4 py-3">Ramo</th>
            <th className="px-4 py-3 text-right">Propostas</th>
            <th className="px-4 py-3 text-right">Prêmio total</th>
            <th className="px-4 py-3 text-right">Comissão total</th>
          </tr>
        </thead>
        <tbody>
          {dados.map((r) => (
            <tr
              key={r.ramo}
              className="border-b border-line hover:bg-canvas transition-colors"
            >
              <td className="px-4 py-3 font-medium capitalize text-ink ">{r.ramo}</td>
              <td className="px-4 py-3 text-right text-ink ">{r.n_propostas}</td>
              <td className="px-4 py-3 text-right font-mono text-ink ">{formatBRL(r.premio_total)}</td>
              <td className="px-4 py-3 text-right font-mono text-success font-semibold">{formatBRL(r.comissao_total)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="bg-canvas border-t-2 border-line font-semibold text-xs text-muted ">
            <td className="px-4 py-3">Total</td>
            <td className="px-4 py-3 text-right">{dados.reduce((s, r) => s + r.n_propostas, 0)}</td>
            <td className="px-4 py-3 text-right font-mono">{formatBRL(String(totalPremio))}</td>
            <td className="px-4 py-3 text-right font-mono text-success ">{formatBRL(String(totalComissao))}</td>
          </tr>
        </tfoot>
      </DataTable>
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
  const [comissoes, setComissoes] = useState<ComissoesResumoOut | null>(null);
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
        <h1 className="text-xl font-semibold text-ink ">Relatórios</h1>
        <p className="text-sm text-muted mt-1">
          Análise de produção, funil e mix de ramos
        </p>
      </div>

      {/* Card de filtros */}
      <div className="rounded border border-line bg-surface p-4">
        <p className="text-xs font-semibold text-muted uppercase tracking-wide mb-3">
          Período
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {PERIODOS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriodo(p.value)}
              className={`px-3 py-2 text-xs rounded font-medium transition-colors ${
                periodo === p.value
                  ? "bg-action text-ink shadow-panel"
                  : "bg-canvas text-muted hover:bg-surface "
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
                className="border border-line rounded px-3 py-2 text-xs bg-surface text-ink focus:outline-none focus:ring-2 focus:ring-action"
              />
              <span className="text-xs text-muted">até</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="border border-line rounded px-3 py-2 text-xs bg-surface text-ink focus:outline-none focus:ring-2 focus:ring-action"
              />
            </div>
          )}
        </div>
      </div>

      {/* Erro */}
      {err && (
        <div className="rounded border border-line bg-canvas p-4 text-sm text-danger ">
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
            <div className="rounded border border-line bg-surface overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-line ">
                <h2 className="text-sm font-semibold text-ink ">
                  Produção por corretor
                </h2>
                <div className="flex gap-2">
                  <a
                    href={api.relatorios.exportUrl("producao", periodoParam, "csv", fromParam, toParam)}
                    className="inline-flex items-center gap-1 px-3 py-2 text-xs font-medium rounded border border-line text-ink bg-surface hover:bg-canvas transition-colors"
                  >
                    ↓ CSV
                  </a>
                  <a
                    href={api.relatorios.exportUrl("producao", periodoParam, "xlsx", fromParam, toParam)}
                    className="inline-flex items-center gap-1 px-3 py-2 text-xs font-medium rounded border border-line text-ink bg-surface hover:bg-canvas transition-colors"
                  >
                    ↓ XLSX
                  </a>
                </div>
              </div>
              {producao && <TabelaProducao dados={producao} />}
            </div>
          )}

          {/* Funil de conversão */}
          <div className="rounded border border-line bg-surface overflow-hidden">
            <div className="px-4 py-3 border-b border-line ">
              <h2 className="text-sm font-semibold text-ink ">
                Funil de conversão
              </h2>
            </div>
            <div className="p-4">
              {funil ? (
                <Funil dados={funil} />
              ) : (
                <div className="py-8 text-center">
                  <span className="text-xl">📊</span>
                  <p className="text-sm text-muted mt-3">
                    Sem dados no período.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Mix por ramo */}
          <div className="rounded border border-line bg-surface overflow-hidden">
            <div className="px-4 py-3 border-b border-line ">
              <h2 className="text-sm font-semibold text-ink ">
                Mix por ramo
              </h2>
            </div>
            <div className="p-4">
              {mix ? (
                <Mix dados={mix} />
              ) : (
                <div className="py-8 text-center">
                  <span className="text-xl">📂</span>
                  <p className="text-sm text-muted mt-3">
                    Sem dados no período.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Comissões por ramo */}
          <div className="rounded border border-line bg-surface overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-line ">
              <h2 className="text-sm font-semibold text-ink ">
                Comissões por ramo
              </h2>
              <a
                href={api.relatorios.comissoesExportUrl(periodoParam, fromParam, toParam)}
                className="inline-flex items-center gap-1 px-3 py-2 text-xs font-medium rounded border border-line text-ink bg-surface hover:bg-canvas transition-colors"
              >
                ↓ CSV
              </a>
            </div>
            {comissoes ? (
              <TabelaComissoes dados={comissoes} />
            ) : (
              <div className="py-8 text-center">
                <span className="text-xl">💰</span>
                <p className="text-sm text-muted mt-3">
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
