import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Cliente, type ClientePatch, type CotacaoResumo, type Dominio, type Imovel, type TimelineItem, type Veiculo } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatBRL } from "@/lib/utils";

function fmtData(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const TIPO_CONFIG: Record<string, { label: string; dot: string }> = {
  "cliente.criado": { label: "Cliente cadastrado", dot: "bg-action" },
  "cotacao.criada": { label: "Cotação criada", dot: "bg-action" },
  "proposta.transmitida": { label: "Proposta transmitida", dot: "bg-success" },
};

function TimelineCard({ item, isLast }: { item: TimelineItem; isLast: boolean }) {
  const cfg = TIPO_CONFIG[item.tipo] ?? { label: item.tipo, dot: "bg-surface" };

  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div className={`w-2.5 h-2.5 rounded-full mt-2 flex-shrink-0 ${cfg.dot}`} />
        {!isLast && (
          <div className="w-px flex-1 border-l-2 border-dashed border-line mt-1" />
        )}
      </div>
      <div className="pb-4 flex-1">
        <p className="text-xs text-muted ">{fmtData(item.data)}</p>
        <p className="text-sm font-medium text-ink mt-1">{cfg.label}</p>
        <div className="mt-1 text-xs text-muted space-y-1">
          {item.tipo === "cotacao.criada" && (
            <>
              <p>Ramo: <span className="font-medium text-ink ">{String(item.dados.ramo)}</span></p>
              <p>Prêmio: <span className="font-medium text-ink ">{formatBRL(item.dados.premio_total as string | null)}</span></p>
              <p>Status: <span className="font-medium text-ink ">{String(item.dados.status)}</span></p>
            </>
          )}
          {item.tipo === "proposta.transmitida" && (
            <>
              <p>Protocolo: <span className="font-mono font-medium text-ink ">{String(item.dados.protocolo)}</span></p>
              <p>Parcelas: <span className="font-medium text-ink ">{Number(item.dados.n_parcelas)}× de {formatBRL(item.dados.valor_parcela as string)}</span></p>
              {item.dados.numero_apolice && (
                <p>Apólice: <span className="font-mono font-medium text-success ">{String(item.dados.numero_apolice)}</span></p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const INFO_ICONS: Record<string, string> = {
  "E-mail": "📧",
  "Telefone": "📱",
  "Nascimento": "🎂",
  "Estado civil": "💍",
  "Profissão": "💼",
  "Cadastrado em": "📅",
};

function InfoRow({ label, value }: { label: string; value: string }) {
  const icon = INFO_ICONS[label];
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted ">
        {icon && <span className="mr-1">{icon}</span>}
        {label}
      </p>
      <p className="text-sm font-medium text-ink mt-1">{value}</p>
    </div>
  );
}

const SELECT_CLASS =
  "mt-1 w-full border border-line rounded px-3 py-2 text-sm bg-surface text-ink ";

function EditForm({
  cliente,
  onSave,
  onCancel,
}: {
  cliente: Cliente;
  onSave: (updated: Cliente) => void;
  onCancel: () => void;
}) {
  const [nome, setNome] = useState(cliente.nome);
  const [email, setEmail] = useState(cliente.email ?? "");
  const [telefone, setTelefone] = useState(cliente.telefone ?? "");
  const [dataNasc, setDataNasc] = useState(cliente.data_nascimento ?? "");
  const [estadoCivil, setEstadoCivil] = useState(cliente.estado_civil ?? "");
  const [profissao, setProfissao] = useState(cliente.profissao ?? "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [estadosCivis, setEstadosCivis] = useState<Dominio[]>([]);
  const [profissoes, setProfissoes] = useState<Dominio[]>([]);

  useEffect(() => {
    Promise.all([
      api.dominios.list("estado_civil"),
      api.dominios.list("profissao"),
    ]).then(([ec, pr]) => {
      setEstadosCivis(ec);
      setProfissoes(pr);
    }).catch(() => undefined);
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr(null);
    const patch: ClientePatch = { nome };
    if (email) patch.email = email;
    if (telefone) patch.telefone = telefone;
    if (dataNasc) patch.data_nascimento = dataNasc;
    if (estadoCivil) patch.estado_civil = estadoCivil;
    if (profissao) patch.profissao = profissao;
    try {
      const updated = await api.clientes.update(cliente.id, patch);
      onSave(updated);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {err && (
        <div className="rounded border border-line bg-canvas p-3 text-sm text-danger ">
          {err}
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-muted ">Nome *</label>
          <Input value={nome} onChange={(e) => setNome(e.target.value)} required autoFocus className="mt-1 rounded" />
        </div>
        <div>
          <label className="text-xs text-muted ">E-mail</label>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 rounded" />
        </div>
        <div>
          <label className="text-xs text-muted ">Telefone</label>
          <Input value={telefone} onChange={(e) => setTelefone(e.target.value)} className="mt-1 rounded" />
        </div>
        <div>
          <label className="text-xs text-muted ">Data de nascimento</label>
          <Input type="date" value={dataNasc} onChange={(e) => setDataNasc(e.target.value)} className="mt-1 rounded" />
        </div>
        <div>
          <label className="text-xs text-muted ">Estado civil</label>
          <select
            value={estadoCivil}
            onChange={(e) => setEstadoCivil(e.target.value)}
            className={SELECT_CLASS}
          >
            <option value="">— selecione —</option>
            {estadosCivis.map((d) => (
              <option key={d.codigo} value={d.codigo}>{d.descricao}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-muted ">Profissão</label>
          <select
            value={profissao}
            onChange={(e) => setProfissao(e.target.value)}
            className={SELECT_CLASS}
          >
            <option value="">— selecione —</option>
            {profissoes.map((d) => (
              <option key={d.codigo} value={d.codigo}>{d.descricao}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="flex gap-2 justify-end">
        <Button type="button" variant="outline" size="sm" onClick={onCancel} disabled={saving}>
          Cancelar
        </Button>
        <Button type="submit" size="sm" disabled={saving || !nome.trim()}>
          {saving ? (
            <>
              <svg className="animate-spin h-3.5 w-3.5 mr-2 inline" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
              Aguarde...
            </>
          ) : "Salvar"}
        </Button>
      </div>
    </form>
  );
}

function VeiculosSection({ clienteId }: { clienteId: string }) {
  const [veiculos, setVeiculos] = useState<Veiculo[] | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let disposed = false;
    setError(false);
    setVeiculos(null);
    api.clientes.veiculos(clienteId)
      .then(items => { if (!disposed) setVeiculos(items); })
      .catch(() => { if (!disposed) setError(true); });
    return () => { disposed = true; };
  }, [clienteId, attempt]);

  if (error) return <div role="alert" className="border border-line rounded p-4 space-y-2">
    <p className="text-sm text-danger">Não foi possível carregar veículos.</p>
    <Button variant="outline" onClick={() => setAttempt(value => value + 1)}>Tentar novamente</Button>
  </div>;
  if (veiculos === null) return <p role="status" className="text-sm text-muted">Carregando veículos…</p>;

  if (veiculos === null) return null;
  if (veiculos.length === 0) return null;

  return (
    <div className="bg-surface border border-line rounded p-4">
      <h2 className="text-sm font-semibold text-ink mb-3">
        Veículos ({veiculos.length})
      </h2>
      <div className="space-y-2">
        {veiculos.map((v) => (
          <div
            key={v.id}
            className="flex items-center justify-between text-sm border border-line rounded px-3 py-2 hover:bg-canvas transition-colors"
          >
            <span className="font-bold text-ink flex items-center gap-2">
              <span>🚗</span>
              {v.marca} {v.modelo}
            </span>
            <div className="text-xs text-muted flex gap-2 items-center">
              <span>{v.ano_fabricacao}/{v.ano_modelo}</span>
              <span className="capitalize">{v.combustivel}</span>
              {v.placa && (
                <span className="font-mono uppercase bg-canvas px-2 rounded">
                  {v.placa}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const STATUS_CLS: Record<string, string> = {
  sucesso: "bg-canvas text-success ",
  aguardando: "bg-canvas text-warning ",
  processando: "bg-canvas text-action ",
  restricao: "bg-canvas text-warning ",
  erro: "bg-canvas text-danger ",
};

function CotacoesSection({ clienteId }: { clienteId: string }) {
  const [cotacoes, setCotacoes] = useState<CotacaoResumo[] | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let disposed = false;
    setError(false);
    setCotacoes(null);
    api.clientes.cotacoes(clienteId)
      .then(items => { if (!disposed) setCotacoes(items); })
      .catch(() => { if (!disposed) setError(true); });
    return () => { disposed = true; };
  }, [clienteId, attempt]);

  if (error) return <div role="alert" className="border border-line rounded p-4 space-y-2">
    <p className="text-sm text-danger">Não foi possível carregar cotações.</p>
    <Button variant="outline" onClick={() => setAttempt(value => value + 1)}>Tentar novamente</Button>
  </div>;
  if (cotacoes === null) return <p role="status" className="text-sm text-muted">Carregando cotações…</p>;

  if (cotacoes === null || cotacoes.length === 0) return null;

  return (
    <div className="bg-surface border border-line rounded p-4">
      <h2 className="text-sm font-semibold text-ink mb-3">
        Cotações ({cotacoes.length})
      </h2>
      <div className="space-y-2">
        {cotacoes.map((c) => (
          <div
            key={c.id}
            className="flex items-center justify-between text-sm border border-line rounded px-3 py-2 hover:bg-canvas transition-colors"
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium whitespace-nowrap ${STATUS_CLS[c.status] ?? "bg-canvas text-muted "}`}>
                {c.status}
              </span>
              <span className="font-medium text-ink capitalize">{c.ramo}</span>
              {c.numero_apolice && (
                <span className="text-xs font-mono text-success truncate">
                  #{c.numero_apolice}
                </span>
              )}
            </div>
            <div className="text-xs text-muted flex gap-3 items-center flex-shrink-0">
              {c.premio_total && (
                <span className="font-medium text-ink ">
                  {formatBRL(c.premio_total)}
                </span>
              )}
              <span>{new Date(c.criado_em).toLocaleDateString("pt-BR")}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ImoveisSection({ clienteId }: { clienteId: string }) {
  const [imoveis, setImoveis] = useState<Imovel[] | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let disposed = false;
    setError(false);
    setImoveis(null);
    api.clientes.imoveis(clienteId)
      .then(items => { if (!disposed) setImoveis(items); })
      .catch(() => { if (!disposed) setError(true); });
    return () => { disposed = true; };
  }, [clienteId, attempt]);

  if (error) return <div role="alert" className="border border-line rounded p-4 space-y-2">
    <p className="text-sm text-danger">Não foi possível carregar imóveis.</p>
    <Button variant="outline" onClick={() => setAttempt(value => value + 1)}>Tentar novamente</Button>
  </div>;
  if (imoveis === null) return <p role="status" className="text-sm text-muted">Carregando imóveis…</p>;

  if (imoveis === null) return null;
  if (imoveis.length === 0) return null;

  return (
    <div className="bg-surface border border-line rounded p-4">
      <h2 className="text-sm font-semibold text-ink mb-3">
        Imóveis ({imoveis.length})
      </h2>
      <div className="space-y-2">
        {imoveis.map((im) => (
          <div
            key={im.id}
            className="flex items-center justify-between text-sm border border-line rounded px-3 py-2 hover:bg-canvas transition-colors"
          >
            <span className="font-bold text-ink capitalize flex items-center gap-2">
              <span>🏠</span>
              {im.tipo_imovel.replace("_", " ")}
            </span>
            <div className="text-xs text-muted flex gap-2 items-center">
              <span className="font-mono bg-canvas px-2 rounded">
                CEP {im.cep}
              </span>
              <span className="capitalize">{im.tipo_construcao.replace("_", " ")}</span>
              {im.logradouro && (
                <span className="truncate max-w-36">
                  {im.logradouro}{im.numero ? `, ${im.numero}` : ""}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function getInitials(nome: string): string {
  const parts = nome.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function ClienteDetailPage() {
  const { clienteId } = useParams<{ clienteId: string }>();
  const navigate = useNavigate();
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    if (!clienteId) return;
    let disposed = false;
    setLoading(true);
    setErr(null);
    setCliente(null);
    setTimeline([]);
    setEditing(false);
    setShowArchiveConfirm(false);
    Promise.all([api.clientes.get(clienteId), api.clientes.timeline(clienteId)])
      .then(([c, t]) => {
        if (disposed) return;
        setCliente(c);
        setTimeline([...t].reverse());
      })
      .catch((e: unknown) => {
        if (!disposed) setErr(e instanceof Error ? e.message : "Não foi possível carregar o cliente.");
      })
      .finally(() => { if (!disposed) setLoading(false); });
    return () => { disposed = true; };
  }, [clienteId, loadAttempt]);

  if (loading || (!err && cliente?.id !== clienteId)) return (
    <div role="status" aria-label="Carregando cliente" className="max-w-2xl space-y-6 animate-pulse">
      <div className="flex items-center gap-4">
        <div className="h-4 w-16 bg-surface rounded" />
        <div className="h-6 w-48 bg-surface rounded" />
      </div>
      <div className="bg-surface border border-line rounded p-4 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="space-y-1">
              <div className="h-3 w-20 bg-surface rounded" />
              <div className="h-4 w-32 bg-surface rounded" />
            </div>
          ))}
        </div>
      </div>
      <div className="space-y-3">
        <div className="h-5 w-32 bg-surface rounded" />
        {[...Array(3)].map((_, i) => (
          <div key={i} className="flex gap-4">
            <div className="w-2.5 h-2.5 rounded-full bg-surface mt-2 flex-shrink-0" />
            <div className="flex-1 space-y-1 pb-4">
              <div className="h-3 w-24 bg-surface rounded" />
              <div className="h-4 w-36 bg-surface rounded" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
  if (err)
    return (
      <div role="alert" className="rounded border border-line bg-canvas p-4 text-sm space-y-3">
        <p className="text-danger">{err}</p>
        <Button variant="outline" onClick={() => setLoadAttempt(value => value + 1)}>Tentar novamente</Button>
      </div>
    );
  if (!cliente) return null;

  async function handleArchive() {
    if (!clienteId) return;
    setArchiving(true);
    try {
      await api.clientes.archive(clienteId);
      navigate("/clientes");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Erro ao arquivar");
      setShowArchiveConfirm(false);
    } finally {
      setArchiving(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      {showArchiveConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-surface rounded border border-line p-6 max-w-sm w-full mx-4 space-y-4">
            <h3 className="text-base font-semibold text-ink ">Arquivar cliente</h3>
            <p className="text-sm text-muted ">Tem certeza? Esta ação pode ser desfeita pelo administrador.</p>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setShowArchiveConfirm(false)} className="px-4 py-2 text-sm rounded border border-line text-ink hover:bg-canvas transition-colors">Cancelar</button>
              <button onClick={handleArchive} disabled={archiving} className="px-4 py-2 text-sm rounded bg-danger text-ink hover:bg-danger transition-colors disabled:opacity-60">
                {archiving ? (
                  <>
                    <svg className="animate-spin h-3.5 w-3.5 mr-2 inline" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                    </svg>
                    Aguarde...
                  </>
                ) : "Arquivar"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1 text-sm text-muted hover:text-action transition-colors px-2 py-1 rounded hover:bg-canvas "
        >
          <span>←</span>
          <span>Voltar</span>
        </button>
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-full bg-canvas text-action flex items-center justify-center font-bold text-sm flex-shrink-0">
            {getInitials(cliente.nome)}
          </div>
          <h1 className="text-xl font-semibold text-ink truncate">{cliente.nome}</h1>
        </div>
        <a
          href={api.clientes.fichaUrl(clienteId!)}
          target="_blank"
          rel="noreferrer"
          title="Exportar ficha do cliente em PDF"
          className="flex items-center gap-1 text-xs text-muted hover:text-action transition-colors px-2 py-1 rounded hover:bg-canvas flex-shrink-0"
        >
          <span>↓</span>
          <span className="hidden sm:inline">PDF</span>
        </a>
        <button
          onClick={() => setShowArchiveConfirm(true)}
          title="Arquivar cliente"
          className="flex items-center gap-1 text-xs text-danger hover:text-danger transition-colors px-2 py-1 rounded hover:bg-canvas flex-shrink-0"
        >
          <span>🗑</span>
          <span className="hidden sm:inline">Arquivar</span>
        </button>
      </div>

      <div className="bg-surface border border-line rounded p-4 space-y-4">
        {editing ? (
          <EditForm
            cliente={cliente}
            onSave={(updated) => {
              setCliente(updated);
              setEditing(false);
            }}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4">
              <InfoRow label="E-mail" value={cliente.email ?? "—"} />
              <InfoRow label="Telefone" value={cliente.telefone ?? "—"} />
              <InfoRow
                label="Nascimento"
                value={
                  cliente.data_nascimento
                    ? new Date(cliente.data_nascimento + "T00:00:00").toLocaleDateString("pt-BR")
                    : "—"
                }
              />
              <InfoRow label="Estado civil" value={cliente.estado_civil ?? "—"} />
              <InfoRow label="Profissão" value={cliente.profissao?.replace("_", " ") ?? "—"} />
              <InfoRow label="Cadastrado em" value={fmtData(cliente.criado_em)} />
            </div>
            <div className="flex justify-end">
              <button
                className="text-xs text-action hover:underline"
                onClick={() => setEditing(true)}
              >
                Editar dados
              </button>
            </div>
          </>
        )}
      </div>

      {clienteId && <VeiculosSection clienteId={clienteId} />}
      {clienteId && <ImoveisSection clienteId={clienteId} />}
      {clienteId && <CotacoesSection clienteId={clienteId} />}

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-medium text-ink ">Linha do tempo</h2>
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigate(`/cotacao?cliente=${clienteId}`)}
          >
            Nova cotação
          </Button>
        </div>
        {timeline.length === 0 ? (
          <p className="text-sm text-muted ">Nenhuma atividade registrada.</p>
        ) : (
          <div>
            {timeline.map((item, i) => (
              <TimelineCard key={i} item={item} isLast={i === timeline.length - 1} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
