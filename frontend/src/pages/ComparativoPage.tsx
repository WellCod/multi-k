import { DataTable } from "@/components/DataTable";
import { InsurerResult } from "@/components/InsurerResult";
import { InsurerComparison } from "@/components/InsurerComparison";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type ItemComparativo, type Parcela, type Proposta, type Cotacao, type VersaoPremio } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/StatusBadge";
import { Money } from "@/components/Money";
import { formatBRL, formatDate } from "@/lib/utils";

import { TransmitirModal } from "./cotacao/TransmitirModal";

// ---------------------------------------------------------------------------
// Skeleton loading
// ---------------------------------------------------------------------------

function ComparativoSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div className="h-5 w-16 rounded bg-surface animate-pulse" />
        <div className="h-7 w-64 rounded bg-surface animate-pulse" />
      </div>
      <div className="rounded border border-line bg-surface overflow-hidden">
        <div className="h-10 bg-canvas border-b border-line animate-pulse" />
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-14 border-b border-line animate-pulse bg-surface "
            style={{ opacity: 1 - i * 0.15 }}
          />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Modal de transmissão
// ---------------------------------------------------------------------------

function ParcelasPanel({ propostaId }: { propostaId: string }) {
  const [parcelas, setParcelas] = useState<Parcela[] | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open || parcelas !== null) return;
    api.propostas.parcelas(propostaId).then(setParcelas).catch(() => setParcelas([]));
  }, [open, propostaId, parcelas]);

  return (
    <div className="mt-4">
      <button
        className="text-xs font-medium text-success hover:underline"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "▲ Ocultar parcelas" : "▼ Ver calendário de parcelas"}
      </button>
      {open && parcelas && (
        <div className="mt-3 overflow-x-auto rounded border border-line ">
          <DataTable className="text-xs border-collapse w-full">
            <thead>
              <tr className="bg-canvas text-left text-muted ">
                <th className="px-3 py-2">#</th>
                <th className="px-3 py-2">Vencimento</th>
                <th className="px-3 py-2 text-right">Valor</th>
                <th className="px-3 py-2 text-right">Comissão</th>
              </tr>
            </thead>
            <tbody>
              {parcelas.map((p) => (
                <tr key={p.numero} className="border-t border-line ">
                  <td className="px-3 py-2 text-ink ">{p.numero}ª</td>
                  <td className="px-3 py-2 text-ink ">
                    {p.vencimento ? formatDate(p.vencimento) : "—"}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-ink ">
                    {formatBRL(p.valor)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-success ">
                    {formatBRL(p.comissao)}
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Célula de observações colapsável
// ---------------------------------------------------------------------------


// ---------------------------------------------------------------------------
// Painel de histórico de prêmio por versão
// ---------------------------------------------------------------------------

function PremiumHistoryPanel({ cotacaoId }: { cotacaoId: string }) {
  const [versoes, setVersoes] = useState<VersaoPremio[] | null>(null);

  useEffect(() => {
    api.cotacoes.versoes(cotacaoId).then(setVersoes).catch(() => setVersoes([]));
  }, [cotacaoId]);

  if (!versoes || versoes.length < 2) return null;

  return (
    <div className="rounded border border-line bg-surface p-4">
      <h2 className="text-sm font-semibold text-ink mb-4">
        Evolução do prêmio ({versoes.length} versões)
      </h2>
      <div className="space-y-3">
        {versoes.map((v, i) => {
          return (
            <div key={v.id} className="flex items-center gap-3">
              <span className="text-xs text-muted w-6 shrink-0">
                v{i + 1}
              </span>
              <span className="text-xs font-mono text-ink w-24 text-right shrink-0">
                {v.premio_total ? formatBRL(v.premio_total) : "—"}
              </span>
              <span className="text-xs text-muted w-20 text-right shrink-0">
                {formatDate(v.criado_em)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Página principal
// ---------------------------------------------------------------------------

export function ComparativoPage() {
  const { cotacaoId } = useParams<{ cotacaoId: string }>();
  const navigate = useNavigate();
  const [cotacao, setCotacao] = useState<Cotacao | null>(null);
  const [itens, setItens] = useState<ItemComparativo[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [transmitirCia, setTransmitirCia] = useState<string | null>(null);
  const [proposta, setProposta] = useState<Proposta | null>(null);
  const [apoliceInput, setApoliceInput] = useState("");
  const [apoliceLoading, setApoliceLoading] = useState(false);
  const [apoliceErr, setApoliceErr] = useState<string | null>(null);

  useEffect(() => {
    if (!cotacaoId) return;
    Promise.all([api.cotacoes.get(cotacaoId), api.cotacoes.comparativo(cotacaoId)])
      .then(([c, comp]) => {
        setCotacao(c);
        // Mantém a ordem da API sem converter valores monetários em float.
        setItens(comp);
        if (c.proposta_id) {
          api.propostas.get(c.proposta_id).then(setProposta).catch(() => undefined);
        }
      })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Erro"))
      .finally(() => setLoading(false));
  }, [cotacaoId]);

  if (loading) return <ComparativoSkeleton />;

  if (err) {
    return (
      <div className="rounded border border-line bg-canvas p-4 text-sm text-danger ">
        {err}
      </div>
    );
  }

  if (!cotacao || !cotacaoId) return null;

  const podeTransmitir =
    (cotacao.status === "sucesso" || cotacao.status === "restricao") && !proposta;
  const single = itens.length === 1 ? itens[0] : null;
  const risk = cotacao.dados_risco;
  const vehicle = [risk.marca, risk.modelo, risk.ano_modelo].filter(value => typeof value === "string" && value).join(" · ");

  return (
    <div className={`space-y-6 mx-auto ${single ? "max-w-5xl" : "w-full"}`}>
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={() => navigate(-1)}
          className="text-sm text-action hover:underline flex items-center gap-1"
        >
          ← Voltar
        </button>
        <h1 className="text-xl font-semibold text-ink ">
          {single ? "Sua cotação — " : "Comparativo — "}
          {cotacao.ramo.charAt(0).toUpperCase() + cotacao.ramo.slice(1)}
        </h1>
        {!single && <StatusBadge status={cotacao.status} />}
        </div>
      <p className="text-sm text-muted">{vehicle ? `${vehicle} · ` : ""}Cotação de {formatDate(cotacao.criado_em)}</p>

      {/* Card de proposta emitida */}
      {proposta && (
        <div className="rounded border border-line bg-canvas p-4">
          <div className="flex items-start gap-3">
            <span className="text-xl mt-1">✓</span>
            <div className="flex-1">
              <p className="font-semibold text-success text-base">
                Proposta transmitida com sucesso!
              </p>
              <p className="text-sm text-success mt-1">
                Protocolo:{" "}
                <span className="font-mono font-bold text-success text-base">
                  {proposta.protocolo}
                </span>
              </p>
              <p className="text-sm text-success mt-1">
                {proposta.n_parcelas}× de {formatBRL(proposta.valor_parcela)}{" "}
                &nbsp;|&nbsp; Comissão: {formatBRL(proposta.comissao_parcela)}/parcela
              </p>
              <ParcelasPanel propostaId={proposta.id} />

              {/* Vínculo apólice */}
              <div className="mt-4 pt-4 border-t border-line ">
                {proposta.numero_apolice ? (
                  <p className="text-sm text-success ">
                    Apólice:{" "}
                    <span className="font-mono font-bold text-success ">
                      {proposta.numero_apolice}
                    </span>
                  </p>
                ) : (
                  <form
                    className="flex gap-2 items-center"
                    onSubmit={async (e) => {
                      e.preventDefault();
                      if (!apoliceInput.trim()) return;
                      setApoliceLoading(true);
                      setApoliceErr(null);
                      try {
                        const updated = await api.propostas.vincularApolice(
                          proposta.id,
                          apoliceInput.trim(),
                        );
                        setProposta(updated);
                        setApoliceInput("");
                      } catch (ex: unknown) {
                        setApoliceErr(
                          ex instanceof Error ? ex.message : "Erro ao vincular apólice",
                        );
                      } finally {
                        setApoliceLoading(false);
                      }
                    }}
                  >
                    <input
                      type="text"
                      placeholder="Nº da apólice emitida"
                      value={apoliceInput}
                      onChange={(e) => setApoliceInput(e.target.value)}
                      maxLength={100}
                      className="flex-1 border border-line rounded px-3 py-2 text-sm bg-surface text-ink focus:outline-none focus:ring-2 focus:ring-action"
                    />
                    <Button
                      type="submit"
                      size="sm"
                      disabled={apoliceLoading || !apoliceInput.trim()}
                    >
                      {apoliceLoading ? "Salvando…" : "Vincular apólice"}
                    </Button>
                  </form>
                )}
                {apoliceErr && (
                  <p className="text-xs text-danger mt-1">{apoliceErr}</p>
                )}
              </div>

              {cotacao.cliente_id && (
                <Button
                  className="mt-4"
                  size="sm"
                  variant="outline"
                  onClick={() => navigate(`/clientes/${cotacao.cliente_id}`)}
                >
                  Ver timeline do cliente
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {single ? <section className="quote-summary" aria-label="Resumo da cotação">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold capitalize">{single.nome || single.cia}</h2>
          <StatusBadge status={single.status} />
        </div>
        <div className="flex flex-wrap gap-6 items-end">
          <div><p className="text-xs text-muted mb-1">Valor informado pela seguradora</p><p className="text-2xl font-semibold tabular-nums"><Money value={single.premio_total} /></p></div>
          {single.annual_total && <div><p className="text-xs text-muted mb-1">Opção anual</p><p className="text-lg font-medium"><Money value={single.annual_total} /></p></div>}
        </div>
        {single.mensagens.map((message, index) => <p key={index} className="text-sm text-muted">{message}</p>)}
        {single.restricoes.map((restriction, index) => <p key={index} className="text-sm text-warning">{restriction.mensagem}</p>)}
        {single.necessita_vistoria && <p className="text-sm text-warning">Vistoria prévia obrigatória.</p>}
        <div className="flex flex-wrap gap-3 border-t border-line pt-4">
          {podeTransmitir && ["sucesso", "restricao"].includes(single.status) && <Button onClick={() => setTransmitirCia(single.cia)}>Revisar proposta</Button>}
          <a className="control inline-flex items-center px-3 text-sm text-action" href={api.cotacoes.comparativoPdfUrl(cotacaoId)} target="_blank" rel="noreferrer">Baixar PDF</a>
        </div>
        <p className="text-xs text-muted">Você revisará os dados antes de confirmar a transmissão.</p>
      </section> : <div className="result-grid">
        {itens.map(item => <InsurerResult key={item.cia} result={item} actions={
          podeTransmitir && ["sucesso", "restricao"].includes(item.status)
              ? <Button onClick={() => setTransmitirCia(item.cia)}>Revisar proposta</Button>
            : undefined
        } />)}
      </div>}
      {!itens.length && <p role="status" className="text-sm text-muted">
        {["aguardando", "pendente", "processando"].includes(cotacao.status)
          ? "Aguardando resultados das seguradoras."
          : "Nenhum resultado disponível para esta cotação."}
      </p>}
      {single ? <section className="quote-summary" aria-label="Coberturas da cotação">
        <div><h2 className="text-base font-semibold">Coberturas</h2><p className="text-sm text-muted mt-1">Limites informados pela seguradora para esta seleção.</p></div>
        <dl className="divide-y divide-line">{(single.coberturas_comparaveis ?? []).map(coverage => <div key={coverage.conceito_id} className="flex justify-between gap-4 py-3 text-sm">
          <dt>{coverage.nome_canonico}</dt><dd className="text-right font-medium shrink-0"><Money value={coverage.limite} /></dd>
        </div>)}</dl>
        {!single.coberturas_comparaveis?.length && <p className="text-sm text-muted">Os detalhes das coberturas não foram informados.</p>}
        {single.coberturas_comparaveis?.some(c => c.limite != null && /^0+(?:\.0+)?$/.test(c.limite)) && <p className="text-xs text-muted">Valores zerados reproduzem o retorno da seguradora e não confirmam ausência de cobertura. Consulte as condições antes de transmitir.</p>}
      </section> : <InsurerComparison items={itens} />}

      {/* Histórico de prêmio por recotação */}
      <PremiumHistoryPanel cotacaoId={cotacaoId} />

      {/* Ações */}
      {!single && <div className="flex gap-3">
        <a
          href={api.cotacoes.comparativoPdfUrl(cotacaoId)}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2 rounded border border-line text-sm font-medium text-ink bg-surface hover:bg-canvas transition-colors"
        >
          ↓ Baixar PDF
        </a>
      </div>}

      {transmitirCia && (
        <TransmitirModal
          cotacaoId={cotacaoId}
          cia={transmitirCia}
          ramo={cotacao.ramo}
          onClose={() => setTransmitirCia(null)}
          onSuccess={(p) => {
            setProposta(p);
            setTransmitirCia(null);
          }}
        />
      )}
    </div>
  );
}
