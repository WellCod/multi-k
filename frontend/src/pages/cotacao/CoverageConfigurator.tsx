import { useState } from "react";
import { api, type Peril, type RepricingResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { formatBRL } from "@/lib/utils";

interface Props {
  cotacaoId: string;
  cia: string;
  coveragesAvailable: Record<string, Peril>;
  initialSelected: Record<string, string | null>;
  onClose: () => void;
  onApply: (result: RepricingResult) => void;
}

const PERIL_ORDER = [
  "colisao-e-desastres-naturais",
  "roubo-e-furto",
  "incendio",
  "danos-materiais",
  "danos-corporais",
  "danos-morais",
  "morte-e-invalidez",
  "assistencia-24h",
  "assistencia-vidros",
  "backup-car",
  "home-assistance",
  "assistencia-contra-buracos",
  "assistencia-lataria-e-pintura",
];

function sortPerils(available: Record<string, Peril>): [string, Peril][] {
  const entries = Object.entries(available);
  return [
    ...PERIL_ORDER.filter((k) => available[k]).map((k) => [k, available[k]] as [string, Peril]),
    ...entries.filter(([k]) => !PERIL_ORDER.includes(k)),
  ];
}

export function CoverageConfigurator({
  cotacaoId,
  cia,
  coveragesAvailable,
  initialSelected,
  onClose,
  onApply,
}: Props) {
  const [selected, setSelected] = useState<Record<string, string | null>>(initialSelected);
  const [pricing, setPricing] = useState<RepricingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSelect = (perilSlug: string, optionSlug: string | null) => {
    setSelected((s) => ({ ...s, [perilSlug]: optionSlug }));
    setPricing(null);
  };

  const handleReprice = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.cotacoes.repricing(cotacaoId, cia, selected);
      setPricing(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao recalcular.");
    } finally {
      setLoading(false);
    }
  };

  const handleApply = () => {
    if (pricing) onApply(pricing);
    onClose();
  };

  const perils = sortPerils(coveragesAvailable);
  const hasChanges = JSON.stringify(selected) !== JSON.stringify(initialSelected);

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-2xl flex flex-col max-h-[92vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b dark:border-gray-700 flex-shrink-0">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Configurar coberturas</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Selecione as opções desejadas e recalcule o prêmio</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-2xl leading-none"
            aria-label="Fechar"
          >
            ×
          </button>
        </div>

        <div className="overflow-y-auto flex-1 px-6 py-4 space-y-3">
          {perils.map(([slug, peril]) => {
            if (!peril.peril_options?.length) return null;
            const current = selected[slug];
            return (
              <div key={slug} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2.5 bg-gray-50 dark:bg-gray-700/60">
                  <span className="text-sm font-semibold text-gray-800 dark:text-gray-100">{peril.name}</span>
                  {peril.mandatory ? (
                    <span className="text-[10px] font-bold uppercase tracking-wide text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded px-1.5 py-0.5">Obrigatório</span>
                  ) : (
                    <span className="text-[10px] text-gray-400">Opcional</span>
                  )}
                </div>
                <div className="divide-y divide-gray-100 dark:divide-gray-700">
                  {!peril.mandatory && (
                    <label className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors ${current === null ? "bg-blue-50 dark:bg-blue-900/20" : "hover:bg-gray-50 dark:hover:bg-gray-700/40"}`}>
                      <input
                        type="radio"
                        name={slug}
                        checked={current === null}
                        onChange={() => handleSelect(slug, null)}
                        className="accent-blue-600"
                      />
                      <span className="text-sm text-gray-500 dark:text-gray-400 flex-1">Não contratar</span>
                      <span className="text-xs text-gray-400">— /mês</span>
                    </label>
                  )}
                  {peril.peril_options.map((opt) => {
                    const isSelected = current === opt.slug;
                    return (
                      <label key={opt.slug} className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors ${isSelected ? "bg-blue-50 dark:bg-blue-900/20" : "hover:bg-gray-50 dark:hover:bg-gray-700/40"}`}>
                        <input
                          type="radio"
                          name={slug}
                          checked={isSelected}
                          onChange={() => handleSelect(slug, opt.slug)}
                          className="accent-blue-600"
                        />
                        <div className="flex-1 min-w-0">
                          <span className="text-sm font-medium text-gray-800 dark:text-gray-100">{opt.name}</span>
                          {opt.deductible > 0 && (
                            <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">
                              Franquia: {formatBRL(String(opt.deductible))}
                            </span>
                          )}
                          {opt.coverage_amount > 0 && (
                            <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">
                              Cobertura: {formatBRL(String(opt.coverage_amount))}
                            </span>
                          )}
                        </div>
                        <span className="text-sm font-mono font-semibold text-gray-700 dark:text-gray-200 whitespace-nowrap">
                          {opt.price > 0 ? `+${formatBRL(String(opt.price))}/mês` : "incluso"}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {pricing && (
          <div className="px-6 py-3 bg-green-50 dark:bg-green-900/30 border-t border-green-200 dark:border-green-800 flex-shrink-0">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs text-green-700 dark:text-green-400 font-medium">Novo prêmio calculado</p>
                <p className="text-xl font-bold text-green-800 dark:text-green-300">
                  {formatBRL(pricing.monthly_total)}<span className="text-sm font-normal">/mês</span>
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs text-green-700 dark:text-green-400">Anual</p>
                <p className="text-lg font-semibold text-green-800 dark:text-green-300">{formatBRL(pricing.annual_total)}</p>
              </div>
            </div>
            {pricing.info && (
              <p className="text-xs text-green-600 dark:text-green-400 mt-1 truncate">{pricing.info}</p>
            )}
          </div>
        )}

        {error && (
          <div className="px-6 py-2 text-sm text-red-600 dark:text-red-400 border-t dark:border-gray-700 flex-shrink-0">{error}</div>
        )}

        <div className="px-6 py-4 border-t dark:border-gray-700 flex items-center justify-between gap-3 flex-shrink-0">
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={handleReprice} disabled={loading || !hasChanges}>
              {loading ? "Calculando…" : "Recalcular prêmio"}
            </Button>
            <Button onClick={handleApply} disabled={!pricing}>
              Aplicar e fechar
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
