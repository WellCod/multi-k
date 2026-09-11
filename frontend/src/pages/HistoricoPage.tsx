import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Cotacao, type PaginatedCotacoes } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination } from "@/components/Pagination";
import { Tooltip } from "@/components/Tooltip";
import { formatBRL, formatDate } from "@/lib/utils";
import { useInsurers } from "@/hooks/useInsurers";

const PAGE_SIZE = 20;

function nomeProponente(dados: Record<string, unknown>): string {
  const prop = dados.proponente as Record<string, unknown> | undefined;
  return String(prop?.nome ?? dados.nome ?? "");
}

const RAMO_LABEL: Record<string, string> = {
  auto: "Auto",
  moto: "Moto",
  imovel: "Imóvel",
  vida: "Vida",
  empresarial: "Empresarial",
};

function SkeletonCard() {
  return (
    <div className="bg-surface rounded border border-line px-4 py-4 animate-pulse">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-2">
          <div className="flex gap-2 items-center">
            <div className="h-4 w-4 rounded bg-surface " />
            <div className="h-4 w-20 rounded bg-surface " />
            <div className="h-5 w-16 rounded bg-surface " />
          </div>
          <div className="h-3 w-40 rounded bg-surface " />
          <div className="h-3 w-24 rounded bg-surface " />
        </div>
        <div className="space-y-2 text-right">
          <div className="h-5 w-24 rounded bg-surface ml-auto" />
          <div className="flex gap-2 justify-end">
            <div className="h-7 w-20 rounded bg-surface " />
            <div className="h-7 w-20 rounded bg-surface " />
          </div>
        </div>
      </div>
    </div>
  );
}

function ActiveFilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-canvas text-action border border-line ">
      {label}
      <button onClick={onRemove} className="ml-1 hover:text-action leading-none" aria-label={`Remover filtro: ${label}`}>×</button>
    </span>
  );
}

function RestricoesList({ restricoes }: { restricoes: { codigo: string; mensagem: string }[] }) {
  const [open, setOpen] = useState(false);
  if (restricoes.length === 0) return null;
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="text-sm text-warning hover:underline flex items-center gap-1"
      >
        <span>{open ? "▾" : "▸"}</span>
        {restricoes.length} {restricoes.length === 1 ? "restrição" : "restrições"}
      </button>
      {open && (
        <ul className="mt-1 space-y-1 pl-3 border-l-2 border-line ">
          {restricoes.map((r) => (
            <li key={r.codigo} className="text-xs text-warning ">
              <span className="font-mono text-warning ">{r.codigo}</span> — {r.mensagem}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function VincularApolice({ propostaId, onVinculado }: { propostaId: string; onVinculado: (n: string) => void }) {
  const [open, setOpen] = useState(false);
  const [numero, setNumero] = useState("");
  const [saving, setSaving] = useState(false);
  const [errLocal, setErrLocal] = useState<string | null>(null);

  function submit() {
    const trimmed = numero.trim();
    if (!trimmed) return;
    setSaving(true);
    setErrLocal(null);
    api.propostas
      .vincularApolice(propostaId, trimmed)
      .then(() => { onVinculado(trimmed); setOpen(false); })
      .catch((e: unknown) => setErrLocal(e instanceof Error ? e.message : "Erro"))
      .finally(() => setSaving(false));
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="text-xs px-3 py-1 rounded border border-dashed border-line text-success hover:bg-canvas transition-colors"
      >
        + Apólice
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1 mt-1">
      <input
        autoFocus
        value={numero}
        onChange={(e) => setNumero(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") submit(); if (e.key === "Escape") setOpen(false); }}
        placeholder="Nº apólice"
        className="text-xs px-2 py-1 rounded border border-line bg-surface text-ink focus:outline-none focus:ring-1 focus:ring-action w-28"
      />
      <button
        onClick={submit}
        disabled={saving || !numero.trim()}
        className="text-xs px-2 py-1 rounded bg-success text-ink hover:bg-success disabled:opacity-50 transition-colors"
      >
        {saving ? "…" : "OK"}
      </button>
      <button onClick={() => setOpen(false)} className="text-xs text-muted hover:text-muted ">✕</button>
      {errLocal && <span className="text-xs text-danger">{errLocal}</span>}
    </div>
  );
}

export function HistoricoPage() {
  const { items: insurers, error: insurersError } = useInsurers();
  const [data, setData] = useState<PaginatedCotacoes | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [filtroRamo, setFiltroRamo] = useState("");
  const [filtroStatus, setFiltroStatus] = useState("");
  const [filtroDias, setFiltroDias] = useState(0);
  const [filtroCia, setFiltroCia] = useState("");
  const [orderBy, setOrderBy] = useState("");
  const [page, setPage] = useState(1);
  const [apolicesPendentes, setApolicesPendentes] = useState<Record<string, string>>({});
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const requestVersion = useRef(0);
  const navigate = useNavigate();

  const fetchCotacoes = useCallback((opts: {
    page: number;
    ramo: string;
    status: string;
    dias: number;
    q: string;
    cia: string;
    order_by: string;
  }) => {
    const version = ++requestVersion.current;
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
        cia: opts.cia || undefined,
        order_by: opts.order_by || undefined,
      })
      .then((r: PaginatedCotacoes) => { if (version === requestVersion.current) setData(r); })
      .catch((e: unknown) => {
        if (version === requestVersion.current) setErr(e instanceof Error ? e.message : "Erro ao carregar histórico");
      })
      .finally(() => { if (version === requestVersion.current) setLoading(false); });
  }, []);

  // Re-fetch whenever filter params change (debounce busca)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetchCotacoes({ page, ramo: filtroRamo, status: filtroStatus, dias: filtroDias, q: busca, cia: filtroCia, order_by: orderBy });
    }, busca ? 350 : 0);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      requestVersion.current++;
    };
  }, [page, filtroRamo, filtroStatus, filtroDias, busca, filtroCia, orderBy]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reset to page 1 when filters change (not page itself)
  useEffect(() => {
    setPage(1);
  }, [busca, filtroRamo, filtroStatus, filtroDias, filtroCia, orderBy]);

  const temFiltroAtivo = busca || filtroRamo || filtroStatus || filtroDias > 0 || filtroCia || orderBy;

  function limparFiltros() {
    setBusca("");
    setFiltroRamo("");
    setFiltroStatus("");
    setFiltroDias(0);
    setFiltroCia("");
    setOrderBy("");
  }

  const selectClass =
    "border border-line rounded px-3 py-2 text-sm bg-surface text-ink focus:outline-none focus:ring-2 focus:ring-action";

  const cotacoes: Cotacao[] = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink ">
            Histórico de cotações
          </h1>
          {!loading && !err && data && (
            <p className="text-sm text-muted mt-1">
              {total} {total === 1 ? "cotação" : "cotações"}{temFiltroAtivo ? " encontrada" + (total !== 1 ? "s" : "") : " no total"}
            </p>
          )}
        </div>
        <div className="flex gap-2 flex-shrink-0">
          <Button
            size="sm"
            variant="outline"
            onClick={() => { window.location.href = api.cotacoes.exportCsvUrl(); }}
          >
            Exportar CSV
          </Button>
          <Button size="sm" onClick={() => navigate("/cotacao")}>
            Nova cotação
          </Button>
        </div>
      </div>

      {/* Filtros */}
      <div className="comparison-panel p-4 space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
          <Input
            placeholder="Buscar por nome ou ID da seguradora"
            aria-label="Buscar proponente ou identificador da seguradora"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            className="w-full sm:col-span-2 xl:col-span-3"
          />
          <select
            value={filtroRamo}
            aria-label="Filtrar por ramo"
            onChange={(e) => setFiltroRamo(e.target.value)}
            className={selectClass}
          >
            <option value="">Todos os ramos</option>
            {Object.keys(RAMO_LABEL).map((r) => (
              <option key={r} value={r}>
                {RAMO_LABEL[r]}
              </option>
            ))}
          </select>
          <select
            value={filtroStatus}
            aria-label="Filtrar por status"
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
            aria-label="Filtrar por período"
            onChange={(e) => setFiltroDias(Number(e.target.value))}
            className={selectClass}
          >
            <option value={0}>Qualquer período</option>
            <option value={7}>Últimos 7 dias</option>
            <option value={30}>Últimos 30 dias</option>
            <option value={90}>Últimos 90 dias</option>
            <option value={365}>Último ano</option>
          </select>
          <select
            value={filtroCia}
            aria-label="Filtrar por seguradora"
            onChange={(e) => setFiltroCia(e.target.value)}
            className={selectClass}
          >
            <option value="">Todas as seguradoras</option>
            {insurers.map(item => <option key={item.id} value={item.id}>{item.nome}</option>)}
          </select>
          <select
            value={orderBy}
            onChange={(e) => setOrderBy(e.target.value)}
            className={selectClass}
            aria-label="Ordenar por"
          >
            <option value="">Mais recentes</option>
            <option value="data_asc">Mais antigas</option>
            <option value="premio_desc">Maior prêmio</option>
            <option value="premio_asc">Menor prêmio</option>
          </select>
          {temFiltroAtivo && (
            <button
              onClick={limparFiltros}
              className="text-sm text-muted hover:text-action underline justify-self-start self-center"
            >
              Limpar filtros
            </button>
          )}
        </div>

        {/* Chips de filtros ativos */}
        {temFiltroAtivo && (
          <div className="flex flex-wrap gap-2 pt-1 border-t border-line ">
            {busca && <ActiveFilterChip label={`"${busca}"`} onRemove={() => setBusca("")} />}
            {filtroRamo && <ActiveFilterChip label={`Ramo: ${filtroRamo}`} onRemove={() => setFiltroRamo("")} />}
            {filtroStatus && <ActiveFilterChip label={`Status: ${filtroStatus}`} onRemove={() => setFiltroStatus("")} />}
            {filtroDias > 0 && <ActiveFilterChip label={filtroDias === 365 ? "Último ano" : `Últimos ${filtroDias} dias`} onRemove={() => setFiltroDias(0)} />}
            {filtroCia && <ActiveFilterChip label={insurers.find(item => item.id === filtroCia)?.nome ?? filtroCia} onRemove={() => setFiltroCia("")} />}
            {orderBy && <ActiveFilterChip label={{ data_asc: "Mais antigas", premio_desc: "Maior prêmio", premio_asc: "Menor prêmio" }[orderBy] ?? orderBy} onRemove={() => setOrderBy("")} />}
          </div>
        )}
        {insurersError && <p role="status" className="text-sm text-warning">{insurersError}</p>}
      </div>

      {/* Erro */}
      {err && (
        <div role="alert" className="comparison-panel p-4 space-y-3 text-sm text-danger">
          <p>{err}</p>
          <Button variant="outline" onClick={() => fetchCotacoes({ page, ramo: filtroRamo, status: filtroStatus, dias: filtroDias, q: busca, cia: filtroCia, order_by: orderBy })}>Tentar novamente</Button>
        </div>
      )}

      {/* Skeleton */}
      {loading && (
        <div role="status" aria-label="Carregando cotações" className="space-y-3">
          {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* Empty state */}
      {!loading && !err && cotacoes.length === 0 && (
        <div className="comparison-panel py-12 px-4 text-center">
          <p className="text-base font-medium text-ink">
            {temFiltroAtivo ? "Nenhuma cotação encontrada" : "Nenhuma cotação registrada"}
          </p>
          <p className="text-sm text-muted mt-1">
            {temFiltroAtivo ? "Tente ajustar os filtros acima." : "Crie sua primeira cotação para consultar os resultados aqui."}
          </p>
          {temFiltroAtivo && (
            <button onClick={limparFiltros} className="mt-3 text-xs text-action underline">
              Limpar filtros
            </button>
          )}
        </div>
      )}

      {/* Lista */}
      {!loading && !err && cotacoes.length > 0 && (
        <>
          <div className="comparison-panel divide-y divide-line">
            {cotacoes.map((c) => {
              const nome = nomeProponente(c.dados_risco);
              return (
                <div
                  key={c.id}
                  className="px-4 py-4 hover:bg-canvas transition-colors"
                >
                  <div className="flex flex-col md:flex-row md:items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <button onClick={() => navigate(`/cotacoes/${c.id}/comparativo`)} className="text-base font-semibold text-ink hover:text-action text-left break-words">
                        {nome || "Proponente não informado"}
                      </button>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm text-muted">
                          {RAMO_LABEL[c.ramo] ?? c.ramo}
                        </span>
                        <StatusBadge status={c.status} />
                        {c.necessita_vistoria && (
                          <span className="text-xs text-warning bg-canvas border border-line rounded-full px-2 py-1">
                            Vistoria obrigatória
                          </span>
                        )}
                        {c.proposta_id && (
                          <span className="text-xs text-success bg-canvas border border-line rounded-full px-2 py-1">
                            Proposta registrada
                          </span>
                        )}
                        {(c.numero_apolice ?? apolicesPendentes[c.id]) && (
                          <span className="text-xs font-mono text-success bg-canvas border border-line rounded-full px-2 py-1">
                            Apólice {c.numero_apolice ?? apolicesPendentes[c.id]}
                          </span>
                        )}
                        {c.versao_anterior_id && (
                          <span className="text-xs text-action bg-canvas border border-line rounded-full px-2 py-1">
                            Revisão
                          </span>
                        )}
                      </div>

                      <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted ">
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

                    <div className="md:w-72 md:flex-shrink-0 md:text-right space-y-2">
                      <p className="text-xs text-muted">Prêmio informado</p>
                      {c.premio_total != null ? (
                        <p className="text-base font-semibold text-ink tabular-nums">
                          {formatBRL(c.premio_total)}
                        </p>
                      ) : (
                        <p className="text-sm text-muted font-medium">—</p>
                      )}

                      <div className="flex gap-2 md:justify-end flex-wrap">
                        {c.cliente_id && (
                          <button
                            onClick={() => navigate(`/clientes/${c.cliente_id}`)}
                            className="text-sm px-3 py-2 rounded text-muted hover:bg-surface transition-colors"
                          >
                            Cliente
                          </button>
                        )}
                          <Button variant="outline" size="sm"
                            onClick={() => navigate(`/cotacoes/${c.id}/comparativo`)}
                          >
                            Ver resultados
                          </Button>
                        <Tooltip text="Nova cotação com os mesmos dados" position="top">
                          <button
                            onClick={() => navigate(`/cotacao?recotar=${c.id}`)}
                            className="text-sm px-3 py-2 rounded text-muted hover:bg-surface transition-colors"
                          >
                            Refazer
                          </button>
                        </Tooltip>
                        {c.proposta_id && !c.numero_apolice && !apolicesPendentes[c.id] && (
                          <VincularApolice
                            propostaId={c.proposta_id}
                            onVinculado={(n) => setApolicesPendentes((prev) => ({ ...prev, [c.id]: n }))}
                          />
                        )}
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
            <p className="text-xs text-center text-muted ">
              Página {page} de {pages}
            </p>
          )}
        </>
      )}
    </div>
  );
}
