import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { KpiCard } from "@/components/KpiCard";
import {
  api,
  type HomeAdminOut,
  type HomeCorretorOut,
  type ItemCotacaoAbandonada,
  type ItemParcelaVencendo,
  type ItemPropostaParada,
  type ItemRenovacaoHome,
  type KpiCorretor,
  type KpiRamo,
} from "@/lib/api";
import { formatBRL, formatDate, formatDatetime } from "@/lib/utils";
import { Tooltip } from "@/components/Tooltip";
import { Button } from "@/components/ui/button";

// ---------------------------------------------------------------------------
// Shared — Skeleton
// ---------------------------------------------------------------------------

function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 ${className}`}
    />
  );
}

// ---------------------------------------------------------------------------
// Corretor — KPI mini cards
// ---------------------------------------------------------------------------

function MiniKpi({
  label,
  count,
  color,
}: {
  label: string;
  count: number;
  color: "red" | "amber" | "blue" | "gray";
}) {
  const colorMap = {
    red: "text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800",
    amber:
      "text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800",
    blue: "text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800",
    gray: "text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900/20 border-gray-200 dark:border-gray-700",
  };
  return (
    <div
      className={`rounded-xl border px-4 py-3 flex flex-col items-center gap-0.5 ${colorMap[color]}`}
    >
      <span className="text-2xl font-bold">{count}</span>
      <span className="text-xs font-medium text-center leading-tight">{label}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Corretor — seções da fila de trabalho
// ---------------------------------------------------------------------------

function SecaoRenovacoes({ items }: { items: ItemRenovacaoHome[] }) {
  const navigate = useNavigate();
  if (items.length === 0) return null;
  return (
    <section>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
        Renovações próximas ({items.length})
      </h2>
      <div className="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="bg-red-50 dark:bg-red-900/20 px-4 py-2 border-b border-red-100 dark:border-red-800">
          <p className="text-xs font-medium text-red-700 dark:text-red-400 uppercase tracking-wide">
            Atenção — requerem renovação em breve
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse bg-white dark:bg-gray-800">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-700 text-left text-xs text-gray-500 dark:text-gray-400">
                <th className="px-4 py-2.5">Protocolo</th>
                <th className="px-4 py-2.5">Ramo</th>
                <th className="px-4 py-2.5">Prêmio</th>
                <th className="px-4 py-2.5">Vigência até</th>
                <th className="px-4 py-2.5 text-center">Dias</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr
                  key={r.proposta_id}
                  className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/40 transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-xs text-gray-700 dark:text-gray-300">
                    {r.protocolo}
                  </td>
                  <td className="px-4 py-3 capitalize text-gray-900 dark:text-white">{r.ramo}</td>
                  <td className="px-4 py-3 text-gray-900 dark:text-white">{formatBRL(r.premio_total)}</td>
                  <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{formatDate(r.fim_vigencia)}</td>
                  <td className="px-4 py-3 text-center font-semibold">
                    <span
                      className={
                        r.dias_para_vencer <= 30
                          ? "text-red-700 dark:text-red-400"
                          : r.dias_para_vencer <= 45
                            ? "text-orange-600 dark:text-orange-400"
                            : "text-yellow-600 dark:text-yellow-400"
                      }
                    >
                      {r.dias_para_vencer}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Tooltip text="Abre nova cotação pré-preenchida para renovação desta apólice" position="top">
                      <button
                        className="text-xs px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-700 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 transition-colors whitespace-nowrap"
                        onClick={() => navigate(`/cotacao?recotar=${r.cotacao_id}`)}
                      >
                        Renovar
                      </button>
                    </Tooltip>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function SecaoPropostasParadas({ items }: { items: ItemPropostaParada[] }) {
  const navigate = useNavigate();
  if (items.length === 0) return null;
  return (
    <section>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
        Cotações sem proposta há 2+ dias ({items.length})
      </h2>
      <div className="space-y-2">
        {items.map((p) => (
          <div
            key={p.cotacao_id}
            className="flex items-center justify-between bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 border-l-4 border-l-amber-400 rounded-xl px-4 py-3 text-sm hover:shadow-sm transition-shadow"
          >
            <div>
              <span className="capitalize font-medium text-gray-900 dark:text-white">{p.ramo}</span>
              <span className="text-gray-400 dark:text-gray-500 text-xs ml-2">{formatDatetime(p.criado_em)}</span>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-gray-700 dark:text-gray-300 font-mono">{formatBRL(p.premio_total)}</span>
              <button
                className="text-xs px-2.5 py-1 rounded-lg bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-700 hover:bg-amber-100 dark:hover:bg-amber-900/50 transition-colors"
                onClick={() => navigate(`/cotacoes/${p.cotacao_id}/comparativo`)}
              >
                Ver
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function SecaoCotacoesAbandonadas({ items }: { items: ItemCotacaoAbandonada[] }) {
  const navigate = useNavigate();
  if (items.length === 0) return null;
  return (
    <section>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
        Cotações em processamento há 2+ dias ({items.length})
      </h2>
      <div className="space-y-2">
        {items.map((c) => (
          <div
            key={c.cotacao_id}
            className="flex items-center justify-between bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 border-l-4 border-l-blue-400 rounded-xl px-4 py-3 text-sm hover:shadow-sm transition-shadow"
          >
            <div>
              <span className="capitalize font-medium text-gray-900 dark:text-white">{c.ramo}</span>
              <span className="text-gray-400 dark:text-gray-500 text-xs ml-2">{formatDatetime(c.criado_em)}</span>
            </div>
            <Tooltip text="Retoma esta cotação incompleta para enviar à seguradora" position="top">
              <button
                className="text-xs px-2.5 py-1 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-700 hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
                onClick={() => navigate(`/cotacao?recotar=${c.cotacao_id}`)}
              >
                Continuar
              </button>
            </Tooltip>
          </div>
        ))}
      </div>
    </section>
  );
}

function SecaoParcelasVencendo({ items }: { items: ItemParcelaVencendo[] }) {
  if (items.length === 0) return null;
  return (
    <section>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
        Parcelas vencendo em 30 dias ({items.length})
      </h2>
      <div className="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse bg-white dark:bg-gray-800">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 text-left text-xs text-gray-500 dark:text-gray-400">
                <th className="px-4 py-2.5">Protocolo</th>
                <th className="px-4 py-2.5">Parcela</th>
                <th className="px-4 py-2.5">Vencimento</th>
                <th className="px-4 py-2.5 text-right">Valor</th>
                <th className="px-4 py-2.5 text-right">Comissão</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr
                  key={`${p.proposta_id}-${p.numero_parcela}`}
                  className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/40 transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-xs text-gray-700 dark:text-gray-300">
                    {p.protocolo}
                  </td>
                  <td className="px-4 py-3 text-gray-900 dark:text-white">{p.numero_parcela}ª</td>
                  <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{formatDate(p.vencimento)}</td>
                  <td className="px-4 py-3 text-right font-mono text-gray-900 dark:text-white">{formatBRL(p.valor)}</td>
                  <td className="px-4 py-3 text-right font-mono text-green-700 dark:text-green-400">{formatBRL(p.comissao)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function HomeCorretorSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="h-7 w-32 rounded-lg bg-gray-200 dark:bg-gray-700 animate-pulse" />
        <div className="h-9 w-28 rounded-lg bg-gray-200 dark:bg-gray-700 animate-pulse" />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonCard key={i} className="h-20" />
        ))}
      </div>
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonCard key={i} className="h-14" />
        ))}
      </div>
    </div>
  );
}

function HomeCorretor() {
  const [data, setData] = useState<HomeCorretorOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.home
      .corretor()
      .then(setData)
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Erro"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <HomeCorretorSkeleton />;
  if (err)
    return (
      <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-400">
        {err}
      </div>
    );
  if (!data) return null;

  const total =
    data.renovacoes.length +
    data.propostas_paradas.length +
    data.cotacoes_abandonadas.length +
    data.parcelas_vencendo.length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Minha fila</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Pendências que precisam da sua atenção hoje
          </p>
        </div>
        <Button onClick={() => navigate("/cotacao")}>Nova cotação</Button>
      </div>

      {total > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <MiniKpi label="Renovações" count={data.renovacoes.length} color="red" />
          <MiniKpi label="Sem proposta" count={data.propostas_paradas.length} color="amber" />
          <MiniKpi label="Em processamento" count={data.cotacoes_abandonadas.length} color="blue" />
          <MiniKpi label="Parcelas vencendo" count={data.parcelas_vencendo.length} color="gray" />
        </div>
      )}

      {total === 0 ? (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 py-20 text-center">
          <span className="text-4xl">🎉</span>
          <p className="text-base font-medium text-gray-700 dark:text-gray-200 mt-4">
            Nenhuma pendência no momento.
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Use o menu para iniciar uma nova cotação.
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          <SecaoRenovacoes items={data.renovacoes} />
          <SecaoPropostasParadas items={data.propostas_paradas} />
          <SecaoCotacoesAbandonadas items={data.cotacoes_abandonadas} />
          <SecaoParcelasVencendo items={data.parcelas_vencendo} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Admin — KPIs
// ---------------------------------------------------------------------------

function BarraHorizontal({
  items,
}: {
  items: { label: string; value: number; max: number }[];
}) {
  return (
    <div className="space-y-3">
      {items.map((item) => {
        const pct = item.max > 0 ? Math.round((item.value / item.max) * 100) : 0;
        return (
          <div key={item.label} className="flex items-center gap-3">
            <span className="w-28 text-xs text-gray-600 dark:text-gray-400 text-right capitalize truncate shrink-0">
              {item.label}
            </span>
            <div className="flex-1 h-5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 w-20 text-right shrink-0">
              {item.value} <span className="font-normal text-gray-400">({pct}%)</span>
            </span>
          </div>
        );
      })}
    </div>
  );
}

function HomeAdminSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-7 w-40 rounded-lg bg-gray-200 dark:bg-gray-700 animate-pulse" />
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonCard key={i} className="h-24" />
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <SkeletonCard className="h-48" />
        <SkeletonCard className="h-48" />
      </div>
    </div>
  );
}

function HomeAdmin() {
  const [data, setData] = useState<HomeAdminOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.home
      .admin()
      .then(setData)
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Erro"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <HomeAdminSkeleton />;
  if (err)
    return (
      <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-400">
        {err}
      </div>
    );
  if (!data) return null;

  const maxRamo = Math.max(...(data.por_ramo as KpiRamo[]).map((r) => r.count), 1);
  const maxCorretor = Math.max(...(data.por_corretor as KpiCorretor[]).map((c) => c.propostas), 1);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Visão geral</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Indicadores consolidados da carteira
          </p>
        </div>
        <button
          onClick={() => navigate("/dashboard")}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-indigo-200 dark:border-indigo-700 text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/20 hover:bg-indigo-100 dark:hover:bg-indigo-900/40 transition-colors"
        >
          Ver métricas detalhadas →
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard label="Segurados vigentes" value={data.segurados_vigentes} />
        <KpiCard label="Apólices vigentes" value={data.apolices_vigentes} />
        <KpiCard label="Cotações em andamento" value={data.cotacoes_em_andamento} />
        <KpiCard label="Prêmio líquido" value={formatBRL(data.premio_liquido)} />
        <KpiCard label="Comissão produzida" value={formatBRL(data.comissao_produzida)} />
        <KpiCard label="Comissão recebida" value={formatBRL(data.comissao_recebida)} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {data.por_ramo.length > 0 && (
          <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden">
            <div className="bg-indigo-50 dark:bg-indigo-900/20 px-4 py-3 border-b border-indigo-100 dark:border-indigo-800">
              <h2 className="text-sm font-semibold text-indigo-800 dark:text-indigo-200">
                Mix por ramo
              </h2>
            </div>
            <div className="p-4">
              <BarraHorizontal
                items={(data.por_ramo as KpiRamo[])
                  .sort((a, b) => b.count - a.count)
                  .map((r) => ({ label: r.ramo, value: r.count, max: maxRamo }))}
              />
            </div>
          </div>
        )}

        {data.por_corretor.length > 0 && (
          <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden">
            <div className="bg-emerald-50 dark:bg-emerald-900/20 px-4 py-3 border-b border-emerald-100 dark:border-emerald-800">
              <h2 className="text-sm font-semibold text-emerald-800 dark:text-emerald-200">
                Propostas por corretor
              </h2>
            </div>
            <div className="p-4">
              <BarraHorizontal
                items={(data.por_corretor as KpiCorretor[])
                  .sort((a, b) => b.propostas - a.propostas)
                  .map((c) => ({ label: c.nome, value: c.propostas, max: maxCorretor }))}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Página — despacha por papel
// ---------------------------------------------------------------------------

export function HomePage() {
  const { user } = useAuth();
  if (!user) return null;
  return user.papel === "admin" ? <HomeAdmin /> : <HomeCorretor />;
}
