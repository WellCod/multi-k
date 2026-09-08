import { useState, useEffect } from "react";
import { api, type Proposta } from "@/lib/api";
import { Button } from "@/components/ui/button";

const PARCELAMENTOS = ["AVISTA", "2X", "3X", "6X", "10X"];

interface TransmitirModalProps {
  cotacaoId: string;
  ramo?: string;
  cia?: string;
  vigenciaInicio?: string;
  onClose: () => void;
  onSuccess: (p: Proposta) => void;
}

export function TransmitirModal({
  cotacaoId,
  ramo,
  cia = "fake",
  vigenciaInicio,
  onClose,
  onSuccess,
}: TransmitirModalProps) {
  const [plano, setPlano] = useState("AVISTA");
  const [parcelas, setParcelas] = useState(1);
  const [comissao, setComissao] = useState("0.1500");
  const [vigencia, setVigencia] = useState(
    vigenciaInicio ?? new Date().toISOString().slice(0, 10),
  );
  const [policyType, setPolicyType] = useState<"monthly" | "annual">("monthly");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [comissaoErr, setComissaoErr] = useState<string | null>(null);

  const isJustos = cia === "justos";

  useEffect(() => {
    if (!ramo) return;
    api.comissoes.get(cia, ramo)
      .then((cfg) => { setComissao(cfg.pct_padrao); })
      .catch(() => { /* mantém padrão 15% */ });
  }, [cia, ramo]);

  const handleComissaoChange = (pct: number) => {
    if (pct < 0 || pct > 30) {
      setComissaoErr("Comissão deve ser entre 0% e 30%");
    } else {
      setComissaoErr(null);
    }
    setComissao((pct / 100).toFixed(4));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const pct = Number(comissao) * 100;
    if (pct < 0 || pct > 30) {
      setComissaoErr("Comissão deve ser entre 0% e 30%");
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const dadosNegocio = isJustos
        ? { policy_type: policyType, ...(policyType === "annual" ? { installments: parcelas } : {}) }
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
        <h2 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">Transmitir proposta</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          {isJustos && (
            <div>
              <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-200">Tipo de pagamento</label>
              <div className="flex gap-4">
                {(["monthly", "annual"] as const).map((t) => (
                  <label key={t} className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
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
            <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-200">Parcelamento</label>
            <select
              className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
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
            <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-200">Comissão (%)</label>
            <input
              type="number"
              step="0.5"
              min="0"
              max="30"
              className={`w-full border rounded px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 ${comissaoErr ? "border-red-500 dark:border-red-500" : "border-gray-300 dark:border-gray-600"}`}
              value={Number(comissao) * 100}
              onChange={(e) => handleComissaoChange(Number(e.target.value))}
            />
            {comissaoErr && (
              <p className="text-xs text-red-600 dark:text-red-400 mt-1" role="alert">
                {comissaoErr}
              </p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-200">Início vigência</label>
            <input
              type="date"
              className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              value={vigencia}
              onChange={(e) => setVigencia(e.target.value)}
            />
          </div>
          {err && (
            <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 px-4 py-3 flex items-start gap-3">
              <div className="flex-1 text-sm text-red-700 dark:text-red-400">{err}</div>
              <button
                type="button"
                onClick={() => setErr(null)}
                className="text-red-400 hover:text-red-600 dark:hover:text-red-200 leading-none text-lg flex-shrink-0"
                aria-label="Fechar erro"
              >
                ×
              </button>
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" disabled={loading || !!comissaoErr}>
              {loading ? "Transmitindo…" : "Confirmar"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
