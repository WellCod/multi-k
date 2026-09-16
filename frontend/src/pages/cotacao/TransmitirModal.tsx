import { useEffect, useState } from "react";
import { api, type Proposta, type Seguradora, type PaymentOption } from "@/lib/api";
import { formatBRL } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Dialog } from "@/components/Dialog";
import { Field, Stack, Row } from "@/components/primitives";
import { TransmissionReview } from "@/components/TransmissionReview";

interface Props { cotacaoId: string; ramo?: string; cia: string; revisaoBase?: string; vigenciaInicio?: string; onClose: () => void; onSuccess: (p: Proposta) => void }
export function TransmitirModal({ cotacaoId, ramo, cia, revisaoBase, vigenciaInicio, onClose, onSuccess }: Props) {
  const [carrier, setCarrier] = useState<Seguradora | null>(null);
  const [plano, setPlano] = useState("");
  const [mode, setMode] = useState("");
  const [options, setOptions] = useState<PaymentOption[] | null>(null);
  const [commission, setCommission] = useState("15");
  const [quotedCommission, setQuotedCommission] = useState<string | null>(null);
  const [vigencia, setVigencia] = useState(vigenciaInicio ?? new Date().toISOString().slice(0,10));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [transmissionBlocked, setTransmissionBlocked] = useState(true);
  const [reviewVersion, setReviewVersion] = useState(0);
  useEffect(() => {
    let disposed = false;
    api.dominios.seguradoras().then(items => {
      if (disposed) return;
      const selected = items.find(item => item.id === cia);
      if (!selected) { setError("Seguradora indisponível. Atualize a cotação antes de transmitir."); return; }
      setCarrier(selected);
      setPlano(cia === "justos" ? "" : selected.planos[0]?.codigo ?? "");
      setMode(selected.modos_transmissao[0]?.id ?? "");
    }).catch(() => { if (!disposed) setError("Não foi possível carregar as condições de transmissão. Feche e tente novamente."); });
    if (ramo) api.comissoes.get(cia, ramo).then(config => { if (!disposed) setCommission(String(Number(config.pct_padrao) * 100)); }).catch(() => undefined);
    return () => { disposed = true; };
  }, [cia, ramo]);
  useEffect(() => {
    if (cia !== "justos") return;
    let disposed = false;
    setOptions(null); setPlano("");
    api.cotacoes.comparativo(cotacaoId).then(items => {
      if (disposed) return;
      const offer = items.find(item => item.cia === cia);
      if (!offer || offer.revisao_base !== revisaoBase) {
        setError("A revisão mudou. Feche e atualize o comparativo."); return;
      }
      setOptions(offer.condicoes_pagamento ?? []);
      // A comissão entra no preço da seguradora: exibir a cotada, não a padrão.
      const quoted = offer.comissao_pct_cotada ?? null;
      setQuotedCommission(quoted);
      if (quoted !== null) setCommission(String(Number(quoted) * 100));
    }).catch(() => { if (!disposed) setError("Não foi possível consultar as condições. Feche e tente novamente."); });
    return () => { disposed = true; };
  }, [cia, cotacaoId, revisaoBase]);
  async function transmit(event: React.FormEvent) {
    event.preventDefault();
    const option = cia === "justos" && plano !== "" ? options?.[Number(plano)] : undefined;
    const plan = cia === "justos" ? (option && option.valor_parcela !== null && option.valor_total !== null ? {
      codigo: option.periodicidade === "monthly" ? "MENSAL" : `ANUAL_${option.parcelas}X`, parcelas: option.parcelas,
    } : undefined) : carrier?.planos.find(p => p.codigo === plano);
    if (!carrier || !plan || !revisaoBase || loading || transmissionBlocked) return;
    const percent = Number(commission);
    if (!Number.isFinite(percent) || percent <= 0 || percent > 30) { setError("Informe uma comissão entre 0,01% e 30%."); return; }
    setLoading(true); setError("");
    const selectedMode = carrier.modos_transmissao.find(m => m.id === mode);
    const business = { ...selectedMode?.dados_negocio };
    if (selectedMode?.campo_parcelas) business[selectedMode.campo_parcelas] = plan.parcelas;
    try {
      onSuccess(await api.cotacoes.transmitir(cotacaoId, { ...(option ? { opcao_pagamento: Number(plano) } : {}), revisao_base: revisaoBase, chave_idempotencia: crypto.randomUUID(), cia, plano_pagamento: plan.codigo, n_parcelas: plan.parcelas, comissao_pct: (percent / 100).toFixed(4), inicio_vigencia: vigencia, dados_negocio: business }));
    } catch (e) { setTransmissionBlocked(true); setReviewVersion(v => v + 1); setError(e instanceof Error ? e.message : "Não foi possível confirmar o envio. Consulte a situação antes de tentar novamente."); }
    finally { setLoading(false); }
  }
  return <Dialog title="Transmitir proposta" onClose={() => { if (!loading) onClose(); }}>
    <TransmissionReview cotacaoId={cotacaoId} reloadKey={reviewVersion} disabled={loading} onStateChange={setTransmissionBlocked} />
    <form onSubmit={transmit}><Stack>
      <p>Confira as condições de {carrier?.nome ?? "transmissão"}. A proposta será transmitida somente após sua confirmação.</p>
      {!revisaoBase && <p role="alert" className="text-danger">Atualize o comparativo para carregar a revisão antes de transmitir.</p>}
      {cia === "justos" ? <Field label="Condição confirmada pela seguradora">
        <Select required disabled={loading || options === null} value={plano} onChange={e => setPlano(e.target.value)}>
          <option value="">Selecione uma condição</option>
          {options?.map((option, index) => <option key={index} value={String(index)} disabled={option.valor_parcela === null || option.valor_total === null || (option.periodicidade === "monthly" && option.parcelas !== 1)}>
            {option.periodicidade === "monthly" ? "Mensal — ciclo" : `Anual — ${option.parcelas}x`} · {option.valor_parcela === null ? "Parcela não informada" : formatBRL(option.valor_parcela)} · Total {option.valor_total === null ? "não informado" : formatBRL(option.valor_total)}
          </option>)}
        </Select>
        {options?.length === 0 && <p className="text-warning">Condições não informadas. Recalcule as coberturas antes de transmitir.</p>}
      </Field> : <>
        {!!carrier?.modos_transmissao.length && <Field label="Tipo de pagamento"><Select value={mode} onChange={e=>setMode(e.target.value)}>{carrier.modos_transmissao.map(m=><option key={m.id} value={m.id}>{m.label}</option>)}</Select></Field>}
        <Field label="Parcelamento"><Select required value={plano} onChange={e=>setPlano(e.target.value)}><option value="">Selecione um plano</option>{carrier?.planos.map(p=><option key={p.codigo} value={p.codigo}>{p.descricao}</option>)}</Select></Field>
      </>}
      <Field label="Comissão (%)">
        <Input type="number" min="0.01" max="30" step="0.01" required readOnly={quotedCommission !== null} value={commission} onChange={e=>setCommission(e.target.value)} />
        {quotedCommission !== null && <p className="text-xs text-muted">Comissão usada pela seguradora no cálculo do prêmio. Para alterar, recotize.</p>}
      </Field>
      <Field label="Início da vigência"><Input type="date" required value={vigencia} onChange={e=>setVigencia(e.target.value)} /></Field>
      {error && (
        <details open className="rounded border border-danger/40 bg-danger/5 p-2 text-sm text-danger">
          <summary className="cursor-pointer font-medium">Erro na transmissão</summary>
          <pre className="mt-1 whitespace-pre-wrap break-all text-xs">{error}</pre>
        </details>
      )}
      <Row className="justify-end"><Button type="button" variant="outline" disabled={loading} onClick={onClose}>Voltar</Button><Button type="submit" disabled={!carrier || !plano || !revisaoBase || loading || transmissionBlocked}>{loading ? "Transmitindo…" : "Confirmar transmissão"}</Button></Row>
    </Stack></form>
  </Dialog>;
}
