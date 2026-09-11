import { DataTable } from "@/components/DataTable";
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
  login:                    { label: "Login",                  icon: "→", color: "bg-canvas text-success " },
  logout:                   { label: "Logout",                 icon: "←", color: "bg-canvas text-muted " },
  falha_login:              { label: "Falha de login",         icon: "✕", color: "bg-canvas text-danger " },
  "cliente.criado":         { label: "Cliente criado",         icon: "+", color: "bg-canvas text-action " },
  "cliente.arquivado":      { label: "Cliente arquivado",      icon: "−", color: "bg-canvas text-warning " },
  "cotacao.criada":         { label: "Cotação criada",         icon: "◎", color: "bg-canvas text-action " },
  "cotacao.recotada":       { label: "Recotação",              icon: "↺", color: "bg-canvas text-muted " },
  "proposta.transmitida":   { label: "Proposta emitida",       icon: "✓", color: "bg-canvas text-success " },
  "veiculo.adicionado":     { label: "Veículo adicionado",     icon: "🚗", color: "bg-canvas text-action " },
  "imovel.adicionado":      { label: "Imóvel adicionado",      icon: "🏠", color: "bg-canvas text-muted " },
  admin_criar_usuario:      { label: "Usuário criado",         icon: "👤", color: "bg-canvas text-muted " },
  admin_atualizar_usuario:  { label: "Usuário atualizado",     icon: "✎", color: "bg-canvas text-muted " },
  admin_reset_senha:        { label: "Reset de senha",         icon: "🔑", color: "bg-canvas text-warning " },
  "apolice.vinculada":      { label: "Apólice vinculada",       icon: "📄", color: "bg-canvas text-success " },
};

const TODOS_TIPOS = Object.keys(TIPO_META);

function TipoBadge({ tipo }: { tipo: string }) {
  const meta = TIPO_META[tipo];
  const cls = meta?.color ?? "bg-canvas text-muted ";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium whitespace-nowrap ${cls}`}>
      <span className="text-xs leading-none">{meta?.icon ?? "•"}</span>
      {meta?.label ?? tipo}
    </span>
  );
}

function DadosCell({ dados }: { dados: Record<string, unknown> }) {
  const [expanded, setExpanded] = useState(false);
  const entries = Object.entries(dados);
  if (entries.length === 0) return <span className="text-muted ">—</span>;

  if (!expanded) {
    const preview = entries
      .slice(0, 2)
      .map(([k, v]) => `${k}: ${typeof v === "string" ? v.slice(0, 30) : String(v)}`)
      .join(" · ");
    return (
      <button
        onClick={() => setExpanded(true)}
        className="text-left text-xs text-muted hover:text-ink font-mono leading-relaxed group"
        title="Clique para expandir"
      >
        <span>{preview}{entries.length > 2 ? " …" : ""}</span>
        <span className="ml-2 opacity-0 group-hover:opacity-100 text-action transition-opacity">[+]</span>
      </button>
    );
  }

  return (
    <div className="space-y-1">
      {entries.map(([k, v]) => (
        <div key={k} className="flex gap-2 text-xs font-mono">
          <span className="text-muted flex-shrink-0">{k}:</span>
          <span className="text-ink break-all">{String(v)}</span>
        </div>
      ))}
      <button onClick={() => setExpanded(false)} className="text-xs text-action hover:underline mt-1">
        recolher
      </button>
    </div>
  );
}

function SkeletonRow() {
  return (
    <tr className="border-b border-line animate-pulse">
      <td className="px-4 py-3"><div className="h-3 w-28 rounded bg-surface " /></td>
      <td className="px-4 py-3"><div className="h-5 w-24 rounded-full bg-surface " /></td>
      <td className="px-4 py-3"><div className="h-3 w-24 rounded bg-surface " /></td>
      <td className="px-4 py-3"><div className="h-3 w-20 rounded bg-surface " /></td>
      <td className="px-4 py-3"><div className="h-3 w-40 rounded bg-surface " /></td>
    </tr>
  );
}

const selectClass =
  "border border-line rounded px-3 py-2 text-sm bg-surface text-ink focus:outline-none focus:ring-2 focus:ring-action";

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
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink ">Auditoria</h1>
          {!loading && !err && (
            <p className="text-sm text-muted mt-1">
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
      <div className="bg-surface border border-line rounded p-4">
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
              className="text-xs text-muted hover:text-danger underline"
            >
              Limpar filtros
            </button>
          )}
        </div>
      </div>

      {/* Erro */}
      {err && (
        <div className="rounded border border-line bg-canvas p-4 text-sm text-danger ">
          {err}
        </div>
      )}

      {/* Tabela */}
      <div className="bg-surface border border-line rounded overflow-hidden">
        <div className="overflow-x-auto">
          <DataTable className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-canvas text-left text-xs font-semibold text-muted uppercase tracking-wide">
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
                    <p className="text-xl mb-2">🔒</p>
                    <p className="text-sm font-medium text-ink ">Nenhum evento encontrado</p>
                    {temFiltro && (
                      <button
                        onClick={() => { handleTipo(""); handleUsuario(""); }}
                        className="mt-2 text-xs text-action underline"
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
                  className={`border-b border-line hover:bg-canvas transition-colors ${
                    idx % 2 === 0 ? "" : "bg-canvas "
                  }`}
                >
                  <td className="px-4 py-3 text-xs text-muted whitespace-nowrap tabular-nums">
                    {fmtData(item.criado_em)}
                  </td>
                  <td className="px-4 py-3">
                    <TipoBadge tipo={item.tipo} />
                  </td>
                  <td className="px-4 py-3">
                    {item.usuario_nome ? (
                      <span className="text-xs font-medium text-ink ">
                        {item.usuario_nome}
                      </span>
                    ) : (
                      <span className="text-xs text-muted ">Sistema</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {item.ip_origem ? (
                      <span className="text-xs font-mono text-muted bg-canvas rounded px-2 py-1">
                        {item.ip_origem}
                      </span>
                    ) : (
                      <span className="text-muted text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 max-w-sm">
                    <DadosCell dados={item.dados} />
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>

        {!loading && total > PAGE_SIZE && (
          <div className="px-4 py-3 border-t border-line ">
            <Pagination page={page} total={total} perPage={PAGE_SIZE} onChange={setPage} />
          </div>
        )}
      </div>
    </div>
  );
}
