import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Renovacao } from "@/lib/api";

const JANELA_CONFIG = {
  D30: { label: "≤ 30 dias", color: "bg-red-100 text-red-800 border-red-200" },
  D45: { label: "31–45 dias", color: "bg-orange-100 text-orange-800 border-orange-200" },
  D60: { label: "46–60 dias", color: "bg-yellow-100 text-yellow-800 border-yellow-200" },
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

function fmtDate(d: string) {
  return new Date(d + "T12:00:00").toLocaleDateString("pt-BR");
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
        <h1 className="text-xl font-semibold">Renovações</h1>
        <div className="flex gap-2 text-xs text-gray-500">
          {(["D30", "D45", "D60"] as const).map((j) => (
            <JanelaBadge key={j} janela={j} />
          ))}
        </div>
      </div>

      {loading && <p className="text-sm text-gray-500">Carregando…</p>}
      {err && <p className="text-sm text-red-600">{err}</p>}

      {(["D30", "D45", "D60"] as const).map((janela) => {
        const grupo = grouped[janela];
        if (grupo.length === 0) return null;
        return (
          <div key={janela}>
            <div className="flex items-center gap-2 mb-3">
              <JanelaBadge janela={janela} />
              <span className="text-sm text-gray-500">{grupo.length} apólice(s)</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-gray-50 border-b text-left">
                    <th className="px-4 py-2 font-medium">Protocolo</th>
                    <th className="px-4 py-2 font-medium">Ramo</th>
                    <th className="px-4 py-2 font-medium">Prêmio</th>
                    <th className="px-4 py-2 font-medium">Vigência até</th>
                    <th className="px-4 py-2 font-medium">Dias</th>
                    <th className="px-4 py-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {grupo.map((r) => (
                    <tr key={r.proposta_id} className="border-b hover:bg-gray-50">
                      <td className="px-4 py-3 font-mono text-xs">{r.protocolo}</td>
                      <td className="px-4 py-3 capitalize">{r.ramo}</td>
                      <td className="px-4 py-3">{fmtReal(r.premio_total)}</td>
                      <td className="px-4 py-3">{fmtDate(r.fim_vigencia)}</td>
                      <td className="px-4 py-3 font-semibold text-center">
                        {r.dias_para_vencer}
                      </td>
                      <td className="px-4 py-3 flex gap-2">
                        {r.cliente_id && (
                          <button
                            className="text-xs text-blue-600 hover:underline"
                            onClick={() => navigate(`/clientes/${r.cliente_id}`)}
                          >
                            Ver cliente
                          </button>
                        )}
                        <button
                          className="text-xs text-indigo-600 hover:underline"
                          onClick={() => navigate(`/cotacao?recotar=${r.cotacao_id}`)}
                        >
                          Renovar
                        </button>
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
