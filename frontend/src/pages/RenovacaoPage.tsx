import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Renovacao } from "@/lib/api";
import { Tooltip } from "@/components/Tooltip";
import { formatBRL, formatDate } from "@/lib/utils";

const JANELA_CONFIG = {
  D30: {
    label: "≤ 30 dias",
    headerBg: "bg-red-50 dark:bg-red-900/20",
    headerText: "text-red-800 dark:text-red-300",
    border: "border-red-200 dark:border-red-800",
    badgeColor:
      "bg-red-100 text-red-800 border-red-200 dark:bg-red-900/50 dark:text-red-300 dark:border-red-700",
    countText: "text-red-600 dark:text-red-400",
  },
  D45: {
    label: "31–45 dias",
    headerBg: "bg-orange-50 dark:bg-orange-900/20",
    headerText: "text-orange-800 dark:text-orange-300",
    border: "border-orange-200 dark:border-orange-800",
    badgeColor:
      "bg-orange-100 text-orange-800 border-orange-200 dark:bg-orange-900/50 dark:text-orange-300 dark:border-orange-700",
    countText: "text-orange-600 dark:text-orange-400",
  },
  D60: {
    label: "46–60 dias",
    headerBg: "bg-yellow-50 dark:bg-yellow-900/20",
    headerText: "text-yellow-800 dark:text-yellow-300",
    border: "border-yellow-200 dark:border-yellow-800",
    badgeColor:
      "bg-yellow-100 text-yellow-800 border-yellow-200 dark:bg-yellow-900/50 dark:text-yellow-300 dark:border-yellow-700",
    countText: "text-yellow-600 dark:text-yellow-400",
  },
};

type Janela = keyof typeof JANELA_CONFIG;

function DiasBadge({ dias, janela }: { dias: number; janela: Janela }) {
  const cfg = JANELA_CONFIG[janela];
  return (
    <span
      className={`inline-flex items-center justify-center rounded border px-2 py-0.5 text-xs font-semibold tabular-nums ${cfg.badgeColor}`}
    >
      {dias}d
    </span>
  );
}

function SkeletonGroupCard() {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden animate-pulse">
      <div className="px-4 py-3 bg-gray-100 dark:bg-gray-700/60 flex items-center justify-between">
        <div className="h-4 w-24 rounded bg-gray-200 dark:bg-gray-600" />
        <div className="h-4 w-16 rounded bg-gray-200 dark:bg-gray-600" />
      </div>
      <div className="divide-y divide-gray-100 dark:divide-gray-700">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="px-4 py-3 flex items-center gap-4">
            <div className="h-3 w-28 rounded bg-gray-200 dark:bg-gray-700" />
            <div className="h-3 w-16 rounded bg-gray-200 dark:bg-gray-700" />
            <div className="h-3 w-24 rounded bg-gray-200 dark:bg-gray-700" />
            <div className="h-3 w-20 rounded bg-gray-200 dark:bg-gray-700" />
            <div className="ml-auto h-6 w-14 rounded bg-gray-200 dark:bg-gray-700" />
          </div>
        ))}
      </div>
    </div>
  );
}

function GrupoCard({ janela, grupo }: { janela: Janela; grupo: Renovacao[] }) {
  const navigate = useNavigate();
  const cfg = JANELA_CONFIG[janela];

  return (
    <div className={`rounded-xl border ${cfg.border} overflow-hidden`}>
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
      <div className="bg-white dark:bg-gray-800 overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-700/60 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
              <th className="px-4 py-2.5">Protocolo</th>
              <th className="px-4 py-2.5">Ramo</th>
              <th className="px-4 py-2.5">Prêmio</th>
              <th className="px-4 py-2.5">Vigência até</th>
              <th className="px-4 py-2.5 text-center">Dias</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {grupo.map((r) => (
              <tr
                key={r.proposta_id}
                className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
              >
                <td className="px-4 py-3 font-mono text-xs text-gray-700 dark:text-gray-300">
                  {r.protocolo}
                </td>
                <td className="px-4 py-3 capitalize text-gray-900 dark:text-white">
                  {r.ramo}
                </td>
                <td className="px-4 py-3 text-gray-900 dark:text-white tabular-nums">
                  {formatBRL(r.premio_total)}
                </td>
                <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                  {formatDate(r.fim_vigencia)}
                </td>
                <td className="px-4 py-3 text-center">
                  <DiasBadge dias={r.dias_para_vencer} janela={janela} />
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-2 justify-end">
                    {r.cliente_id && (
                      <button
                        className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors whitespace-nowrap"
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
                        className="text-xs px-2.5 py-1 rounded-lg border border-indigo-200 dark:border-indigo-700 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 transition-colors whitespace-nowrap"
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
        </table>
      </div>
    </div>
  );
}

export function RenovacaoPage() {
  const [renovacoes, setRenovacoes] = useState<Renovacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.renovacoes
      .list(60)
      .then(setRenovacoes)
      .catch((e: unknown) =>
        setErr(e instanceof Error ? e.message : "Erro ao carregar renovações"),
      )
      .finally(() => setLoading(false));
  }, []);

  const grouped = {
    D30: renovacoes.filter((r) => r.janela === "D30"),
    D45: renovacoes.filter((r) => r.janela === "D45"),
    D60: renovacoes.filter((r) => r.janela === "D60"),
  };

  const total = renovacoes.length;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
          Renovações
        </h1>
        {!loading && !err && total > 0 && (
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            {total} apólice{total !== 1 ? "s" : ""} vencem nos próximos 60 dias
          </p>
        )}
      </div>

      {/* Erro */}
      {err && (
        <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-400">
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
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 py-16 text-center">
          <p className="text-4xl mb-3">📋</p>
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Nenhuma apólice vence nos próximos 60 dias
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Volte mais tarde para acompanhar os vencimentos
          </p>
        </div>
      )}

      {/* Cards de grupos */}
      {!loading && !err && total > 0 && (
        <div className="space-y-4">
          {(["D30", "D45", "D60"] as const).map((janela) => {
            const grupo = grouped[janela];
            if (grupo.length === 0) return null;
            return <GrupoCard key={janela} janela={janela} grupo={grupo} />;
          })}
        </div>
      )}
    </div>
  );
}
