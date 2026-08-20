import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Cotacao } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { formatBRL, formatDate } from "@/lib/utils";

const STATUS_LABEL: Record<string, { label: string; color: string }> = {
  aguardando: { label: "Aguardando", color: "text-gray-500 bg-gray-100" },
  processando: { label: "Processando", color: "text-blue-700 bg-blue-100" },
  sucesso: { label: "Sucesso", color: "text-green-700 bg-green-100" },
  restricao: { label: "Com restrição", color: "text-yellow-700 bg-yellow-100" },
  erro: { label: "Não realizada", color: "text-red-700 bg-red-100" },
};

const MOCK_COTACOES: Cotacao[] = [
  {
    id: "mock-1",
    ramo: "auto",
    status: "sucesso",
    cliente_id: null,
    cotacao_id_cia: "YLM-2026-001482",
    premio_total: "2340.00",
    restricoes: [],
    mensagens: [],
    necessita_vistoria: false,
    versao_anterior_id: null,
    criado_em: new Date(Date.now() - 2 * 86400000).toISOString(),
    dados_risco: {},
  },
  {
    id: "mock-2",
    ramo: "residencia",
    status: "restricao",
    cliente_id: null,
    cotacao_id_cia: "YLM-2026-001391",
    premio_total: "890.50",
    restricoes: [{ codigo: "R01", mensagem: "Imóvel em área de risco hídrico" }],
    mensagens: [],
    necessita_vistoria: true,
    versao_anterior_id: null,
    criado_em: new Date(Date.now() - 5 * 86400000).toISOString(),
    dados_risco: {},
  },
  {
    id: "mock-3",
    ramo: "auto",
    status: "sucesso",
    cliente_id: null,
    cotacao_id_cia: "YLM-2026-001274",
    premio_total: "3120.00",
    restricoes: [],
    mensagens: [],
    necessita_vistoria: false,
    versao_anterior_id: null,
    criado_em: new Date(Date.now() - 8 * 86400000).toISOString(),
    dados_risco: {},
  },
  {
    id: "mock-4",
    ramo: "auto",
    status: "erro",
    cliente_id: null,
    cotacao_id_cia: null,
    premio_total: null,
    restricoes: [],
    mensagens: [],
    necessita_vistoria: false,
    versao_anterior_id: null,
    criado_em: new Date(Date.now() - 10 * 86400000).toISOString(),
    dados_risco: {},
  },
  {
    id: "mock-5",
    ramo: "residencia",
    status: "sucesso",
    cliente_id: null,
    cotacao_id_cia: "YLM-2026-001102",
    premio_total: "1540.00",
    restricoes: [],
    mensagens: [],
    necessita_vistoria: false,
    versao_anterior_id: "mock-old",
    criado_em: new Date(Date.now() - 15 * 86400000).toISOString(),
    dados_risco: {},
  },
];

function StatusBadge({ status }: { status: string }) {
  const meta = STATUS_LABEL[status] ?? {
    label: status,
    color: "text-gray-700 bg-gray-100",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${meta.color}`}
    >
      {meta.label}
    </span>
  );
}

export function HistoricoPage() {
  const [cotacoes, setCotacoes] = useState<Cotacao[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.cotacoes
      .list()
      .then((data) => setCotacoes(data.length > 0 ? data : MOCK_COTACOES))
      .catch(() => setCotacoes(MOCK_COTACOES))
      .finally(() => setLoading(false));
  }, []);

  const handleRecotar = (cotacao: Cotacao) => {
    navigate(`/cotacao?recotar=${cotacao.id}`);
  };

  if (loading) {
    return <p className="text-sm text-gray-500">Carregando histórico…</p>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-gray-900">Histórico de cotações</h2>
        <Button size="sm" onClick={() => navigate("/cotacao")}>
          Nova cotação
        </Button>
      </div>

      <div className="space-y-3">
        {cotacoes.map((c) => (
          <div
            key={c.id}
            className="bg-white rounded-lg border border-gray-200 px-5 py-4 flex items-center justify-between gap-4"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium text-gray-900 capitalize">
                  {c.ramo}
                </span>
                <StatusBadge status={c.status} />
                {c.necessita_vistoria && (
                  <span className="text-xs text-yellow-700 bg-yellow-50 border border-yellow-200 rounded px-1.5 py-0.5">
                    Vistoria
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span>{formatDate(c.criado_em)}</span>
                {c.cotacao_id_cia && (
                  <span className="font-mono truncate">{c.cotacao_id_cia}</span>
                )}
                {c.versao_anterior_id && (
                  <span className="text-blue-600">Revisão</span>
                )}
              </div>
              {c.restricoes.length > 0 && (
                <ul className="mt-1 text-xs text-yellow-700 space-y-0.5">
                  {c.restricoes.map((r) => (
                    <li key={r.codigo}>{r.mensagem}</li>
                  ))}
                </ul>
              )}
            </div>

            <div className="text-right flex-shrink-0">
              {c.premio_total ? (
                <p className="text-base font-semibold text-gray-900">
                  {formatBRL(c.premio_total)}
                </p>
              ) : (
                <p className="text-sm text-gray-400">—</p>
              )}
              <div className="flex gap-2 mt-2 justify-end">
                {(c.status === "sucesso" || c.status === "restricao") && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => navigate(`/cotacoes/${c.id}/comparativo`)}
                  >
                    Comparativo
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleRecotar(c)}
                >
                  Recotar
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
