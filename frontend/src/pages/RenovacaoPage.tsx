import { DataTable } from "@/components/DataTable";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type CotacaoCriada, type Renovacao } from "@/lib/api";
import { Tooltip } from "@/components/Tooltip";
import { formatBRL, formatDate } from "@/lib/utils";

const JANELA_CONFIG = {
  D30: {
    label: "≤ 30 dias",
    headerBg: "bg-canvas ",
    headerText: "text-danger ",
    border: "border-line ",
    badgeColor:
      "bg-canvas text-danger border-line ",
    countText: "text-danger ",
  },
  D45: {
    label: "31–45 dias",
    headerBg: "bg-canvas ",
    headerText: "text-warning ",
    border: "border-line ",
    badgeColor:
      "bg-canvas text-warning border-line ",
    countText: "text-warning ",
  },
  D60: {
    label: "46–60 dias",
    headerBg: "bg-canvas ",
    headerText: "text-warning ",
    border: "border-line ",
    badgeColor:
      "bg-canvas text-warning border-line ",
    countText: "text-warning ",
  },
};

type Janela = keyof typeof JANELA_CONFIG;

function DiasBadge({ dias, janela }: { dias: number; janela: Janela }) {
  const cfg = JANELA_CONFIG[janela];
  return (
    <span
      className={`inline-flex items-center justify-center rounded border px-2 py-1 text-xs font-semibold tabular-nums ${cfg.badgeColor}`}
    >
      {dias}d
    </span>
  );
}

function SkeletonGroupCard() {
  return (
    <div className="rounded border border-line overflow-hidden animate-pulse">
      <div className="px-4 py-3 bg-canvas flex items-center justify-between">
        <div className="h-4 w-24 rounded bg-surface " />
        <div className="h-4 w-16 rounded bg-surface " />
      </div>
      <div className="divide-y divide-line ">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="px-4 py-3 flex items-center gap-4">
            <div className="h-3 w-28 rounded bg-surface " />
            <div className="h-3 w-16 rounded bg-surface " />
            <div className="h-3 w-24 rounded bg-surface " />
            <div className="h-3 w-20 rounded bg-surface " />
            <div className="ml-auto h-6 w-14 rounded bg-surface " />
          </div>
        ))}
      </div>
    </div>
  );
}

function GrupoCard({
  janela,
  grupo,
  selecionadas,
  onToggle,
}: {
  janela: Janela;
  grupo: Renovacao[];
  selecionadas: Set<string>;
  onToggle: (cotacaoId: string) => void;
}) {
  const navigate = useNavigate();
  const cfg = JANELA_CONFIG[janela];

  return (
    <div className={`rounded border ${cfg.border} overflow-hidden`}>
      {/* Header colorido do grupo */}
      <div className={`flex items-center justify-between px-4 py-3 ${cfg.headerBg}`}>
        <span className={`text-sm font-semibold ${cfg.headerText}`}>
          {cfg.label}
        </span>
        <span className={`text-xs font-medium ${cfg.countText}`}>
          {grupo.length} apólice{grupo.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Tabela interna */}
      <div className="bg-surface overflow-x-auto">
        <DataTable className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-canvas text-left text-xs font-semibold text-muted uppercase tracking-wide">
              <th className="px-3 py-3 w-8" />
              <th className="px-4 py-3">Protocolo</th>
              <th className="px-4 py-3">Ramo</th>
              <th className="px-4 py-3">Prêmio</th>
              <th className="px-4 py-3">Vigência até</th>
              <th className="px-4 py-3 text-center">Dias</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {grupo.map((r) => (
              <tr
                key={r.proposta_id}
                className={`border-b border-line transition-colors ${
                  selecionadas.has(r.cotacao_id)
                    ? "bg-canvas "
                    : "hover:bg-canvas "
                }`}
              >
                <td className="px-3 py-3">
                  <input
                    type="checkbox"
                    checked={selecionadas.has(r.cotacao_id)}
                    onChange={() => onToggle(r.cotacao_id)}
                    className="rounded border-line text-action focus:ring-action"
                    aria-label={`Selecionar ${r.protocolo}`}
                  />
                </td>
                <td className="px-4 py-3 font-mono text-xs text-ink ">
                  {r.protocolo}
                </td>
                <td className="px-4 py-3 capitalize text-ink ">
                  {r.ramo}
                </td>
                <td className="px-4 py-3 text-ink tabular-nums">
                  {formatBRL(r.premio_total)}
                </td>
                <td className="px-4 py-3 text-ink ">
                  {formatDate(r.fim_vigencia)}
                </td>
                <td className="px-4 py-3 text-center">
                  <DiasBadge dias={r.dias_para_vencer} janela={janela} />
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-2 justify-end">
                    {r.cliente_id && (
                      <button
                        className="text-xs px-3 py-1 rounded border border-line text-muted hover:bg-canvas transition-colors whitespace-nowrap"
                        onClick={() => navigate(`/clientes/${r.cliente_id}`)}
                      >
                        Ver cliente
                      </button>
                    )}
                    <Tooltip
                      text="Abre nova cotação pré-preenchida para renovação"
                      position="top"
                    >
                      <button
                        className="text-xs px-3 py-1 rounded border border-line text-action hover:bg-canvas transition-colors whitespace-nowrap"
                        onClick={() =>
                          navigate(`/cotacao?recotar=${r.cotacao_id}`)
                        }
                      >
                        Renovar
                      </button>
                    </Tooltip>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      </div>
    </div>
  );
}

const SELECT_CLS =
  "rounded border border-line bg-surface text-sm text-ink px-3 py-2 focus:outline-none focus:ring-2 focus:ring-action ";

export function RenovacaoPage() {
  const navigate = useNavigate();
  const [renovacoes, setRenovacoes] = useState<Renovacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [ramo, setRamo] = useState("");
  const [janela, setJanela] = useState("");
  const [csvLoading, setCsvLoading] = useState(false);
  const [selecionadas, setSelecionadas] = useState<Set<string>>(new Set());
  const [loteLoading, setLoteLoading] = useState(false);
  const [loteResultado, setLoteResultado] = useState<CotacaoCriada[] | null>(null);

  useEffect(() => {
    setLoading(true);
    api.renovacoes
      .list(60, ramo || undefined, janela || undefined)
      .then(setRenovacoes)
      .catch((e: unknown) =>
        setErr(e instanceof Error ? e.message : "Erro ao carregar renovações"),
      )
      .finally(() => setLoading(false));
    setSelecionadas(new Set());
  }, [ramo, janela]);

  const grouped = {
    D30: renovacoes.filter((r) => r.janela === "D30"),
    D45: renovacoes.filter((r) => r.janela === "D45"),
    D60: renovacoes.filter((r) => r.janela === "D60"),
  };

  const total = renovacoes.length;

  const handleToggle = (cotacaoId: string) => {
    setSelecionadas((prev) => {
      const next = new Set(prev);
      next.has(cotacaoId) ? next.delete(cotacaoId) : next.add(cotacaoId);
      return next;
    });
  };

  const handleSelecionarTodas = () => {
    if (selecionadas.size === renovacoes.length) {
      setSelecionadas(new Set());
    } else {
      setSelecionadas(new Set(renovacoes.map((r) => r.cotacao_id)));
    }
  };

  const handleRecotarLote = async () => {
    if (selecionadas.size === 0) return;
    setLoteLoading(true);
    try {
      const resultado = await api.cotacoes.recotarLote([...selecionadas]);
      setLoteResultado(resultado);
      setSelecionadas(new Set());
    } catch {
      // silently ignore
    } finally {
      setLoteLoading(false);
    }
  };

  const handleExportCsv = async () => {
    setCsvLoading(true);
    try {
      const blob = await api.renovacoes.exportCsv(60, ramo || undefined, janela || undefined);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "renovacoes.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // silently ignore — user can retry
    } finally {
      setCsvLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink ">
            Renovações
          </h1>
          {!loading && !err && total > 0 && (
            <p className="text-sm text-muted mt-1">
              {total} apólice{total !== 1 ? "s" : ""} vencem nos próximos 60 dias
            </p>
          )}
        </div>

        {/* Filtros + CSV */}
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={ramo}
            onChange={(e) => setRamo(e.target.value)}
            aria-label="Filtrar por ramo"
            className={SELECT_CLS}
          >
            <option value="">Todos os ramos</option>
            <option value="auto">Auto</option>
            <option value="imovel">Imóvel</option>
          </select>

          <select
            value={janela}
            onChange={(e) => setJanela(e.target.value)}
            aria-label="Filtrar por janela"
            className={SELECT_CLS}
          >
            <option value="">Todas as janelas</option>
            <option value="D30">≤ 30 dias</option>
            <option value="D45">31–45 dias</option>
            <option value="D60">46–60 dias</option>
          </select>

          <button
            onClick={handleExportCsv}
            disabled={csvLoading || loading}
            className="inline-flex items-center gap-2 rounded border border-line bg-surface px-3 py-2 text-sm text-ink hover:bg-canvas disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {csvLoading ? (
              <span className="h-3.5 w-3.5 rounded-full border-2 border-line border-t-transparent animate-spin" />
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
            )}
            Exportar CSV
          </button>
        </div>
      </div>

      {/* Erro */}
      {err && (
        <div className="rounded border border-line bg-canvas p-4 text-sm text-danger ">
          {err}
        </div>
      )}

      {/* Skeleton de loading: 3 cards de grupo */}
      {loading && (
        <div className="space-y-4">
          <SkeletonGroupCard />
          <SkeletonGroupCard />
          <SkeletonGroupCard />
        </div>
      )}

      {/* Empty state */}
      {!loading && !err && total === 0 && (
        <div className="rounded border border-line bg-surface py-16 text-center">
          <p className="text-xl mb-3">📋</p>
          <p className="text-sm font-medium text-ink ">
            Nenhuma apólice encontrada
          </p>
          <p className="text-xs text-muted mt-1">
            {ramo || janela
              ? "Tente remover os filtros aplicados"
              : "Volte mais tarde para acompanhar os vencimentos"}
          </p>
        </div>
      )}

      {/* Barra de seleção em lote */}
      {!loading && !err && total > 0 && (
        <div className="flex flex-wrap items-center gap-3 px-1">
          <button
            onClick={handleSelecionarTodas}
            className="text-xs text-muted hover:text-ink underline"
          >
            {selecionadas.size === renovacoes.length ? "Desmarcar todas" : "Selecionar todas"}
          </button>
          {selecionadas.size > 0 && (
            <button
              onClick={handleRecotarLote}
              disabled={loteLoading}
              className="inline-flex items-center gap-2 px-3 py-2 rounded bg-action hover:bg-action disabled:opacity-50 text-ink text-xs font-medium transition-colors"
            >
              {loteLoading ? (
                <span className="h-3 w-3 rounded-full border-2 border-white border-t-transparent animate-spin" />
              ) : null}
              Recotar {selecionadas.size} selecionada{selecionadas.size !== 1 ? "s" : ""}
            </button>
          )}
        </div>
      )}

      {/* Modal resultado lote */}
      {loteResultado && (
        <div className="rounded border border-line bg-canvas p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-action ">
                {loteResultado.length} cotaç{loteResultado.length !== 1 ? "ões criadas" : "ão criada"} com sucesso
              </p>
              <p className="text-xs text-action mt-1">
                Processamento em andamento — acompanhe no histórico
              </p>
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                onClick={() => navigate("/historico")}
                className="text-xs px-3 py-1 rounded bg-action text-ink hover:bg-action transition-colors"
              >
                Ver histórico
              </button>
              <button
                onClick={() => setLoteResultado(null)}
                className="text-xs text-action hover:text-action "
                aria-label="fechar"
              >
                ✕
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cards de grupos */}
      {!loading && !err && total > 0 && (
        <div className="space-y-4">
          {(["D30", "D45", "D60"] as const).map((j) => {
            const grupo = grouped[j];
            if (grupo.length === 0) return null;
            return (
              <GrupoCard
                key={j}
                janela={j}
                grupo={grupo}
                selecionadas={selecionadas}
                onToggle={handleToggle}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
