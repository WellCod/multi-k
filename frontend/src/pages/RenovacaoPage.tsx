import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Renovacao } from "@/lib/api";

const JANELA_CONFIG = {
  D30: { label: "≤ 30 dias", color: "bg-red-100 text-red-800 border-red-200" },
  D45: { label: "31–45 dias", color: "bg-orange-100 text-orange-800 border-orange-200" },
  D60: { label: "46–60 dias", color: "bg-yellow-100 text-yellow-800 border-yellow-200" },
};

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
      .then(setRenovacoes)
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Erro"))
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

      {!loading && !err && renovacoes.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          <p className="text-lg">Nenhuma renovação nos próximos 60 dias</p>
          <p className="text-sm mt-1">As apólices vencendo aparecerão aqui automaticamente.</p>
        </div>
      )}

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
                          onClick={() =>
                            navigate(`/cotacao?recotar=${r.cotacao_id}`)
                          }
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
