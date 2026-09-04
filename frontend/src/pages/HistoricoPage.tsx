import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Cotacao, type PaginatedCotacoes } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination } from "@/components/Pagination";
import { Tooltip } from "@/components/Tooltip";
import { formatBRL, formatDate } from "@/lib/utils";

const PAGE_SIZE = 20;

function nomeProponente(dados: Record<string, unknown>): string {
  const prop = dados.proponente as Record<string, unknown> | undefined;
  return String(prop?.nome ?? dados.nome ?? "");
}

const RAMO_ICON: Record<string, string> = {
  auto: "🚗",
  imovel: "🏠",
  vida: "💙",
  empresarial: "🏢",
};

function RamoIcon({ ramo }: { ramo: string }) {
  return <span className="text-base leading-none">{RAMO_ICON[ramo] ?? "📋"}</span>;
}

function SkeletonCard() {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 px-5 py-4 animate-pulse">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-2">
          <div className="flex gap-2 items-center">
            <div className="h-4 w-4 rounded bg-gray-200 dark:bg-gray-700" />
            <div className="h-4 w-20 rounded bg-gray-200 dark:bg-gray-700" />
            <div className="h-5 w-16 rounded bg-gray-200 dark:bg-gray-700" />
          </div>
          <div className="h-3 w-40 rounded bg-gray-200 dark:bg-gray-700" />
          <div className="h-3 w-24 rounded bg-gray-200 dark:bg-gray-700" />
        </div>
        <div className="space-y-2 text-right">
          <div className="h-5 w-24 rounded bg-gray-200 dark:bg-gray-700 ml-auto" />
          <div className="flex gap-2 justify-end">
            <div className="h-7 w-20 rounded bg-gray-200 dark:bg-gray-700" />
            <div className="h-7 w-20 rounded bg-gray-200 dark:bg-gray-700" />
          </div>
        </div>
      </div>
    </div>
  );
}

function ActiveFilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700">
      {label}
      <button onClick={onRemove} className="ml-0.5 hover:text-blue-900 dark:hover:text-blue-100 leading-none" aria-label="remover filtro">×</button>
    </span>
  );
}

function RestricoesList({ restricoes }: { restricoes: { codigo: string; mensagem: string }[] }) {
  const [open, setOpen] = useState(false);
  if (restricoes.length === 0) return null;
  return (
    <div className="mt-1.5">
      <button
        onClick={() => setOpen((o) => !o)}
        className="text-xs text-yellow-700 dark:text-yellow-400 hover:underline flex items-center gap-1"
      >
        <span>{open ? "▾" : "▸"}</span>
        {restricoes.length} restrição{restricoes.length > 1 ? "ões" : ""}
      </button>
      {open && (
        <ul className="mt-1 space-y-0.5 pl-3 border-l-2 border-yellow-300 dark:border-yellow-700">
          {restricoes.map((r) => (
            <li key={r.codigo} className="text-xs text-yellow-700 dark:text-yellow-400">
              <span className="font-mono text-yellow-600 dark:text-yellow-500">{r.codigo}</span> — {r.mensagem}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function HistoricoPage() {
  const [data, setData] = useState<PaginatedCotacoes | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [filtroRamo, setFiltroRamo] = useState("");
  const [filtroStatus, setFiltroStatus] = useState("");
  const [filtroDias, setFiltroDias] = useState(0);
  const [page, setPage] = useState(1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();

  const fetchCotacoes = useCallback((opts: {
    page: number;
    ramo: string;
    status: string;
    dias: number;
    q: string;
  }) => {
    setLoading(true);
    setErr(null);
    api.cotacoes
      .list({
        page: opts.page,
        page_size: PAGE_SIZE,
        ramo: opts.ramo || undefined,
        status: opts.status || undefined,
        dias: opts.dias || undefined,
        q: opts.q.trim() || undefined,
      })
      .then((r: PaginatedCotacoes) => setData(r))
      .catch((e: unknown) =>
        setErr(e instanceof Error ? e.message : "Erro ao carregar histórico"),
      )
      .finally(() => setLoading(false));
  }, []);

  // Re-fetch whenever filter params change (debounce busca)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetchCotacoes({ page, ramo: filtroRamo, status: filtroStatus, dias: filtroDias, q: busca });
    }, busca ? 350 : 0);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [page, filtroRamo, filtroStatus, filtroDias, busca]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reset to page 1 when filters change (not page itself)
  useEffect(() => {
    setPage(1);
  }, [busca, filtroRamo, filtroStatus, filtroDias]);

  const temFiltroAtivo = busca || filtroRamo || filtroStatus || filtroDias > 0;

  function limparFiltros() {
    setBusca("");
    setFiltroRamo("");
    setFiltroStatus("");
    setFiltroDias(0);
  }

  const selectClass =
    "border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500";

  const cotacoes: Cotacao[] = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
            Histórico de cotações
          </h1>
          {!loading && !err && data && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
              {total} cotação{total !== 1 ? "ões" : ""}{temFiltroAtivo ? " encontrada" + (total !== 1 ? "s" : "") : " no total"}
            </p>
          )}
        </div>
        <div className="flex gap-2 flex-shrink-0">
          <Button
            size="sm"
            variant="outline"
            onClick={() => { window.location.href = api.cotacoes.exportCsvUrl(); }}
          >
            ↓ Exportar CSV
          </Button>
          <Button size="sm" onClick={() => navigate("/cotacao")}>
            + Nova cotação
          </Button>
        </div>
      </div>

      {/* Filtros */}
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 space-y-3">
        <div className="flex flex-wrap gap-2">
          <Input
            placeholder="Buscar proponente ou ID CIA…"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            className="min-w-[200px] flex-1"
          />
          <select
            value={filtroRamo}
            onChange={(e) => setFiltroRamo(e.target.value)}
            className={selectClass}
          >
            <option value="">Todos os ramos</option>
            {["auto", "imovel", "vida", "empresarial"].map((r) => (
              <option key={r} value={r}>
                {RAMO_ICON[r] ?? ""} {r.charAt(0).toUpperCase() + r.slice(1)}
              </option>
            ))}
          </select>
          <select
            value={filtroStatus}
            onChange={(e) => setFiltroStatus(e.target.value)}
            className={selectClass}
          >
            <option value="">Qualquer status</option>
            {[
              { v: "sucesso", l: "Sucesso" },
              { v: "restricao", l: "Com restrição" },
              { v: "erro", l: "Não realizada" },
              { v: "aguardando", l: "Aguardando" },
              { v: "processando", l: "Processando" },
            ].map(({ v, l }) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
          <select
            value={filtroDias}
            onChange={(e) => setFiltroDias(Number(e.target.value))}
            className={selectClass}
          >
            <option value={0}>Qualquer período</option>
            <option value={7}>Últimos 7 dias</option>
            <option value={30}>Últimos 30 dias</option>
            <option value={90}>Últimos 90 dias</option>
            <option value={365}>Último ano</option>
          </select>
          {temFiltroAtivo && (
            <button
              onClick={limparFiltros}
              className="text-xs text-gray-500 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400 underline self-center"
            >
              Limpar filtros
            </button>
          )}
        </div>

        {/* Chips de filtros ativos */}
        {temFiltroAtivo && (
          <div className="flex flex-wrap gap-1.5 pt-1 border-t border-gray-100 dark:border-gray-700">
            {busca && <ActiveFilterChip label={`"${busca}"`} onRemove={() => setBusca("")} />}
            {filtroRamo && <ActiveFilterChip label={`Ramo: ${filtroRamo}`} onRemove={() => setFiltroRamo("")} />}
            {filtroStatus && <ActiveFilterChip label={`Status: ${filtroStatus}`} onRemove={() => setFiltroStatus("")} />}
            {filtroDias > 0 && <ActiveFilterChip label={filtroDias === 365 ? "Último ano" : `Últimos ${filtroDias} dias`} onRemove={() => setFiltroDias(0)} />}
          </div>
        )}
      </div>

      {/* Erro */}
      {err && (
        <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-400">
          {err}
        </div>
      )}

      {/* Skeleton */}
      {loading && (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* Empty state */}
      {!loading && !err && cotacoes.length === 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 py-16 text-center">
          <p className="text-4xl mb-3">🔍</p>
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {temFiltroAtivo ? "Nenhuma cotação encontrada" : "Nenhuma cotação registrada"}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            {temFiltroAtivo ? "Tente ajustar os filtros acima" : "Clique em + Nova cotação para começar"}
          </p>
          {temFiltroAtivo && (
            <button onClick={limparFiltros} className="mt-3 text-xs text-blue-600 dark:text-blue-400 underline">
              Limpar filtros
            </button>
          )}
        </div>
      )}

      {/* Lista */}
      {!loading && !err && cotacoes.length > 0 && (
        <>
          <div className="space-y-2">
            {cotacoes.map((c) => {
              const nome = nomeProponente(c.dados_risco);
              return (
                <div
                  key={c.id}
                  className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 px-5 py-4 hover:border-gray-300 dark:hover:border-gray-600 transition-colors"
                >
                  <div className="flex items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <RamoIcon ramo={c.ramo} />
                        <span className="text-sm font-semibold text-gray-900 dark:text-white capitalize">
                          {c.ramo}
                        </span>
                        <StatusBadge status={c.status} />
                        {c.necessita_vistoria && (
                          <span className="text-xs text-yellow-700 dark:text-yellow-300 bg-yellow-50 dark:bg-yellow-900/50 border border-yellow-200 dark:border-yellow-700 rounded-full px-2 py-0.5">
                            Vistoria obrigatória
                          </span>
                        )}
                        {c.proposta_id && (
                          <span className="text-xs text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/50 border border-green-200 dark:border-green-700 rounded-full px-2 py-0.5">
                            ✓ Emitida
                          </span>
                        )}
                        {c.numero_apolice && (
                          <span className="text-xs font-mono text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30 border border-emerald-200 dark:border-emerald-700 rounded-full px-2 py-0.5">
                            Apólice {c.numero_apolice}
                          </span>
                        )}
                        {c.versao_anterior_id && (
                          <span className="text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/50 border border-blue-200 dark:border-blue-700 rounded-full px-2 py-0.5">
                            Revisão
                          </span>
                        )}
                      </div>

                      {nome && (
                        <p className="mt-1 text-sm font-medium text-gray-700 dark:text-gray-300">
                          {nome}
                        </p>
                      )}

                      <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-0.5 text-xs text-gray-400 dark:text-gray-500">
                        <span>{formatDate(c.criado_em)}</span>
                        {c.cotacao_id_cia && (
                          <Tooltip text={c.cotacao_id_cia} position="top">
                            <span className="font-mono cursor-default">
                              {c.cotacao_id_cia.length > 20
                                ? `${c.cotacao_id_cia.slice(0, 20)}…`
                                : c.cotacao_id_cia}
                            </span>
                          </Tooltip>
                        )}
                      </div>

                      <RestricoesList restricoes={c.restricoes} />
                    </div>

                    <div className="flex-shrink-0 text-right space-y-2">
                      {c.premio_total ? (
                        <p className="text-lg font-bold text-gray-900 dark:text-white tabular-nums">
                          {formatBRL(c.premio_total)}
                        </p>
                      ) : (
                        <p className="text-sm text-gray-300 dark:text-gray-600 font-medium">—</p>
                      )}

                      <div className="flex gap-1.5 justify-end flex-wrap">
                        {c.cliente_id && (
                          <button
                            onClick={() => navigate(`/clientes/${c.cliente_id}`)}
                            className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                          >
                            Cliente
                          </button>
                        )}
                        {(c.status === "sucesso" || c.status === "restricao") && (
                          <button
                            onClick={() => navigate(`/cotacoes/${c.id}/comparativo`)}
                            className="text-xs px-2.5 py-1 rounded-lg border border-blue-200 dark:border-blue-700 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors"
                          >
                            Comparativo
                          </button>
                        )}
                        <Tooltip text="Nova cotação com os mesmos dados" position="top">
                          <button
                            onClick={() => navigate(`/cotacao?recotar=${c.id}`)}
                            className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                          >
                            Refazer
                          </button>
                        </Tooltip>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <Pagination
            page={page}
            total={total}
            perPage={PAGE_SIZE}
            onChange={setPage}
          />
          {pages > 1 && (
            <p className="text-xs text-center text-gray-400 dark:text-gray-500">
              Página {page} de {pages}
            </p>
          )}
        </>
      )}
    </div>
  );
}
