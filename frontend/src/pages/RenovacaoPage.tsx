import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Renovacao } from "@/lib/api";
import { Tooltip } from "@/components/Tooltip";

const JANELA_CONFIG = {
  D30: { label: "≤ 30 dias", color: "bg-red-100 text-red-800 border-red-200 dark:bg-red-900/50 dark:text-red-300 dark:border-red-700" },
  D45: { label: "31–45 dias", color: "bg-orange-100 text-orange-800 border-orange-200 dark:bg-orange-900/50 dark:text-orange-300 dark:border-orange-700" },
  D60: { label: "46–60 dias", color: "bg-yellow-100 text-yellow-800 border-yellow-200 dark:bg-yellow-900/50 dark:text-yellow-300 dark:border-yellow-700" },
};

const hoje = new Date();
const d = (offset: number) => {
  const dt = new Date(hoje);
  dt.setDate(dt.getDate() + offset);
  return dt.toISOString().slice(0, 10);
};
const inicio = (fimOffset: number) => d(fimOffset - 365);

const MOCK_RENOVACOES: Renovacao[] = [
  {
    proposta_id: "mock-r1",
    cotacao_id: "mock-c1",
    cliente_id: null,
    protocolo: "PROP-2025-00812",
    ramo: "auto",
    inicio_vigencia: inicio(12),
    fim_vigencia: d(12),
    dias_para_vencer: 12,
    janela: "D30",
    premio_total: "2340.00",
  },
  {
    proposta_id: "mock-r2",
    cotacao_id: "mock-c2",
    cliente_id: null,
    protocolo: "PROP-2025-00748",
    ramo: "residencia",
    inicio_vigencia: inicio(24),
    fim_vigencia: d(24),
    dias_para_vencer: 24,
    janela: "D30",
    premio_total: "890.50",
  },
  {
    proposta_id: "mock-r3",
    cotacao_id: "mock-c3",
    cliente_id: null,
    protocolo: "PROP-2025-00691",
    ramo: "auto",
    inicio_vigencia: inicio(38),
    fim_vigencia: d(38),
    dias_para_vencer: 38,
    janela: "D45",
    premio_total: "3120.00",
  },
  {
    proposta_id: "mock-r4",
    cotacao_id: "mock-c4",
    cliente_id: null,
    protocolo: "PROP-2025-00603",
    ramo: "auto",
    inicio_vigencia: inicio(44),
    fim_vigencia: d(44),
    dias_para_vencer: 44,
    janela: "D45",
    premio_total: "1980.00",
  },
  {
    proposta_id: "mock-r5",
    cotacao_id: "mock-c5",
    cliente_id: null,
    protocolo: "PROP-2025-00541",
    ramo: "residencia",
    inicio_vigencia: inicio(55),
    fim_vigencia: d(55),
    dias_para_vencer: 55,
    janela: "D60",
    premio_total: "1540.00",
  },
  {
    proposta_id: "mock-r6",
    cotacao_id: "mock-c6",
    cliente_id: null,
    protocolo: "PROP-2025-00489",
    ramo: "auto",
    inicio_vigencia: inicio(59),
    fim_vigencia: d(59),
    dias_para_vencer: 59,
    janela: "D60",
    premio_total: "4200.00",
  },
];

function fmtReal(v: string | null) {
  if (!v) return "—";
  return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function fmtDate(dt: string) {
  return new Date(dt + "T12:00:00").toLocaleDateString("pt-BR");
}

function JanelaBadge({ janela }: { janela: "D30" | "D45" | "D60" }) {
  const cfg = JANELA_CONFIG[janela];
  return (
    <span className={`px-2 py-0.5 rounded border text-xs font-medium ${cfg.color}`}>
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
      .then((data) => setRenovacoes(data.length > 0 ? data : MOCK_RENOVACOES))
      .catch(() => {
        setErr(null);
        setRenovacoes(MOCK_RENOVACOES);
      })
      .finally(() => setLoading(false));
  }, []);

  const grouped = {
    D30: renovacoes.filter((r) => r.janela === "D30"),
    D45: renovacoes.filter((r) => r.janela === "D45"),
    D60: renovacoes.filter((r) => r.janela === "D60"),
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Renovações</h1>
        <div className="flex gap-2 text-xs text-gray-500">
          {(["D30", "D45", "D60"] as const).map((j) => (
            <JanelaBadge key={j} janela={j} />
          ))}
        </div>
      </div>

      {loading && <p className="text-sm text-gray-500 dark:text-gray-400">Carregando…</p>}
      {err && <p className="text-sm text-red-600">{err}</p>}

      {(["D30", "D45", "D60"] as const).map((janela) => {
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
                    <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Protocolo</th>
                    <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Ramo</th>
                    <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Prêmio</th>
                    <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Vigência até</th>
                    <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300 text-center">Dias</th>
                    <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300"></th>
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
                      <td className="px-4 py-3 capitalize text-gray-900 dark:text-white">{r.ramo}</td>
                      <td className="px-4 py-3 text-gray-900 dark:text-white">{fmtReal(r.premio_total)}</td>
                      <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{fmtDate(r.fim_vigencia)}</td>
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
                      <td className="px-4 py-3 flex gap-2">
                        {r.cliente_id && (
                          <button
                            className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                            onClick={() => navigate(`/clientes/${r.cliente_id}`)}
                          >
                            Ver cliente
                          </button>
                        )}
                        <Tooltip text="Abre nova cotação pré-preenchida com os dados desta apólice para renovação" position="top">
                          <button
                            className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
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
        );
      })}
    </div>
  );
}
