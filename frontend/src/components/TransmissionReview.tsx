import { useEffect, useState } from "react";
import { api, type TransmissionState } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/Pagination";

interface Props {
  cotacaoId: string;
  reloadKey?: number;
  disabled?: boolean;
  onStateChange?: (blocked: boolean) => void;
  onReviewed?: () => void;
}

export function TransmissionReview({ cotacaoId, reloadKey = 0, disabled = false, onStateChange, onReviewed }: Props) {
  const [state, setState] = useState<TransmissionState | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<"" | "nao_aceita" | "aceita">("");
  const [reason, setReason] = useState("");
  const [reference, setReference] = useState("");
  const [checked, setChecked] = useState(false);
  useEffect(() => {
    let disposed = false;
    setState(null); setError(""); setResult(""); setReason(""); setReference(""); setChecked(false);
    onStateChange?.(true);
    api.transmissoes.estado(cotacaoId).then(value => {
      if (!disposed) { setState(value); onStateChange?.(value.bloqueada); }
    }).catch(() => { if (!disposed) setError("Não foi possível consultar a transmissão. Atualize antes de continuar."); });
    return () => { disposed = true; };
  }, [cotacaoId, reloadKey, refresh, onStateChange]);

  async function review() {
    if (!state?.tentativa_id || !state.versao || busy || disabled) return;
    if (!result || !checked || reason.trim().length < 10 || (result === "aceita" && reference.trim().length < 3)) {
      setError("Informe o resultado, a justificativa e confirme a consulta. Para uma proposta aceita, informe também a referência.");
      return;
    }
    setBusy(true); setError("");
    try {
      const value = await api.transmissoes.conferir(cotacaoId, {
        tentativa_id: state.tentativa_id, versao: state.versao, resultado: result,
        conferido_na_seguradora: true, justificativa: reason.trim(),
        ...(reference.trim() ? { referencia: reference.trim() } : {}),
      });
      setState(value); onStateChange?.(value.bloqueada); onReviewed?.();
    } catch (e) {
      onStateChange?.(true);
      setError(e instanceof Error ? e.message : "Não foi possível registrar a conferência. Atualize e tente novamente.");
    } finally { setBusy(false); }
  }

  if (state?.estado === "sem_tentativa" && !error) return null;
  const canReview = state && ["iniciada", "incerta"].includes(state.estado);
  return <section aria-label="Conferência de transmissão" className="my-3 space-y-3 rounded-lg border border-line bg-canvas p-4 text-sm">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="font-semibold">Conferência de transmissão</h3>
      <Button type="button" size="sm" variant="outline" disabled={busy || disabled} onClick={() => setRefresh(n => n + 1)}>Atualizar situação</Button>
    </div>
    {!state && !error && <p role="status">Consultando a situação do envio…</p>}
    {state?.estado === "liberada" && <p role="status">Conferência registrada. Uma nova tentativa está liberada, sem envio automático.</p>}
    {state?.estado === "concluida" && <p>Já existe uma proposta registrada. Consulte o histórico; não reenvie.</p>}
    {state?.estado === "confirmada" && <p>Proposta aceita na seguradora: reenvio bloqueado. Esta conferência não cria parcelas ou proposta local; o registro local ainda precisa ser regularizado.</p>}
    {canReview && <>
      <p className="text-warning">Resultado não confirmado. Confira no portal da seguradora antes de decidir. Se o envio ainda estiver em andamento, aguarde: a liberação será recusada.</p>
      <label className="block space-y-1"><span>Resultado conferido</span><select aria-label="Resultado conferido" disabled={busy || disabled} value={result} onChange={e => setResult(e.target.value as typeof result)} className="w-full rounded border border-line bg-surface p-2">
        <option value="">Selecione</option><option value="nao_aceita">Não aceita — liberar nova tentativa</option><option value="aceita">Aceita — manter reenvio bloqueado</option>
      </select></label>
      <label className="block space-y-1"><span>Referência da conferência {result === "aceita" ? "(obrigatória)" : "(opcional)"}</span><Input disabled={busy || disabled} maxLength={100} value={reference} onChange={e => setReference(e.target.value)} placeholder="Protocolo da proposta ou atendimento; não cole links com tokens" /></label>
      <label className="block space-y-1"><span>Justificativa para auditoria</span><textarea disabled={busy || disabled} minLength={10} maxLength={500} rows={3} value={reason} onChange={e => setReason(e.target.value)} className="w-full rounded border border-line bg-surface p-2" placeholder="Descreva a conferência. Não inclua CPF, senha ou dados de risco." /></label>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy || disabled} checked={checked} onChange={e => setChecked(e.target.checked)} className="mt-1" /><span>Consultei a seguradora e confirmo o resultado informado. Minha decisão ficará registrada na auditoria.</span></label>
      <Button type="button" disabled={busy || disabled || !checked || !result} onClick={() => void review()}>{busy ? "Registrando…" : result === "nao_aceita" ? "Registrar e liberar nova tentativa" : "Registrar conferência"}</Button>
    </>}
    {error && <p role="alert" className="text-danger">{error}</p>}
  </section>;
}

function PendingContent() {
  const [data, setData] = useState<{ items: TransmissionState[]; total: number; pages: number } | null>(null);
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let disposed = false;
    setError(""); setData(null);
    api.transmissoes.pendentes(page).then(value => { if (!disposed) setData(value); })
      .catch(() => { if (!disposed) setError("Não foi possível carregar as pendências. Tente atualizar."); });
    return () => { disposed = true; };
  }, [page, refresh]);
  return <div className="space-y-3 pt-3">
    <p className="text-sm text-muted">Corretores conferem suas próprias cotações. Administradores também conferem as da equipe, dentro da mesma empresa.</p>
    <Button type="button" size="sm" variant="outline" onClick={() => setRefresh(n => n + 1)}>Atualizar pendências</Button>
    {error && <p role="alert" className="text-danger">{error}</p>}
    {!data && !error && <p role="status">Carregando pendências…</p>}
    {data?.total === 0 && <p>Nenhuma transmissão pendente de conferência.</p>}
    <ul className="space-y-2">{data?.items.map(item => <li key={item.cotacao_id}><Button type="button" variant="outline" onClick={() => setSelected(item.cotacao_id)} aria-pressed={selected === item.cotacao_id} className="h-auto whitespace-normal text-left">
      {item.cia} · Cotação {item.cotacao_id.slice(0, 8)} · {item.atualizado_em ? new Date(item.atualizado_em).toLocaleString("pt-BR") : ""}{item.estado === "confirmada" ? " · Aceita na seguradora" : " · A conferir"}
    </Button></li>)}</ul>
    {data && data.pages > 1 && <Pagination page={page} total={data.total} perPage={20} onChange={setPage} />}
    {selected && <TransmissionReview key={selected} cotacaoId={selected} onReviewed={() => setRefresh(n => n + 1)} />}
  </div>;
}

export function PendingTransmissions() {
  const [open, setOpen] = useState(false);
  return <details className="rounded-lg border border-line bg-surface p-4" onToggle={e => setOpen(e.currentTarget.open)}>
    <summary className="cursor-pointer font-medium">Conferir transmissões</summary>
    {open && <PendingContent />}
  </details>;
}
