import { useEffect, useState } from "react";
import { api, type Proposta, type Seguradora } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Dialog } from "@/components/Dialog";
import { Field, Stack, Row } from "@/components/primitives";

interface Props { cotacaoId: string; ramo?: string; cia: string; vigenciaInicio?: string; onClose: () => void; onSuccess: (p: Proposta) => void }
export function TransmitirModal({ cotacaoId, ramo, cia, vigenciaInicio, onClose, onSuccess }: Props) {
  const [carrier, setCarrier] = useState<Seguradora | null>(null);
  const [plano, setPlano] = useState("");
  const [mode, setMode] = useState("");
  const [commission, setCommission] = useState("15");
  const [vigencia, setVigencia] = useState(vigenciaInicio ?? new Date().toISOString().slice(0,10));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let disposed = false;
    api.dominios.seguradoras().then(items => {
      if (disposed) return;
      const selected = items.find(item => item.id === cia);
      if (!selected) { setError("Seguradora indisponível. Atualize a cotação antes de transmitir."); return; }
      setCarrier(selected);
      setPlano(selected.planos[0]?.codigo ?? "");
      setMode(selected.modos_transmissao[0]?.id ?? "");
    }).catch(() => { if (!disposed) setError("Não foi possível carregar as condições de transmissão. Feche e tente novamente."); });
    if (ramo) api.comissoes.get(cia, ramo).then(config => { if (!disposed) setCommission(String(Number(config.pct_padrao) * 100)); }).catch(() => undefined);
    return () => { disposed = true; };
  }, [cia, ramo]);
  async function transmit(event: React.FormEvent) {
    event.preventDefault();
    const plan = carrier?.planos.find(p => p.codigo === plano);
    if (!carrier || !plan || loading) return;
    const percent = Number(commission);
    if (!Number.isFinite(percent) || percent < 0 || percent > 30) { setError("Informe uma comissão entre 0% e 30%."); return; }
    setLoading(true); setError("");
    const selectedMode = carrier.modos_transmissao.find(m => m.id === mode);
    const business = { ...selectedMode?.dados_negocio };
    if (selectedMode?.campo_parcelas) business[selectedMode.campo_parcelas] = plan.parcelas;
    try {
      onSuccess(await api.cotacoes.transmitir(cotacaoId, { cia, plano_pagamento: plan.codigo, n_parcelas: plan.parcelas, comissao_pct: (percent / 100).toFixed(4), inicio_vigencia: vigencia, dados_negocio: business }));
    } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível transmitir. Confira a proposta e tente novamente."); }
    finally { setLoading(false); }
  }
  return <Dialog title="Transmitir proposta" onClose={() => { if (!loading) onClose(); }}>
    <form onSubmit={transmit}><Stack>
      <p>Confira as condições de {carrier?.nome ?? "transmissão"}. A proposta será transmitida somente após sua confirmação.</p>
      {!!carrier?.modos_transmissao.length && <Field label="Tipo de pagamento"><Select value={mode} onChange={e=>setMode(e.target.value)}>{carrier.modos_transmissao.map(m=><option key={m.id} value={m.id}>{m.label}</option>)}</Select></Field>}
      <Field label="Parcelamento"><Select required value={plano} onChange={e=>setPlano(e.target.value)}><option value="">Selecione um plano</option>{carrier?.planos.map(p=><option key={p.codigo} value={p.codigo}>{p.descricao}</option>)}</Select></Field>
      <Field label="Comissão (%)"><Input type="number" min="0" max="30" step="0.01" required value={commission} onChange={e=>setCommission(e.target.value)} /></Field>
      <Field label="Início da vigência"><Input type="date" required value={vigencia} onChange={e=>setVigencia(e.target.value)} /></Field>
      {error && <p role="alert" className="text-danger">{error}</p>}
      <Row className="justify-end"><Button type="button" variant="outline" disabled={loading} onClick={onClose}>Voltar</Button><Button type="submit" disabled={!carrier || !plano || loading}>{loading ? "Transmitindo…" : "Confirmar transmissão"}</Button></Row>
    </Stack></form>
  </Dialog>;
}
