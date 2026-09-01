import { useEffect, useState } from "react";
import { api, type AuditoriaItem, type AuditoriaUsuario } from "@/lib/api";
import { Pagination } from "@/components/Pagination";

const PAGE_SIZE = 50;

function fmtData(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const TIPO_META: Record<string, { label: string; color: string; icon: string }> = {
  login:                  { label: "Login",                icon: "→", color: "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300" },
  logout:                 { label: "Logout",               icon: "←", color: "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300" },
  falha_login:            { label: "Falha de login",       icon: "✕", color: "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300" },
  "cliente.criado":       { label: "Cliente criado",       icon: "+", color: "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300" },
  "cliente.arquivado":    { label: "Cliente arquivado",    icon: "−", color: "bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300" },
  "cotacao.criada":       { label: "Cotação criada",       icon: "◎", color: "bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300" },
  "proposta.transmitida": { label: "Proposta emitida",     icon: "✓", color: "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300" },
  "veiculo.adicionado":   { label: "Veículo adicionado",  icon: "🚗", color: "bg-sky-100 dark:bg-sky-900/40 text-sky-700 dark:text-sky-300" },
  "imovel.adicionado":    { label: "Imóvel adicionado",   icon: "🏠", color: "bg-teal-100 dark:bg-teal-900/40 text-teal-700 dark:text-teal-300" },
};

const TODOS_TIPOS = Object.keys(TIPO_META);

function TipoBadge({ tipo }: { tipo: string }) {
  const meta = TIPO_META[tipo];
  const cls = meta?.color ?? "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${cls}`}>
      <span className="text-[10px] leading-none">{meta?.icon ?? "•"}</span>
      {meta?.label ?? tipo}
    </span>
  );
}

function DadosCell({ dados }: { dados: Record<string, unknown> }) {
  const [expanded, setExpanded] = useState(false);
  const entries = Object.entries(dados);
  if (entries.length === 0) return <span className="text-gray-300 dark:text-gray-600">—</span>;

  if (!expanded) {
    const preview = entries
      .slice(0, 2)
      .map(([k, v]) => `${k}: ${typeof v === "string" ? v.slice(0, 30) : String(v)}`)
      .join(" · ");
    return (
      <button
        onClick={() => setExpanded(true)}
        className="text-left text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 font-mono leading-relaxed group"
        title="Clique para expandir"
      >
        <span>{preview}{entries.length > 2 ? " …" : ""}</span>
        <span className="ml-1.5 opacity-0 group-hover:opacity-100 text-blue-500 transition-opacity">[+]</span>
      </button>
    );
  }

  return (
    <div className="space-y-0.5">
      {entries.map(([k, v]) => (
        <div key={k} className="flex gap-1.5 text-xs font-mono">
          <span className="text-gray-400 dark:text-gray-500 flex-shrink-0">{k}:</span>
          <span className="text-gray-700 dark:text-gray-300 break-all">{String(v)}</span>
        </div>
      ))}
      <button onClick={() => setExpanded(false)} className="text-xs text-blue-500 hover:underline mt-0.5">
        recolher
      </button>
    </div>
  );
}

function SkeletonRow() {
  return (
    <tr className="border-b border-gray-100 dark:border-gray-700 animate-pulse">
      <td className="px-4 py-3"><div className="h-3 w-28 rounded bg-gray-200 dark:bg-gray-700" /></td>
      <td className="px-4 py-3"><div className="h-5 w-24 rounded-full bg-gray-200 dark:bg-gray-700" /></td>
      <td className="px-4 py-3"><div className="h-3 w-24 rounded bg-gray-200 dark:bg-gray-700" /></td>
      <td className="px-4 py-3"><div className="h-3 w-20 rounded bg-gray-200 dark:bg-gray-700" /></td>
      <td className="px-4 py-3"><div className="h-3 w-40 rounded bg-gray-200 dark:bg-gray-700" /></td>
    </tr>
  );
}

const selectClass =
  "border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500";

export function AuditoriaPage() {
  const [items, setItems] = useState<AuditoriaItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [tipo, setTipo] = useState("");
  const [usuarioId, setUsuarioId] = useState("");
  const [usuarios, setUsuarios] = useState<AuditoriaUsuario[]>([]);
  const [page, setPage] = useState(1);

  useEffect(() => {
    api.auditoria.usuarios().then(setUsuarios).catch(() => undefined);
  }, []);

  useEffect(() => {
    setLoading(true);
    setErr(null);
    api.auditoria
      .list({
        page,
        page_size: PAGE_SIZE,
        tipo: tipo || undefined,
        usuario_id: usuarioId || undefined,
      })
      .then((res) => { setItems(res.items); setTotal(res.total); })
      .catch((e: unknown) =>
        setErr(e instanceof Error ? e.message : "Erro ao carregar auditoria"),
      )
      .finally(() => setLoading(false));
  }, [page, tipo, usuarioId]);

  function handleTipo(val: string) { setTipo(val); setPage(1); }
  function handleUsuario(val: string) { setUsuarioId(val); setPage(1); }

  const temFiltro = tipo || usuarioId;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Auditoria</h1>
          {!loading && !err && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
              {total.toLocaleString("pt-BR")} evento{total !== 1 ? "s" : ""}
              {tipo ? ` · ${TIPO_META[tipo]?.label ?? tipo}` : ""}
              {usuarioId && usuarios.length > 0
                ? ` · ${usuarios.find(u => u.id === usuarioId)?.nome ?? "usuário"}`
                : ""}
            </p>
          )}
        </div>
      </div>

      {/* Filtros */}
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
        <div className="flex flex-wrap gap-2 items-center">
          <select value={tipo} onChange={(e) => handleTipo(e.target.value)} className={selectClass}>
            <option value="">Todos os eventos</option>
            {TODOS_TIPOS.map((t) => (
              <option key={t} value={t}>{TIPO_META[t]?.label ?? t}</option>
            ))}
          </select>

          {usuarios.length > 0 && (
            <select value={usuarioId} onChange={(e) => handleUsuario(e.target.value)} className={selectClass}>
              <option value="">Todos os usuários</option>
              {usuarios.map((u) => (
                <option key={u.id} value={u.id}>{u.nome}</option>
              ))}
            </select>
          )}

          {temFiltro && (
            <button
              onClick={() => { handleTipo(""); handleUsuario(""); }}
              className="text-xs text-gray-400 hover:text-red-500 dark:hover:text-red-400 underline"
            >
              Limpar filtros
            </button>
          )}
        </div>
      </div>

      {/* Erro */}
      {err && (
        <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-400">
          {err}
        </div>
      )}

      {/* Tabela */}
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-700/60 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                <th className="px-4 py-3 w-36">Data / hora</th>
                <th className="px-4 py-3 w-44">Evento</th>
                <th className="px-4 py-3 w-36">Usuário</th>
                <th className="px-4 py-3 w-32">IP</th>
                <th className="px-4 py-3">Detalhes</th>
              </tr>
            </thead>
            <tbody>
              {loading && [...Array(8)].map((_, i) => <SkeletonRow key={i} />)}

              {!loading && !err && items.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-16 text-center">
                    <p className="text-3xl mb-2">🔒</p>
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Nenhum evento encontrado</p>
                    {temFiltro && (
                      <button
                        onClick={() => { handleTipo(""); handleUsuario(""); }}
                        className="mt-2 text-xs text-blue-500 underline"
                      >
                        Limpar filtros
                      </button>
                    )}
                  </td>
                </tr>
              )}

              {!loading && !err && items.map((item, idx) => (
                <tr
                  key={item.id}
                  className={`border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors ${
                    idx % 2 === 0 ? "" : "bg-gray-50/50 dark:bg-gray-700/10"
                  }`}
                >
                  <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap tabular-nums">
                    {fmtData(item.criado_em)}
                  </td>
                  <td className="px-4 py-3">
                    <TipoBadge tipo={item.tipo} />
                  </td>
                  <td className="px-4 py-3">
                    {item.usuario_nome ? (
                      <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
                        {item.usuario_nome}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-300 dark:text-gray-600">Sistema</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {item.ip_origem ? (
                      <span className="text-xs font-mono text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 rounded px-1.5 py-0.5">
                        {item.ip_origem}
                      </span>
                    ) : (
                      <span className="text-gray-300 dark:text-gray-600 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 max-w-sm">
                    <DadosCell dados={item.dados} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {!loading && total > PAGE_SIZE && (
          <div className="px-4 py-3 border-t border-gray-100 dark:border-gray-700">
            <Pagination page={page} total={total} perPage={PAGE_SIZE} onChange={setPage} />
          </div>
        )}
      </div>
    </div>
  );
}
