import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Cotacao } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination } from "@/components/Pagination";
import { Tooltip } from "@/components/Tooltip";
import { formatBRL, formatDate } from "@/lib/utils";

const PAGE_SIZE = 10;

function nomeProponente(dados: Record<string, unknown>): string {
  const prop = dados.proponente as Record<string, unknown> | undefined;
  return String(prop?.nome ?? dados.nome ?? "");
}

export function HistoricoPage() {
  const [cotacoes, setCotacoes] = useState<Cotacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [filtroRamo, setFiltroRamo] = useState("");
  const [filtroStatus, setFiltroStatus] = useState("");
  const [page, setPage] = useState(1);
  const navigate = useNavigate();

  useEffect(() => {
    api.cotacoes
      .list()
      .then(setCotacoes)
      .catch((e: unknown) =>
        setErr(e instanceof Error ? e.message : "Erro ao carregar histórico"),
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    setPage(1);
  }, [busca, filtroRamo, filtroStatus]);

  const ramos = useMemo(
    () => [...new Set(cotacoes.map((c) => c.ramo))].sort(),
    [cotacoes],
  );

  const filtradas = useMemo(() => {
    const q = busca.trim().toLowerCase();
    return cotacoes.filter((c) => {
      if (filtroRamo && c.ramo !== filtroRamo) return false;
      if (filtroStatus && c.status !== filtroStatus) return false;
      if (!q) return true;
      return (
        c.ramo.toLowerCase().includes(q) ||
        c.status.toLowerCase().includes(q) ||
        (c.cotacao_id_cia?.toLowerCase().includes(q) ?? false) ||
        nomeProponente(c.dados_risco).toLowerCase().includes(q)
      );
    });
  }, [cotacoes, busca, filtroRamo, filtroStatus]);

  const paginated = filtradas.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (loading) {
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Carregando histórico…
      </p>
    );
  }

  if (err) {
    return (
      <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-400">
        {err}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          Histórico de cotações
        </h2>
        <Button size="sm" onClick={() => navigate("/cotacao")}>
          Nova cotação
        </Button>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <Input
          placeholder="Buscar por proponente, ramo, status, ID…"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="max-w-xs"
        />
        <select
          value={filtroRamo}
          onChange={(e) => setFiltroRamo(e.target.value)}
          className="border border-gray-300 dark:border-gray-600 rounded px-3 py-1.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
        >
          <option value="">Todos os ramos</option>
          {ramos.map((r) => (
            <option key={r} value={r}>
              {r.charAt(0).toUpperCase() + r.slice(1)}
            </option>
          ))}
        </select>
        <select
          value={filtroStatus}
          onChange={(e) => setFiltroStatus(e.target.value)}
          className="border border-gray-300 dark:border-gray-600 rounded px-3 py-1.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
        >
          <option value="">Todos os status</option>
          {["sucesso", "restricao", "erro", "aguardando", "processando"].map(
            (s) => (
              <option key={s} value={s}>
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </option>
            ),
          )}
        </select>
      </div>

      {filtradas.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {busca || filtroRamo || filtroStatus
            ? "Nenhuma cotação encontrada para este filtro."
            : "Nenhuma cotação registrada ainda."}
        </p>
      ) : (
        <>
          <div className="space-y-3">
            {paginated.map((c) => {
              const nome = nomeProponente(c.dados_risco);
              return (
                <div
                  key={c.id}
                  className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 px-5 py-4 flex items-center justify-between gap-4"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
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
                    {nome && (
                      <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-0.5">
                        {nome}
                      </p>
                    )}
                    <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
                      <span>{formatDate(c.criado_em)}</span>
                      {c.cotacao_id_cia && (
                        <span className="font-mono truncate">
                          {c.cotacao_id_cia}
                        </span>
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
                      <p className="text-sm text-gray-400 dark:text-gray-500">
                        —
                      </p>
                    )}
                    <div className="flex gap-2 mt-2 justify-end flex-wrap">
                      {c.cliente_id && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            navigate(`/clientes/${c.cliente_id}`)
                          }
                        >
                          Ver cliente
                        </Button>
                      )}
                      {(c.status === "sucesso" || c.status === "restricao") && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            navigate(`/cotacoes/${c.id}/comparativo`)
                          }
                        >
                          Comparativo
                        </Button>
                      )}
                      <Tooltip
                        text="Abre nova cotação pré-preenchida com os dados desta"
                        position="top"
                      >
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate(`/cotacao?recotar=${c.id}`)}
                        >
                          Refazer
                        </Button>
                      </Tooltip>
                    </div>
                  </div>
                </div>
              );
            })}
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
