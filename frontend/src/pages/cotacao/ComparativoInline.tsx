import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Cotacao, type ItemComparativo, type Proposta, type RepricingResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Money } from "@/components/Money";
import { InsurerResult } from "@/components/InsurerResult";
import { InsurerComparison } from "@/components/InsurerComparison";
import { Row, Stack } from "@/components/primitives";
import { CoverageConfigurator } from "./CoverageConfigurator";

interface Props {
  cotacao: Cotacao;
  cotacaoId: string;
  itens: ItemComparativo[];
  proposta: Proposta | null;
  onEmitir: (cia: string) => void;
  onRecotar: () => void;
  onCancel?: (cia: string) => void;
}
export function ComparativoInline({ cotacao, cotacaoId, itens, proposta, onEmitir, onRecotar, onCancel }: Props) {
  const navigate = useNavigate();
  const [configurando, setConfigurando] = useState<string | null>(null);
  const [overrides, setOverrides] = useState<Record<string, RepricingResult>>({});
  const effective = itens.map(item => {
    const override = overrides[item.cia];
    return override ? { ...item, premio_total: override.monthly_total, annual_total: override.annual_total, coverages_selected: override.coverages_selected, coberturas_comparaveis: override.coberturas_comparaveis } : item;
  });
  const active = effective.find(i => i.cia === configurando);
  const pending = effective.filter(i => ["pendente", "aguardando", "processando"].includes(i.status));
  const successes = effective.filter(i => ["sucesso", "restricao"].includes(i.status));
  if (proposta) return <Stack className="border border-line rounded p-4 bg-surface">
    <h2 className="text-success font-semibold">Proposta transmitida</h2>
    <p>Protocolo: {proposta.protocolo}</p>
    <p className="tabular-nums">{proposta.n_parcelas}× de <Money value={proposta.valor_parcela} /></p>
    {cotacao.cliente_id && <Button variant="outline" onClick={() => navigate(`/clientes/${cotacao.cliente_id}`)}>Ver timeline do cliente</Button>}
  </Stack>;
  return <Stack>
    <Row className="justify-between flex-wrap">
      <h2 className="text-lg font-semibold">Resultado da cotação</h2>
      <p className="text-xs text-muted tabular-nums" role="status">{effective.length - pending.length} de {effective.length} consultas concluídas</p>
    </Row>
    {!pending.length && !successes.length && (effective.length > 0 || cotacao.status === "erro") &&
      <div className="border border-line rounded p-3" role="status"><h3 className="font-semibold">Nenhuma proposta disponível</h3><p>Confira o retorno de cada seguradora abaixo e tente recotar.</p></div>}
    {effective.length === 0 && cotacao.status !== "erro" && <p role="status">{["aguardando", "pendente", "processando"].includes(cotacao.status) ? "Aguardando a identificação das consultas pelo servidor…" : "Nenhum resultado disponível. Recarregue a página para tentar recuperar as consultas."}</p>}
    <div className="result-grid">{effective.map(item => <InsurerResult key={item.cia} result={item} actions={
      <>
        {["aguardando", "pendente", "processando"].includes(item.status) && onCancel && <Button variant="outline" onClick={() => onCancel(item.cia)}>Cancelar consulta</Button>}
        {["sucesso", "restricao"].includes(item.status) && !!item.coverages_available && <Button variant="outline" onClick={() => setConfigurando(item.cia)}>Configurar coberturas</Button>}
        {["sucesso", "restricao"].includes(item.status) && item.cia === "justos" && <a className="control inline-flex items-center rounded border border-line px-3 text-sm" href={api.cotacoes.pdfUrl(cotacaoId, "cotacao")} target="_blank" rel="noreferrer">Baixar PDF</a>}
        {["sucesso", "restricao"].includes(item.status) && <Button onClick={() => onEmitir(item.cia)}>Transmitir proposta</Button>}
      </>
    } />)}</div>
    <InsurerComparison items={effective} />
    <Row className="flex-wrap">
      <a className="control inline-flex items-center rounded border border-line px-3" href={api.cotacoes.comparativoPdfUrl(cotacaoId)} target="_blank" rel="noreferrer">Baixar comparativo em PDF</a>
      <Button variant="outline" onClick={onRecotar}>Recotar</Button>
    </Row>
    {active?.coverages_available && <CoverageConfigurator cotacaoId={cotacaoId} cia={active.cia}
      coveragesAvailable={active.coverages_available} initialSelected={active.coverages_selected ?? {}}
      onClose={() => setConfigurando(null)} onApply={result => { setOverrides(old => ({...old, [active.cia]:result})); setConfigurando(null); }} />}
  </Stack>;
}
