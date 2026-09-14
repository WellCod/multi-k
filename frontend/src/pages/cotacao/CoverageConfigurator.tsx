import { useEffect, useRef, useState } from "react";
import { api, type Peril, type RepricingResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/Dialog";
import { formatBRL } from "@/lib/utils";

interface Props {
  cotacaoId: string;
  cia: string;
  coveragesAvailable: Record<string, Peril>;
  initialSelected: Record<string, string | null>;
  onClose: () => void;
  onApply: (result: RepricingResult) => void;
}

function sortPerils(available: Record<string, Peril>): [string, Peril][] { return Object.entries(available); }

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
  const revision = useRef(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; revision.current += 1; };
  }, []);

  const handleSelect = (perilSlug: string, optionSlug: string | null) => {
    revision.current += 1;
    setSelected((s) => ({ ...s, [perilSlug]: optionSlug }));
    setPricing(null);
    setError(null);
  };

  const handleReprice = async () => {
    const requestedRevision = ++revision.current;
    setLoading(true);
    setPricing(null);
    setError(null);
    try {
      const result = await api.cotacoes.repricing(cotacaoId, cia, selected);
      if (mounted.current && revision.current === requestedRevision) setPricing(result);
    } catch (e) {
      if (mounted.current && revision.current === requestedRevision) {
        setError(e instanceof Error ? e.message : "Erro ao recalcular.");
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
  };

  const handleApply = () => {
    if (!pricing || loading) return;
    onApply(pricing);
    onClose();
  };

  const perils = sortPerils(coveragesAvailable);
  const hasChanges = JSON.stringify(selected) !== JSON.stringify(initialSelected);

  return (
    <Dialog title="Configurar coberturas" onClose={onClose}>
      <div className="bg-surface rounded shadow-panel w-full max-w-2xl flex flex-col max-h-screen">
        <div className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0">
          <div>
            <p className="text-xs text-muted mt-1">Selecione as opções desejadas e recalcule o prêmio</p>
          </div>
          <button
            onClick={onClose}
            className="text-muted hover:text-muted text-xl leading-none"
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
              <div key={slug} className="border border-line rounded overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 bg-canvas ">
                  <span className="text-sm font-semibold text-ink ">{peril.name}</span>
                  {peril.mandatory ? (
                    <span className="text-xs font-bold uppercase tracking-wide text-danger bg-canvas border border-line rounded px-2 py-1">Obrigatório</span>
                  ) : (
                    <span className="text-xs text-muted">Opcional</span>
                  )}
                </div>
                <div className="divide-y divide-line ">
                  {!peril.mandatory && (
                    <label className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${current === null ? "bg-canvas " : "hover:bg-canvas "}`}>
                      <input
                        type="radio"
                        name={slug}
                        checked={current === null}
                        onChange={() => handleSelect(slug, null)}
                        className="accent-action"
                      />
                      <span className="text-sm text-muted flex-1">Não contratar</span>
                      <span className="text-xs text-muted">— /mês</span>
                    </label>
                  )}
                  {peril.peril_options.map((opt) => {
                    const isSelected = current === opt.slug;
                    return (
                      <label key={opt.slug} className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${isSelected ? "bg-canvas " : "hover:bg-canvas "}`}>
                        <input
                          type="radio"
                          name={slug}
                          checked={isSelected}
                          onChange={() => handleSelect(slug, opt.slug)}
                          className="accent-action"
                        />
                        <div className="flex-1 min-w-0">
                          <span className="text-sm font-medium text-ink ">{opt.name}</span>
                          {opt.deductible != null && /[1-9]/.test(opt.deductible) && (
                            <span className="text-xs text-muted ml-2">
                              Franquia: {formatBRL(String(opt.deductible))}
                            </span>
                          )}
                          {opt.coverage_amount != null && /[1-9]/.test(opt.coverage_amount) && (
                            <span className="text-xs text-muted ml-2">
                              Cobertura: {formatBRL(String(opt.coverage_amount))}
                            </span>
                          )}
                        </div>
                        <span className="text-sm font-mono font-semibold text-ink whitespace-nowrap">
                          {opt.price == null ? "Preço não informado" : /[1-9]/.test(opt.price) ? `+${formatBRL(opt.price)}/mês` : "incluso"}
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
          <div className="px-6 py-3 bg-canvas border-t border-line flex-shrink-0">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs text-success font-medium">Novo prêmio calculado</p>
                <p className="text-xl font-bold text-success ">
                  {formatBRL(pricing.monthly_total)}<span className="text-sm font-normal">/mês</span>
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs text-success ">Anual</p>
                <p className="text-lg font-semibold text-success ">{formatBRL(pricing.annual_total)}</p>
              </div>
            </div>
            {pricing.info && (
              <p className="text-xs text-success mt-1 truncate">{pricing.info}</p>
            )}
          </div>
        )}

        {error && (
          <div role="alert" className="px-6 py-2 text-sm text-danger border-t flex-shrink-0">{error}</div>
        )}

        <div className="px-6 py-4 border-t flex flex-wrap items-center justify-between gap-3 flex-shrink-0">
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={handleReprice} disabled={loading || !hasChanges}>
              {loading ? "Calculando…" : "Recalcular prêmio"}
            </Button>
            <Button onClick={handleApply} disabled={!pricing || loading}>
              Aplicar e fechar
            </Button>
          </div>
        </div>
      </div>
    </Dialog>
  );
}
