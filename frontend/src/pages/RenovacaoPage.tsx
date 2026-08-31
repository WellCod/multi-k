import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Renovacao } from "@/lib/api";
import { Tooltip } from "@/components/Tooltip";
import { formatBRL, formatDate } from "@/lib/utils";

const JANELA_CONFIG = {
  D30: {
    label: "≤ 30 dias",
    color:
      "bg-red-100 text-red-800 border-red-200 dark:bg-red-900/50 dark:text-red-300 dark:border-red-700",
  },
  D45: {
    label: "31–45 dias",
    color:
      "bg-orange-100 text-orange-800 border-orange-200 dark:bg-orange-900/50 dark:text-orange-300 dark:border-orange-700",
  },
  D60: {
    label: "46–60 dias",
    color:
      "bg-yellow-100 text-yellow-800 border-yellow-200 dark:bg-yellow-900/50 dark:text-yellow-300 dark:border-yellow-700",
  },
};

function JanelaBadge({ janela }: { janela: "D30" | "D45" | "D60" }) {
  const cfg = JANELA_CONFIG[janela];
  return (
    <span
      className={`px-2 py-0.5 rounded border text-xs font-medium ${cfg.color}`}
    >
      {cfg.label}
    </span>
  );
}

export function RenovacaoPage() {
  const navigate = useNavigate();
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
            Renovações
          </h1>
          {!loading && !err && total > 0 && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
              {total} apólice{total !== 1 ? "s" : ""} vencem nos próximos 60
              dias
            </p>
          )}
        </div>
        <div className="flex gap-2 text-xs text-gray-500">
          {(["D30", "D45", "D60"] as const).map((j) => (
            <JanelaBadge key={j} janela={j} />
          ))}
        </div>
      </div>

      {loading && (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Carregando…
        </p>
      )}

      {err && (
        <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-400">
          {err}
        </div>
      )}

      {!loading && !err && total === 0 && (
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-8 text-center text-sm text-gray-500 dark:text-gray-400">
          Nenhuma apólice vence nos próximos 60 dias.
        </div>
      )}

      {!loading &&
        !err &&
        (["D30", "D45", "D60"] as const).map((janela) => {
          const grupo = grouped[janela];
          if (grupo.length === 0) return null;
          return (
            <div key={janela}>
              <div className="flex items-center gap-2 mb-3">
                <JanelaBadge janela={janela} />
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {grupo.length} apólice{grupo.length !== 1 ? "s" : ""}
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 text-left">
                      <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">
                        Protocolo
                      </th>
                      <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">
                        Ramo
                      </th>
                      <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">
                        Prêmio
                      </th>
                      <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">
                        Vigência até
                      </th>
                      <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300 text-center">
                        Dias
                      </th>
                      <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300" />
                    </tr>
                  </thead>
                  <tbody>
                    {grupo.map((r) => (
                      <tr
                        key={r.proposta_id}
                        className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                      >
                        <td className="px-4 py-3 font-mono text-xs text-gray-700 dark:text-gray-300">
                          {r.protocolo}
                        </td>
                        <td className="px-4 py-3 capitalize text-gray-900 dark:text-white">
                          {r.ramo}
                        </td>
                        <td className="px-4 py-3 text-gray-900 dark:text-white">
                          {formatBRL(r.premio_total)}
                        </td>
                        <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                          {formatDate(r.fim_vigencia)}
                        </td>
                        <td className="px-4 py-3 font-semibold text-center">
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
                          <div className="flex gap-3">
                            {r.cliente_id && (
                              <button
                                className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                                onClick={() =>
                                  navigate(`/clientes/${r.cliente_id}`)
                                }
                              >
                                Ver cliente
                              </button>
                            )}
                            <Tooltip
                              text="Abre nova cotação pré-preenchida para renovação"
                              position="top"
                            >
                              <button
                                className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
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
        })}
    </div>
  );
}
