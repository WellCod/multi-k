import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Cliente, type ClientePatch, type Dominio, type Imovel, type TimelineItem, type Veiculo } from "@/lib/api";
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
  "cliente.criado": { label: "Cliente cadastrado", dot: "bg-blue-500" },
  "cotacao.criada": { label: "Cotação criada", dot: "bg-indigo-500" },
  "proposta.transmitida": { label: "Proposta transmitida", dot: "bg-green-500" },
};

function TimelineCard({ item }: { item: TimelineItem }) {
  const cfg = TIPO_CONFIG[item.tipo] ?? { label: item.tipo, dot: "bg-gray-400" };

  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div className={`w-3 h-3 rounded-full mt-1.5 flex-shrink-0 ${cfg.dot}`} />
        <div className="w-px flex-1 bg-gray-200 dark:bg-gray-700 mt-1" />
      </div>
      <div className="pb-5 flex-1">
        <p className="text-xs text-gray-500 dark:text-gray-400">{fmtData(item.data)}</p>
        <p className="text-sm font-medium text-gray-900 dark:text-white mt-0.5">{cfg.label}</p>
        <div className="mt-1 text-xs text-gray-600 dark:text-gray-400 space-y-0.5">
          {item.tipo === "cotacao.criada" && (
            <>
              <p>Ramo: <span className="font-medium text-gray-800 dark:text-gray-200">{String(item.dados.ramo)}</span></p>
              <p>Prêmio: <span className="font-medium text-gray-800 dark:text-gray-200">{formatBRL(item.dados.premio_total as string | null)}</span></p>
              <p>Status: <span className="font-medium text-gray-800 dark:text-gray-200">{String(item.dados.status)}</span></p>
            </>
          )}
          {item.tipo === "proposta.transmitida" && (
            <>
              <p>Protocolo: <span className="font-mono font-medium text-gray-800 dark:text-gray-200">{String(item.dados.protocolo)}</span></p>
              <p>Parcelas: <span className="font-medium text-gray-800 dark:text-gray-200">{Number(item.dados.n_parcelas)}× de {formatBRL(item.dados.valor_parcela as string)}</span></p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
      <p className="text-sm text-gray-900 dark:text-white mt-0.5">{value}</p>
    </div>
  );
}

const SELECT_CLASS =
  "mt-0.5 w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-1.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white";

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
        <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-3 text-sm text-red-700 dark:text-red-400">
          {err}
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500 dark:text-gray-400">Nome *</label>
          <Input value={nome} onChange={(e) => setNome(e.target.value)} required className="mt-0.5" />
        </div>
        <div>
          <label className="text-xs text-gray-500 dark:text-gray-400">E-mail</label>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-0.5" />
        </div>
        <div>
          <label className="text-xs text-gray-500 dark:text-gray-400">Telefone</label>
          <Input value={telefone} onChange={(e) => setTelefone(e.target.value)} className="mt-0.5" />
        </div>
        <div>
          <label className="text-xs text-gray-500 dark:text-gray-400">Data de nascimento</label>
          <Input type="date" value={dataNasc} onChange={(e) => setDataNasc(e.target.value)} className="mt-0.5" />
        </div>
        <div>
          <label className="text-xs text-gray-500 dark:text-gray-400">Estado civil</label>
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
          <label className="text-xs text-gray-500 dark:text-gray-400">Profissão</label>
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
          {saving ? "Salvando…" : "Salvar"}
        </Button>
      </div>
    </form>
  );
}

function VeiculosSection({ clienteId }: { clienteId: string }) {
  const [veiculos, setVeiculos] = useState<Veiculo[] | null>(null);

  useEffect(() => {
    api.clientes.veiculos(clienteId).then(setVeiculos).catch(() => setVeiculos([]));
  }, [clienteId]);

  if (veiculos === null) return null;
  if (veiculos.length === 0) return null;

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
        Veículos ({veiculos.length})
      </h2>
      <div className="space-y-2">
        {veiculos.map((v) => (
          <div
            key={v.id}
            className="flex items-center justify-between text-sm border border-gray-100 dark:border-gray-700 rounded px-3 py-2"
          >
            <span className="font-medium text-gray-900 dark:text-white">
              {v.marca} {v.modelo}
            </span>
            <div className="text-xs text-gray-500 dark:text-gray-400 flex gap-3">
              <span>{v.ano_fabricacao}/{v.ano_modelo}</span>
              <span className="capitalize">{v.combustivel}</span>
              {v.placa && <span className="font-mono uppercase">{v.placa}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ImoveisSection({ clienteId }: { clienteId: string }) {
  const [imoveis, setImoveis] = useState<Imovel[] | null>(null);

  useEffect(() => {
    api.clientes.imoveis(clienteId).then(setImoveis).catch(() => setImoveis([]));
  }, [clienteId]);

  if (imoveis === null) return null;
  if (imoveis.length === 0) return null;

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
        Imóveis ({imoveis.length})
      </h2>
      <div className="space-y-2">
        {imoveis.map((im) => (
          <div
            key={im.id}
            className="flex items-center justify-between text-sm border border-gray-100 dark:border-gray-700 rounded px-3 py-2"
          >
            <span className="font-medium text-gray-900 dark:text-white capitalize">
              {im.tipo_imovel.replace("_", " ")}
            </span>
            <div className="text-xs text-gray-500 dark:text-gray-400 flex gap-3">
              <span>CEP {im.cep}</span>
              <span className="capitalize">{im.tipo_construcao.replace("_", " ")}</span>
              {im.logradouro && (
                <span className="truncate max-w-[140px]">
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

export function ClienteDetailPage() {
  const { clienteId } = useParams<{ clienteId: string }>();
  const navigate = useNavigate();
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (!clienteId) return;
    Promise.all([api.clientes.get(clienteId), api.clientes.timeline(clienteId)])
      .then(([c, t]) => {
        setCliente(c);
        setTimeline([...t].reverse());
      })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Erro"))
      .finally(() => setLoading(false));
  }, [clienteId]);

  if (loading) return <p className="text-sm text-gray-500 dark:text-gray-400">Carregando…</p>;
  if (err)
    return (
      <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-400">
        {err}
      </div>
    );
  if (!cliente) return null;

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate(-1)}
          className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
        >
          ← Voltar
        </button>
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">{cliente.nome}</h1>
      </div>

      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-4">
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
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
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

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-medium text-gray-900 dark:text-white">Linha do tempo</h2>
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigate(`/cotacao?cliente=${clienteId}`)}
          >
            Nova cotação
          </Button>
        </div>
        {timeline.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">Nenhuma atividade registrada.</p>
        ) : (
          <div>
            {timeline.map((item, i) => (
              <TimelineCard key={i} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
