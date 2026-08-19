import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type ItemComparativo, type Proposta, type Cotacao } from "@/lib/api";
import { Button } from "@/components/ui/button";

const PARCELAMENTOS = ["AVISTA", "2X", "3X", "6X", "10X"];

function fmtReal(v: string | null) {
  if (!v) return "—";
  return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    sucesso: "bg-green-100 text-green-800",
    restricao: "bg-yellow-100 text-yellow-800",
    erro: "bg-red-100 text-red-800",
    processando: "bg-blue-100 text-blue-800",
    aguardando: "bg-gray-100 text-gray-600",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${map[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}

interface TransmitirModalProps {
  cotacaoId: string;
  onClose: () => void;
  onSuccess: (p: Proposta) => void;
}

function TransmitirModal({ cotacaoId, onClose, onSuccess }: TransmitirModalProps) {
  const [plano, setPlano] = useState("AVISTA");
  const [parcelas, setParcelas] = useState(1);
  const [comissao, setComissao] = useState("0.1500");
  const [vigencia, setVigencia] = useState(new Date().toISOString().slice(0, 10));
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    try {
      const proposta = await api.cotacoes.transmitir(cotacaoId, {
        plano_pagamento: plano,
        n_parcelas: parcelas,
        comissao_pct: comissao,
        inicio_vigencia: vigencia,
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
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <h2 className="text-lg font-semibold mb-4">Transmitir proposta</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Plano de pagamento</label>
            <select
              className="w-full border rounded px-3 py-2 text-sm"
              value={plano}
              onChange={(e) => {
                setPlano(e.target.value);
                setParcelas(e.target.value === "AVISTA" ? 1 : Number(e.target.value.replace("X", "")));
              }}
            >
              {PARCELAMENTOS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Comissão (%)</label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              max="100"
              className="w-full border rounded px-3 py-2 text-sm"
              value={Number(comissao) * 100}
              onChange={(e) => setComissao((Number(e.target.value) / 100).toFixed(4))}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Início vigência</label>
            <input
              type="date"
              className="w-full border rounded px-3 py-2 text-sm"
              value={vigencia}
              onChange={(e) => setVigencia(e.target.value)}
            />
          </div>
          {err && <p className="text-red-600 text-sm">{err}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
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
  const [showModal, setShowModal] = useState(false);
  const [proposta, setProposta] = useState<Proposta | null>(null);
  const [err, setErr] = useState<string | null>(null);

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

  const handleTransmissaoSucesso = (p: Proposta) => {
    setProposta(p);
    setShowModal(false);
  };

  if (loading) return <p className="text-sm text-gray-500">Carregando comparativo…</p>;
  if (err) return <p className="text-sm text-red-600">{err}</p>;
  if (!cotacao || !cotacaoId) return null;

  const podeTransmitir = cotacao.status === "sucesso" || cotacao.status === "restricao";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={() => navigate(-1)} className="text-sm text-blue-600 hover:underline">
          ← Voltar
        </button>
        <h1 className="text-xl font-semibold">
          Comparativo — {cotacao.ramo.charAt(0).toUpperCase() + cotacao.ramo.slice(1)}
        </h1>
        <StatusBadge status={cotacao.status} />
      </div>

      {proposta && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="font-medium text-green-800">Proposta transmitida com sucesso!</p>
          <p className="text-sm text-green-700 mt-1">
            Protocolo: <span className="font-mono font-semibold">{proposta.protocolo}</span>
          </p>
          <p className="text-sm text-green-700">
            {proposta.n_parcelas}× de {fmtReal(proposta.valor_parcela)} &nbsp;|&nbsp;
            Comissão: {fmtReal(proposta.comissao_parcela)}/parcela
          </p>
          <Button
            className="mt-3"
            size="sm"
            variant="outline"
            onClick={() => navigate(`/clientes/${cotacao.cliente_id}`)}
          >
            Ver timeline do cliente
          </Button>
        </div>
      )}

      {itens.length === 0 ? (
        <p className="text-sm text-gray-500">Nenhum resultado disponível (cotação em processamento).</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 border-b text-left">
                <th className="px-4 py-2 font-medium">Seguradora</th>
                <th className="px-4 py-2 font-medium">Prêmio total</th>
                <th className="px-4 py-2 font-medium">Restrições</th>
                <th className="px-4 py-2 font-medium">Vistoria</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {itens.map((item, i) => (
                <tr key={i} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-3 font-semibold uppercase">{item.cia}</td>
                  <td className="px-4 py-3 font-mono">{fmtReal(item.premio_total)}</td>
                  <td className="px-4 py-3">
                    {item.restricoes.length === 0
                      ? <span className="text-gray-400">—</span>
                      : item.restricoes.map((r) => (
                          <span key={r.codigo} className="block text-xs text-yellow-700">
                            {r.codigo}: {r.mensagem}
                          </span>
                        ))}
                  </td>
                  <td className="px-4 py-3">
                    {item.necessita_vistoria ? (
                      <span className="text-yellow-700 text-xs font-medium">Sim</span>
                    ) : (
                      <span className="text-gray-400 text-xs">Não</span>
                    )}
                  </td>
                  <td className="px-4 py-3"><StatusBadge status={item.status} /></td>
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
          className="px-4 py-2 border rounded text-sm hover:bg-gray-50 transition-colors"
        >
          Baixar PDF
        </a>
        {podeTransmitir && !proposta && (
          <Button onClick={() => setShowModal(true)}>Transmitir proposta</Button>
        )}
      </div>

      {showModal && (
        <TransmitirModal
          cotacaoId={cotacaoId}
          onClose={() => setShowModal(false)}
          onSuccess={handleTransmissaoSucesso}
        />
      )}
    </div>
  );
}
