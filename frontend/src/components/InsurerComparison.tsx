import type { ItemComparativo } from "@/lib/api";
import { vaiComparar } from "@/lib/comparativo";
import { DataTable } from "./DataTable";
import { InsurerIdentity } from "./InsurerIdentity";
import { Money } from "./Money";
import { StatusBadge } from "./StatusBadge";

export function InsurerComparison({ items }: { items: ItemComparativo[] }) {
  const concepts = new Map<string, { label: string; count: number }>();
  for (const item of items) {
    for (const coverage of item.coberturas_comparaveis ?? []) {
      const old = concepts.get(coverage.conceito_id);
      concepts.set(coverage.conceito_id, { label: coverage.nome_canonico, count: (old?.count ?? 0) + 1 });
    }
  }
  if (!items.length || !vaiComparar(items)) return null;
  const temAnual = items.some(i => i.annual_total != null);
  return <section className="comparison-panel">
    <div className="p-4"><h2 className="text-base font-semibold">Compare as condições</h2><p className="text-sm text-muted mt-1">{items.length} seguradoras, na mesma ordem em todas as linhas.</p></div>
    <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Comparativo entre seguradoras">
    <DataTable className="comparison" style={{ minWidth: `${176 + items.length * 208}px` }}>
      <caption className="sr-only">Condições e coberturas por seguradora</caption>
      <thead><tr><th scope="col">Condição ou cobertura</th>{items.map(i => <th key={i.cia} scope="col"><InsurerIdentity cia={i.cia} nome={i.nome} logoUrl={i.logo_url} /></th>)}</tr></thead>
      <tbody>
        <tr><th scope="row">Resultado</th>{items.map(i => <td key={i.cia}><StatusBadge status={i.status} /></td>)}</tr>
        <tr><th scope="row">Prêmio informado</th>{items.map(i => <td key={i.cia}><Money value={i.premio_total} /></td>)}</tr>
        {temAnual && <tr><th scope="row">Prêmio anual</th>{items.map(i => <td key={i.cia}><Money value={i.annual_total} /></td>)}</tr>}
        <tr><th scope="row">Vistoria prévia</th>{items.map(i => <td key={i.cia}>{["sucesso", "restricao"].includes(i.status) ? i.necessita_vistoria ? "Obrigatória" : "Não solicitada" : ["aguardando", "pendente", "processando"].includes(i.status) ? "Aguardando resultado" : "Não disponível"}</td>)}</tr>
        {[...concepts].map(([id, concept]) => <tr key={id}><th scope="row">{concept.label}{concept.count === 1 && items.length > 1 && <span className="block text-xs text-muted">Informada em um resultado</span>}</th>{items.map(item => {
          const coverage = item.coberturas_comparaveis?.find(c => c.conceito_id === id);
          return <td key={item.cia}>{coverage ? <>{coverage.limite_descricao ?? <Money value={coverage.limite} />}{coverage.nome_original !== concept.label && <span className="block text-xs text-muted">{coverage.nome_original}</span>}</> : ["aguardando", "pendente", "processando"].includes(item.status) ? "Aguardando resultado" : "Não informado"}</td>;
        })}</tr>)}
      </tbody>
    </DataTable>
    </div>
    <p className="p-4 text-xs text-muted">
      {concepts.size
        ? "Ausência de informação não significa ausência de cobertura. Compare também franquias e condições antes de revisar uma proposta."
        : "As seguradoras não informaram coberturas comparáveis. Consulte as condições individuais antes de revisar uma proposta; equivalência não confirmada."}
    </p>
  </section>;
}
