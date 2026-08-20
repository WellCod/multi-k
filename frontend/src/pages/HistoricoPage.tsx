import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Cotacao } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination } from "@/components/Pagination";
import { formatBRL, formatDate } from "@/lib/utils";

const PAGE_SIZE = 10;

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

export function HistoricoPage() {
  const [cotacoes, setCotacoes] = useState<Cotacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [busca, setBusca] = useState("");
  const [page, setPage] = useState(1);
  const navigate = useNavigate();

  useEffect(() => {
    api.cotacoes
      .list()
      .then((data) => setCotacoes(data.length > 0 ? data : MOCK_COTACOES))
      .catch(() => setCotacoes(MOCK_COTACOES))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    setPage(1);
  }, [busca]);

  const filtradas = useMemo(() => {
    const q = busca.trim().toLowerCase();
    if (!q) return cotacoes;
    return cotacoes.filter(
      (c) =>
        c.ramo.toLowerCase().includes(q) ||
        c.cotacao_id_cia?.toLowerCase().includes(q) ||
        c.status.toLowerCase().includes(q),
    );
  }, [cotacoes, busca]);

  const paginated = filtradas.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const handleRecotar = (cotacao: Cotacao) => {
    navigate(`/cotacao?recotar=${cotacao.id}`);
  };

  if (loading) {
    return <p className="text-sm text-gray-500 dark:text-gray-400">Carregando histórico…</p>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Histórico de cotações</h2>
        <Button size="sm" onClick={() => navigate("/cotacao")}>
          Nova cotação
        </Button>
      </div>

      <Input
        placeholder="Filtrar por ramo, status ou ID da seguradora…"
        value={busca}
        onChange={(e) => setBusca(e.target.value)}
        className="max-w-sm mb-4"
      />

      {filtradas.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {busca ? "Nenhuma cotação encontrada para este filtro." : "Nenhuma cotação registrada."}
        </p>
      ) : (
        <>
          <div className="space-y-3">
            {paginated.map((c) => (
              <div
                key={c.id}
                className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 px-5 py-4 flex items-center justify-between gap-4"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-gray-900 dark:text-white capitalize">
                      {c.ramo}
                    </span>
                    <StatusBadge status={c.status} />
                    {c.necessita_vistoria && (
                      <span className="text-xs text-yellow-700 dark:text-yellow-300 bg-yellow-50 dark:bg-yellow-900/50 border border-yellow-200 dark:border-yellow-700 rounded px-1.5 py-0.5">
                        Vistoria
                      </span>
                    )}
                    {c.versao_anterior_id && (
                      <span className="text-xs text-blue-600 dark:text-blue-400 font-medium">
                        Revisão
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
                    <span>{formatDate(c.criado_em)}</span>
                    {c.cotacao_id_cia && (
                      <span className="font-mono truncate">{c.cotacao_id_cia}</span>
                    )}
                  </div>
                  {c.restricoes.length > 0 && (
                    <ul className="mt-1 text-xs text-yellow-700 dark:text-yellow-400 space-y-0.5">
                      {c.restricoes.map((r) => (
                        <li key={r.codigo}>{r.mensagem}</li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="text-right flex-shrink-0">
                  {c.premio_total ? (
                    <p className="text-base font-semibold text-gray-900 dark:text-white">
                      {formatBRL(c.premio_total)}
                    </p>
                  ) : (
                    <p className="text-sm text-gray-400 dark:text-gray-500">—</p>
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
                    <Button variant="outline" size="sm" onClick={() => handleRecotar(c)}>
                      Recotar
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <Pagination
            page={page}
            total={filtradas.length}
            perPage={PAGE_SIZE}
            onChange={setPage}
          />
        </>
      )}
    </div>
  );
}
