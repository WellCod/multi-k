import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Cliente, type TimelineItem } from "@/lib/api";
import { Button } from "@/components/ui/button";

function fmtData(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtReal(v: string | null | undefined) {
  if (!v) return "—";
  return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

const TIPO_CONFIG: Record<string, { label: string; color: string }> = {
  "cliente.criado": { label: "Cliente cadastrado", color: "bg-blue-500" },
  "cotacao.criada": { label: "Cotação criada", color: "bg-indigo-500" },
  "proposta.transmitida": { label: "Proposta transmitida", color: "bg-green-500" },
};

function TimelineCard({ item }: { item: TimelineItem }) {
  const cfg = TIPO_CONFIG[item.tipo] ?? { label: item.tipo, color: "bg-gray-400" };

  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div className={`w-3 h-3 rounded-full mt-1.5 flex-shrink-0 ${cfg.color}`} />
        <div className="w-px flex-1 bg-gray-200 mt-1" />
      </div>
      <div className="pb-5 flex-1">
        <p className="text-xs text-gray-500">{fmtData(item.data)}</p>
        <p className="text-sm font-medium mt-0.5">{cfg.label}</p>
        <div className="mt-1 text-xs text-gray-600 space-y-0.5">
          {item.tipo === "cotacao.criada" && (
            <>
              <p>Ramo: <span className="font-medium">{String(item.dados.ramo)}</span></p>
              <p>Prêmio: <span className="font-medium">{fmtReal(item.dados.premio_total as string | null)}</span></p>
              <p>Status: <span className="font-medium">{String(item.dados.status)}</span></p>
            </>
          )}
          {item.tipo === "proposta.transmitida" && (
            <>
              <p>Protocolo: <span className="font-mono font-medium">{String(item.dados.protocolo)}</span></p>
              <p>Parcelas: <span className="font-medium">{Number(item.dados.n_parcelas)}× de {fmtReal(item.dados.valor_parcela as string)}</span></p>
            </>
          )}
        </div>
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

  useEffect(() => {
    if (!clienteId) return;
    Promise.all([api.clientes.get(clienteId), api.clientes.timeline(clienteId)])
      .then(([c, t]) => {
        setCliente(c);
        setTimeline([...t].reverse()); // mais recente primeiro
      })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Erro"))
      .finally(() => setLoading(false));
  }, [clienteId]);

  if (loading) return <p className="text-sm text-gray-500">Carregando…</p>;
  if (err) return <p className="text-sm text-red-600">{err}</p>;
  if (!cliente) return null;

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={() => navigate(-1)} className="text-sm text-blue-600 hover:underline">
          ← Voltar
        </button>
        <h1 className="text-xl font-semibold">{cliente.nome}</h1>
      </div>

      <div className="bg-white border rounded-lg p-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-gray-500 text-xs">E-mail</p>
          <p>{cliente.email ?? "—"}</p>
        </div>
        <div>
          <p className="text-gray-500 text-xs">Telefone</p>
          <p>{cliente.telefone ?? "—"}</p>
        </div>
        <div>
          <p className="text-gray-500 text-xs">Nascimento</p>
          <p>{cliente.data_nascimento ?? "—"}</p>
        </div>
        <div>
          <p className="text-gray-500 text-xs">Estado civil</p>
          <p>{cliente.estado_civil ?? "—"}</p>
        </div>
        <div>
          <p className="text-gray-500 text-xs">Profissão</p>
          <p>{cliente.profissao ?? "—"}</p>
        </div>
        <div>
          <p className="text-gray-500 text-xs">Cadastrado em</p>
          <p>{fmtData(cliente.criado_em)}</p>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-medium">Linha do tempo</h2>
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigate(`/cotacao?cliente=${clienteId}`)}
          >
            Nova cotação
          </Button>
        </div>
        {timeline.length === 0 ? (
          <p className="text-sm text-gray-500">Nenhuma atividade registrada.</p>
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
