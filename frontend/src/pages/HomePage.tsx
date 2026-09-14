import { DataTable } from "@/components/DataTable";
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
      className={`animate-pulse rounded border border-line bg-surface ${className}`}
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
    red: "text-danger bg-canvas border-line ",
    amber:
      "text-warning bg-canvas border-line ",
    blue: "text-action bg-canvas border-line ",
    gray: "text-muted bg-canvas border-line ",
  };
  return (
    <div
      className={`rounded border px-4 py-3 flex flex-col items-center gap-1 ${colorMap[color]}`}
    >
      <span className="text-xl font-bold">{count}</span>
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
      <h2 className="text-sm font-semibold text-ink mb-3">
        Renovações próximas ({items.length})
      </h2>
      <div className="rounded border border-line overflow-hidden">
        <div className="bg-canvas px-4 py-2 border-b border-line ">
          <p className="text-xs font-medium text-danger uppercase tracking-wide">
            Atenção — requerem renovação em breve
          </p>
        </div>
        <div className="overflow-x-auto">
          <DataTable className="w-full text-sm border-collapse bg-surface ">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted ">
                <th className="px-4 py-3">Protocolo</th>
                <th className="px-4 py-3">Ramo</th>
                <th className="px-4 py-3">Prêmio</th>
                <th className="px-4 py-3">Vigência até</th>
                <th className="px-4 py-3 text-center">Dias</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr
                  key={r.proposta_id}
                  className="border-b border-line hover:bg-canvas transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-xs text-ink ">
                    {r.protocolo}
                  </td>
                  <td className="px-4 py-3 capitalize text-ink ">{r.ramo}</td>
                  <td className="px-4 py-3 text-ink ">{formatBRL(r.premio_total)}</td>
                  <td className="px-4 py-3 text-ink ">{formatDate(r.fim_vigencia)}</td>
                  <td className="px-4 py-3 text-center font-semibold">
                    <span
                      className={
                        r.dias_para_vencer <= 30
                          ? "text-danger "
                          : r.dias_para_vencer <= 45
                            ? "text-warning "
                            : "text-warning "
                      }
                    >
                      {r.dias_para_vencer}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Tooltip text="Abre nova cotação pré-preenchida para renovação desta apólice" position="top">
                      <button
                        className="text-xs px-3 py-1 rounded bg-canvas text-action border border-line hover:bg-canvas transition-colors whitespace-nowrap"
                        onClick={() => navigate(`/cotacao?recotar=${r.cotacao_id}`)}
                      >
                        Renovar
                      </button>
                    </Tooltip>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
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
      <h2 className="text-sm font-semibold text-ink mb-3">
        Cotações sem proposta há 2+ dias ({items.length})
      </h2>
      <div className="space-y-2">
        {items.map((p) => (
          <div
            key={p.cotacao_id}
            className="flex items-center justify-between bg-surface border border-line border-l-4 border-l-amber-400 rounded px-4 py-3 text-sm hover:shadow-panel transition-shadow"
          >
            <div>
              <span className="capitalize font-medium text-ink ">{p.ramo}</span>
              <span className="text-muted text-xs ml-2">{formatDatetime(p.criado_em)}</span>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-ink font-mono">{formatBRL(p.premio_total)}</span>
              <button
                className="text-xs px-3 py-1 rounded bg-canvas text-warning border border-line hover:bg-canvas transition-colors"
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
      <h2 className="text-sm font-semibold text-ink mb-3">
        Cotações em processamento há 2+ dias ({items.length})
      </h2>
      <div className="space-y-2">
        {items.map((c) => (
          <div
            key={c.cotacao_id}
            className="flex items-center justify-between bg-surface border border-line border-l-4 border-l-blue-400 rounded px-4 py-3 text-sm hover:shadow-panel transition-shadow"
          >
            <div>
              <span className="capitalize font-medium text-ink ">{c.ramo}</span>
              <span className="text-muted text-xs ml-2">{formatDatetime(c.criado_em)}</span>
            </div>
            <Tooltip text="Retoma esta cotação incompleta para enviar à seguradora" position="top">
              <button
                className="text-xs px-3 py-1 rounded bg-canvas text-action border border-line hover:bg-canvas transition-colors"
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
      <h2 className="text-sm font-semibold text-ink mb-3">
        Parcelas vencendo em 30 dias ({items.length})
      </h2>
      <div className="rounded border border-line overflow-hidden">
        <div className="overflow-x-auto">
          <DataTable className="w-full text-sm border-collapse bg-surface ">
            <thead>
              <tr className="bg-canvas border-b border-line text-left text-xs text-muted ">
                <th className="px-4 py-3">Protocolo</th>
                <th className="px-4 py-3">Parcela</th>
                <th className="px-4 py-3">Vencimento</th>
                <th className="px-4 py-3 text-right">Valor</th>
                <th className="px-4 py-3 text-right">Comissão</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr
                  key={`${p.proposta_id}-${p.numero_parcela}`}
                  className="border-b border-line hover:bg-canvas transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-xs text-ink ">
                    {p.protocolo}
                  </td>
                  <td className="px-4 py-3 text-ink ">{p.numero_parcela}ª</td>
                  <td className="px-4 py-3 text-ink ">{formatDate(p.vencimento)}</td>
                  <td className="px-4 py-3 text-right font-mono text-ink ">{formatBRL(p.valor)}</td>
                  <td className="px-4 py-3 text-right font-mono text-success ">{formatBRL(p.comissao)}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>
      </div>
    </section>
  );
}

function HomeCorretorSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="h-7 w-32 rounded bg-surface animate-pulse" />
        <div className="h-9 w-28 rounded bg-surface animate-pulse" />
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
      <div className="rounded border border-line bg-canvas p-4 text-sm text-danger ">
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
          <h1 className="text-xl font-semibold text-ink ">Minha fila</h1>
          <p className="text-sm text-muted mt-1">
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
        <div className="rounded border border-line bg-surface py-20 text-center">
          <span className="text-xl">🎉</span>
          <p className="text-base font-medium text-ink mt-4">
            Nenhuma pendência no momento.
          </p>
          <p className="text-sm text-muted mt-1">
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
            <span className="w-28 text-xs text-muted text-right capitalize truncate shrink-0">
              {item.label}
            </span>
            <div className="flex-1 h-5 bg-canvas rounded-full overflow-hidden">
              <div
                className="h-full bg-action rounded-full transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs font-semibold text-ink w-20 text-right shrink-0">
              {item.value} <span className="font-normal text-muted">({pct}%)</span>
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
      <div className="h-7 w-40 rounded bg-surface animate-pulse" />
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
      <div className="rounded border border-line bg-canvas p-4 text-sm text-danger ">
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
          <h1 className="text-xl font-semibold text-ink ">Visão geral</h1>
          <p className="text-sm text-muted mt-1">
            Indicadores consolidados da carteira
          </p>
        </div>
        <button
          onClick={() => navigate("/dashboard")}
          className="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded border border-line text-action bg-canvas hover:bg-canvas transition-colors"
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
          <div className="rounded border border-line bg-surface overflow-hidden">
            <div className="bg-canvas px-4 py-3 border-b border-line ">
              <h2 className="text-sm font-semibold text-action ">
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
          <div className="rounded border border-line bg-surface overflow-hidden">
            <div className="bg-canvas px-4 py-3 border-b border-line ">
              <h2 className="text-sm font-semibold text-success ">
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
