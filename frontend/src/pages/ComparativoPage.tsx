import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type ItemComparativo, type Parcela, type Proposta, type Cotacao } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/StatusBadge";
import { formatBRL, formatDate } from "@/lib/utils";

const PARCELAMENTOS = ["AVISTA", "2X", "3X", "6X", "10X"];

// ---------------------------------------------------------------------------
// Skeleton loading
// ---------------------------------------------------------------------------

function ComparativoSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div className="h-5 w-16 rounded bg-gray-200 dark:bg-gray-700 animate-pulse" />
        <div className="h-7 w-64 rounded-lg bg-gray-200 dark:bg-gray-700 animate-pulse" />
      </div>
      <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden">
        <div className="h-10 bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 animate-pulse" />
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-14 border-b border-gray-100 dark:border-gray-700 animate-pulse bg-white dark:bg-gray-800"
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

interface TransmitirModalProps {
  cotacaoId: string;
  cia: string;
  onClose: () => void;
  onSuccess: (p: Proposta) => void;
}

function TransmitirModal({ cotacaoId, cia, onClose, onSuccess }: TransmitirModalProps) {
  const [plano, setPlano] = useState("AVISTA");
  const [parcelas, setParcelas] = useState(1);
  const [comissao, setComissao] = useState("0.1500");
  const [vigencia, setVigencia] = useState(new Date().toISOString().slice(0, 10));
  const [policyType, setPolicyType] = useState<"monthly" | "annual">("monthly");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [comissaoErr, setComissaoErr] = useState<string | null>(null);

  const isJustos = cia === "justos";

  const handleComissaoChange = (pct: number) => {
    if (pct < 1 || pct > 30) {
      setComissaoErr("Comissão deve estar entre 1% e 30%");
    } else {
      setComissaoErr(null);
    }
    setComissao((pct / 100).toFixed(4));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const pct = Number(comissao) * 100;
    if (pct < 1 || pct > 30) {
      setComissaoErr("Comissão deve estar entre 1% e 30%");
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const dadosNegocio = isJustos
        ? {
            policy_type: policyType,
            ...(policyType === "annual" ? { installments: parcelas } : {}),
          }
        : {};
      const proposta = await api.cotacoes.transmitir(cotacaoId, {
        plano_pagamento: plano,
        n_parcelas: parcelas,
        comissao_pct: comissao,
        inicio_vigencia: vigencia,
        cia,
        dados_negocio: dadosNegocio,
      });
      onSuccess(proposta);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Erro ao transmitir");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-md">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-gray-100 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Transmitir proposta
          </h2>
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mt-0.5">
            {cia}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {isJustos && (
            <div>
              <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-200">
                Tipo de pagamento
              </label>
              <div className="flex gap-3">
                {(["monthly", "annual"] as const).map((t) => (
                  <label
                    key={t}
                    className={`flex items-center gap-2 text-sm cursor-pointer px-4 py-2 rounded-lg border transition-colors ${
                      policyType === t
                        ? "border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300"
                        : "border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                    }`}
                  >
                    <input
                      type="radio"
                      name="policy_type"
                      value={t}
                      checked={policyType === t}
                      onChange={() => setPolicyType(t)}
                      className="sr-only"
                    />
                    {t === "monthly" ? "Mensal" : "Anual"}
                  </label>
                ))}
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1.5 text-gray-700 dark:text-gray-200">
              Parcelamento
            </label>
            <div className="flex gap-2 flex-wrap">
              {PARCELAMENTOS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => {
                    setPlano(p);
                    setParcelas(p === "AVISTA" ? 1 : Number(p.replace("X", "")));
                  }}
                  className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                    plano === p
                      ? "border-blue-500 bg-blue-600 text-white"
                      : "border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5 text-gray-700 dark:text-gray-200">
              Comissão (%)
            </label>
            <input
              type="number"
              step="0.5"
              min="1"
              max="30"
              className={`w-full border rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                comissaoErr
                  ? "border-red-500 dark:border-red-500"
                  : "border-gray-300 dark:border-gray-600"
              }`}
              value={Number(comissao) * 100}
              onChange={(e) => handleComissaoChange(Number(e.target.value))}
            />
            {comissaoErr && (
              <p className="text-xs text-red-600 mt-1">{comissaoErr}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5 text-gray-700 dark:text-gray-200">
              Início vigência
            </label>
            <input
              type="date"
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={vigencia}
              onChange={(e) => setVigencia(e.target.value)}
            />
          </div>

          {err && (
            <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-3 text-sm text-red-700 dark:text-red-400">
              {err}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? "Transmitindo…" : "Confirmar"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Painel de parcelas colapsável
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
        className="text-xs font-medium text-green-700 dark:text-green-400 hover:underline"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "▲ Ocultar parcelas" : "▼ Ver calendário de parcelas"}
      </button>
      {open && parcelas && (
        <div className="mt-3 overflow-x-auto rounded-lg border border-green-200 dark:border-green-800">
          <table className="text-xs border-collapse w-full">
            <thead>
              <tr className="bg-green-50 dark:bg-green-900/20 text-left text-gray-500 dark:text-gray-400">
                <th className="px-3 py-2">#</th>
                <th className="px-3 py-2">Vencimento</th>
                <th className="px-3 py-2 text-right">Valor</th>
                <th className="px-3 py-2 text-right">Comissão</th>
              </tr>
            </thead>
            <tbody>
              {parcelas.map((p) => (
                <tr key={p.numero} className="border-t border-green-200 dark:border-green-800">
                  <td className="px-3 py-1.5 text-gray-700 dark:text-gray-300">{p.numero}ª</td>
                  <td className="px-3 py-1.5 text-gray-700 dark:text-gray-300">
                    {p.vencimento ? formatDate(p.vencimento) : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-gray-900 dark:text-white">
                    {formatBRL(p.valor)}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-green-700 dark:text-green-400">
                    {formatBRL(p.comissao)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Célula de observações colapsável
// ---------------------------------------------------------------------------

function ObservacoesCell({ item }: { item: ItemComparativo }) {
  const [expanded, setExpanded] = useState(false);
  const temConteudo = item.restricoes.length > 0 || item.mensagens.length > 0;

  if (!temConteudo) {
    return <span className="text-gray-300 dark:text-gray-600">—</span>;
  }

  const linhas: { texto: string; tipo: "restricao" | "mensagem" }[] = [
    ...item.restricoes.map((r) => ({
      texto: `${r.codigo}: ${r.mensagem}`,
      tipo: "restricao" as const,
    })),
    ...item.mensagens.map((m) => ({ texto: m, tipo: "mensagem" as const })),
  ];

  const preview = linhas[0];
  const resto = linhas.slice(1);

  return (
    <div className="space-y-0.5">
      <span
        className={`block text-xs ${
          preview.tipo === "restricao"
            ? "text-yellow-700 dark:text-yellow-400"
            : "text-gray-500 dark:text-gray-400"
        } ${!expanded ? "line-clamp-1" : ""}`}
      >
        {preview.texto}
      </span>
      {expanded &&
        resto.map((l, i) => (
          <span
            key={i}
            className={`block text-xs ${
              l.tipo === "restricao"
                ? "text-yellow-700 dark:text-yellow-400"
                : "text-gray-500 dark:text-gray-400"
            }`}
          >
            {l.texto}
          </span>
        ))}
      {resto.length > 0 && (
        <button
          className="text-xs text-blue-500 dark:text-blue-400 hover:underline mt-0.5"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "▲ menos" : `▼ +${resto.length} mais`}
        </button>
      )}
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

  useEffect(() => {
    if (!cotacaoId) return;
    Promise.all([api.cotacoes.get(cotacaoId), api.cotacoes.comparativo(cotacaoId)])
      .then(([c, comp]) => {
        setCotacao(c);
        // Ordena: sucesso/restricao primeiro (por menor prêmio), erros por último
        const ordenados = [...comp].sort((a, b) => {
          const aOk = a.status === "sucesso" || a.status === "restricao";
          const bOk = b.status === "sucesso" || b.status === "restricao";
          if (aOk && !bOk) return -1;
          if (!aOk && bOk) return 1;
          if (aOk && bOk) {
            const aVal = Number(a.premio_total ?? "999999999");
            const bVal = Number(b.premio_total ?? "999999999");
            return aVal - bVal;
          }
          return 0;
        });
        setItens(ordenados);
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
      <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-400">
        {err}
      </div>
    );
  }

  if (!cotacao || !cotacaoId) return null;

  const podeTransmitir =
    (cotacao.status === "sucesso" || cotacao.status === "restricao") && !proposta;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={() => navigate(-1)}
          className="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
        >
          ← Voltar
        </button>
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
          Comparativo —{" "}
          {cotacao.ramo.charAt(0).toUpperCase() + cotacao.ramo.slice(1)}
        </h1>
        <StatusBadge status={cotacao.status} />
      </div>

      {/* Card de proposta emitida */}
      {proposta && (
        <div className="rounded-xl border border-green-200 dark:border-green-700 bg-green-50 dark:bg-green-900/20 p-5">
          <div className="flex items-start gap-3">
            <span className="text-3xl mt-0.5">✓</span>
            <div className="flex-1">
              <p className="font-semibold text-green-800 dark:text-green-300 text-base">
                Proposta transmitida com sucesso!
              </p>
              <p className="text-sm text-green-700 dark:text-green-400 mt-1">
                Protocolo:{" "}
                <span className="font-mono font-bold text-green-900 dark:text-green-200 text-base">
                  {proposta.protocolo}
                </span>
              </p>
              <p className="text-sm text-green-700 dark:text-green-400 mt-0.5">
                {proposta.n_parcelas}× de {formatBRL(proposta.valor_parcela)}{" "}
                &nbsp;|&nbsp; Comissão: {formatBRL(proposta.comissao_parcela)}/parcela
              </p>
              <ParcelasPanel propostaId={proposta.id} />
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

      {/* Tabela de comparativo */}
      {itens.length === 0 ? (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 py-16 text-center">
          <span className="text-4xl">⏳</span>
          <p className="text-base font-medium text-gray-700 dark:text-gray-200 mt-4">
            Nenhum resultado disponível
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Cotação em processamento. Aguarde e recarregue.
          </p>
        </div>
      ) : (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse bg-white dark:bg-gray-800">
              <thead>
                <tr className="bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 text-left text-xs text-gray-500 dark:text-gray-400">
                  <th className="px-4 py-3 font-semibold">Seguradora</th>
                  <th className="px-4 py-3 font-semibold">Mensal</th>
                  <th className="px-4 py-3 font-semibold">Anual</th>
                  <th className="px-4 py-3 font-semibold">Observações</th>
                  <th className="px-4 py-3 font-semibold">Vistoria</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {itens.map((item, i) => (
                  <tr
                    key={i}
                    className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/40 transition-colors"
                  >
                    <td className="px-4 py-3 font-bold uppercase text-gray-900 dark:text-white tracking-wide text-xs">
                      {item.cia}
                    </td>
                    <td className="px-4 py-3 font-mono font-semibold text-gray-900 dark:text-white">
                      {item.premio_total ? (
                        formatBRL(item.premio_total)
                      ) : (
                        <span className="text-gray-300 dark:text-gray-600 font-normal">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-mono text-gray-700 dark:text-gray-300">
                      {item.annual_total ? (
                        formatBRL(item.annual_total)
                      ) : (
                        <span className="text-gray-300 dark:text-gray-600">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 max-w-xs">
                      <ObservacoesCell item={item} />
                    </td>
                    <td className="px-4 py-3">
                      {item.necessita_vistoria ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 border border-yellow-200 dark:border-yellow-800">
                          Sim
                        </span>
                      ) : (
                        <span className="text-gray-300 dark:text-gray-600 text-sm">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={item.status} />
                    </td>
                    <td className="px-4 py-3">
                      {podeTransmitir &&
                        (item.status === "sucesso" || item.status === "restricao") && (
                          <button
                            className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-colors whitespace-nowrap font-medium"
                            onClick={() => setTransmitirCia(item.cia)}
                          >
                            Emitir
                          </button>
                        )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Ações */}
      <div className="flex gap-3">
        <a
          href={api.cotacoes.comparativoPdfUrl(cotacaoId)}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        >
          ↓ Baixar PDF
        </a>
      </div>

      {transmitirCia && (
        <TransmitirModal
          cotacaoId={cotacaoId}
          cia={transmitirCia}
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
