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
              <p>Prêmio: <span className="font-medium text-gray-800 dark:text-gray-200">{fmtReal(item.dados.premio_total as string | null)}</span></p>
              <p>Status: <span className="font-medium text-gray-800 dark:text-gray-200">{String(item.dados.status)}</span></p>
            </>
          )}
          {item.tipo === "proposta.transmitida" && (
            <>
              <p>Protocolo: <span className="font-mono font-medium text-gray-800 dark:text-gray-200">{String(item.dados.protocolo)}</span></p>
              <p>Parcelas: <span className="font-medium text-gray-800 dark:text-gray-200">{Number(item.dados.n_parcelas)}× de {fmtReal(item.dados.valor_parcela as string)}</span></p>
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
        setTimeline([...t].reverse());
      })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Erro"))
      .finally(() => setLoading(false));
  }, [clienteId]);

  if (loading) return <p className="text-sm text-gray-500 dark:text-gray-400">Carregando…</p>;
  if (err) return <p className="text-sm text-red-600 dark:text-red-400">{err}</p>;
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

      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 grid grid-cols-2 gap-4">
        <InfoRow label="E-mail" value={cliente.email ?? "—"} />
        <InfoRow label="Telefone" value={cliente.telefone ?? "—"} />
        <InfoRow label="Nascimento" value={cliente.data_nascimento ?? "—"} />
        <InfoRow label="Estado civil" value={cliente.estado_civil ?? "—"} />
        <InfoRow label="Profissão" value={cliente.profissao?.replace("_", " ") ?? "—"} />
        <InfoRow label="Cadastrado em" value={fmtData(cliente.criado_em)} />
      </div>

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
