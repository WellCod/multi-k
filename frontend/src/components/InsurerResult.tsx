import { useEffect, useState, type ReactNode } from "react";
import { Money } from "./Money";
import { InsurerIdentity } from "./InsurerIdentity";
import { StatusBadge } from "./StatusBadge";
import { Stack, Row } from "./primitives";

export interface InsurerView {
  cia: string;
  nome?: string;
  logo_url?: string | null;
  status: string;
  premio_total: string | null;
  annual_total?: string | null;
  necessita_vistoria: boolean;
  mensagens: string[];
  info?: string | null;
  restricoes: { codigo: string; mensagem: string }[];
  iniciado_em?: string | null;
}

export function InsurerResult({ result, actions }: { result: InsurerView; actions?: ReactNode }) {
  const pending = ["aguardando", "pendente", "processando"].includes(result.status);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [pending]);
  const started = result.iniciado_em ? Date.parse(result.iniciado_em) : NaN;
  const seconds = Number.isFinite(started) ? Math.max(0, Math.floor((now - started) / 1000)) : null;
  return <article className="quote-summary min-w-0" aria-label={result.nome || result.cia}>
    <Stack gap={3}>
      <Row className="justify-between flex-wrap">
        <h3 className="font-semibold"><InsurerIdentity cia={result.cia} nome={result.nome} logoUrl={result.logo_url} /></h3>
        <StatusBadge status={result.status} />
      </Row>
      {pending ? <p role="status">Consultando…{seconds !== null && <span className="tabular-nums"> {seconds}s</span>}</p>
        : <div><p className="text-xs text-muted mb-1">Valor informado pela seguradora</p><p className="text-xl font-semibold"><Money value={result.premio_total} /></p></div>}
      {!pending && result.annual_total && <div><p className="text-xs text-muted">Opção anual</p><p className="font-medium"><Money value={result.annual_total} /></p></div>}
      {result.necessita_vistoria && <p className="text-warning font-medium">Vistoria prévia obrigatória — confirme o prazo de emissão.</p>}
      {result.restricoes.map(r => <p className="text-warning text-xs" key={r.codigo}>{r.mensagem}</p>)}
      {result.mensagens.map((message, index) => <p className="text-xs text-muted" key={index}>{message}</p>)}
      {result.info && !result.mensagens.includes(result.info) && <p className="text-xs text-muted"><span className="font-medium">Observação da seguradora:</span> {result.info}</p>}
      {!pending && result.status === "erro" && !result.mensagens.length && <p className="text-xs text-danger">Não foi possível obter o resultado. Tente recotar nesta seguradora.</p>}
      {result.status === "cancelado" && !result.mensagens.length && <p className="text-xs text-muted">Consulta cancelada. Nenhuma proposta foi transmitida por esta ação.</p>}
      {actions && <Row className="flex-wrap border-t border-line pt-3">{actions}</Row>}
    </Stack>
  </article>;
}
