import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type ItemComparativo, type Proposta, type Cotacao } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/StatusBadge";
import { formatBRL } from "@/lib/utils";

const PARCELAMENTOS = ["AVISTA", "2X", "3X", "6X", "10X"];

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
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6">
        <h2 className="text-lg font-semibold mb-1 text-gray-900 dark:text-white">
          Transmitir proposta
        </h2>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-4 uppercase tracking-wide">
          {cia}
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          {isJustos && (
            <div>
              <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-200">
                Tipo de pagamento
              </label>
              <div className="flex gap-4">
                {(["monthly", "annual"] as const).map((t) => (
                  <label
                    key={t}
                    className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300 cursor-pointer"
                  >
                    <input
                      type="radio"
                      name="policy_type"
                      value={t}
                      checked={policyType === t}
                      onChange={() => setPolicyType(t)}
                    />
                    {t === "monthly" ? "Mensal" : "Anual"}
                  </label>
                ))}
              </div>
            </div>
          )}
          <div>
            <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-200">
              Parcelamento
            </label>
            <select
              className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              value={plano}
              onChange={(e) => {
                setPlano(e.target.value);
                setParcelas(
                  e.target.value === "AVISTA"
                    ? 1
                    : Number(e.target.value.replace("X", "")),
                );
              }}
            >
              {PARCELAMENTOS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-200">
              Comissão (%)
            </label>
            <input
              type="number"
              step="0.5"
              min="1"
              max="30"
              className={`w-full border rounded px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white ${
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
            <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-200">
              Início vigência
            </label>
            <input
              type="date"
              className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              value={vigencia}
              onChange={(e) => setVigencia(e.target.value)}
            />
          </div>
          {err && <p className="text-red-600 text-sm">{err}</p>}
          <div className="flex justify-end gap-2 pt-2">
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
        setItens(comp);
      })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Erro"))
      .finally(() => setLoading(false));
  }, [cotacaoId]);

  if (loading) {
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Carregando comparativo…
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
  if (!cotacao || !cotacaoId) return null;

  const podeTransmitir =
    (cotacao.status === "sucesso" || cotacao.status === "restricao") && !proposta;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate(-1)}
          className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
        >
          ← Voltar
        </button>
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
          Comparativo —{" "}
          {cotacao.ramo.charAt(0).toUpperCase() + cotacao.ramo.slice(1)}
        </h1>
        <StatusBadge status={cotacao.status} />
      </div>

      {proposta && (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700 rounded-lg p-4">
          <p className="font-medium text-green-800 dark:text-green-300">
            Proposta transmitida com sucesso!
          </p>
          <p className="text-sm text-green-700 dark:text-green-400 mt-1">
            Protocolo:{" "}
            <span className="font-mono font-semibold">{proposta.protocolo}</span>
          </p>
          <p className="text-sm text-green-700 dark:text-green-400">
            {proposta.n_parcelas}× de {formatBRL(proposta.valor_parcela)}{" "}
            &nbsp;|&nbsp; Comissão: {formatBRL(proposta.comissao_parcela)}/parcela
          </p>
          {cotacao.cliente_id && (
            <Button
              className="mt-3"
              size="sm"
              variant="outline"
              onClick={() => navigate(`/clientes/${cotacao.cliente_id}`)}
            >
              Ver timeline do cliente
            </Button>
          )}
        </div>
      )}

      {itens.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Nenhum resultado disponível (cotação em processamento).
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 text-left">
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">
                  Seguradora
                </th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">
                  Mensal
                </th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">
                  Anual
                </th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">
                  Observações
                </th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">
                  Vistoria
                </th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">
                  Status
                </th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {itens.map((item, i) => (
                <tr
                  key={i}
                  className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                >
                  <td className="px-4 py-3 font-semibold uppercase text-gray-900 dark:text-white">
                    {item.cia}
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-900 dark:text-white">
                    {item.premio_total ? (
                      formatBRL(item.premio_total)
                    ) : (
                      <span className="text-gray-300 dark:text-gray-600">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-900 dark:text-white">
                    {item.annual_total ? (
                      formatBRL(item.annual_total)
                    ) : (
                      <span className="text-gray-300 dark:text-gray-600">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {item.restricoes.length === 0 && item.mensagens.length === 0 ? (
                      <span className="text-gray-400 dark:text-gray-500">—</span>
                    ) : (
                      <>
                        {item.restricoes.map((r) => (
                          <span
                            key={r.codigo}
                            className="block text-xs text-yellow-700 dark:text-yellow-400"
                          >
                            {r.codigo}: {r.mensagem}
                          </span>
                        ))}
                        {item.mensagens.map((m, mi) => (
                          <span
                            key={mi}
                            className="block text-xs text-gray-500 dark:text-gray-400"
                          >
                            {m}
                          </span>
                        ))}
                      </>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {item.necessita_vistoria ? (
                      <span className="text-yellow-700 dark:text-yellow-400 text-xs font-medium">
                        Sim
                      </span>
                    ) : (
                      <span className="text-gray-400 dark:text-gray-500 text-xs">
                        Não
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={item.status} />
                  </td>
                  <td className="px-4 py-3">
                    {podeTransmitir &&
                      (item.status === "sucesso" || item.status === "restricao") && (
                        <button
                          className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline whitespace-nowrap"
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
      )}

      <div className="flex gap-3">
        <a
          href={api.cotacoes.comparativoPdfUrl(cotacaoId)}
          target="_blank"
          rel="noreferrer"
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        >
          Baixar PDF
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
