import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Cliente, type ClienteInput } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/Pagination";

const PAGE_SIZE = 50;

function fmtData(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR");
}

function Avatar({ nome }: { nome: string }) {
  const initials = nome
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
  return (
    <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-900/50 text-xs font-semibold text-indigo-700 dark:text-indigo-300 select-none">
      {initials || "?"}
    </div>
  );
}

function SkeletonRow() {
  return (
    <tr className="border-b border-gray-100 dark:border-gray-700 animate-pulse">
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-full bg-gray-200 dark:bg-gray-700 flex-shrink-0" />
          <div className="h-3 w-36 rounded bg-gray-200 dark:bg-gray-700" />
        </div>
      </td>
      <td className="px-4 py-3"><div className="h-3 w-40 rounded bg-gray-200 dark:bg-gray-700" /></td>
      <td className="px-4 py-3"><div className="h-3 w-28 rounded bg-gray-200 dark:bg-gray-700" /></td>
      <td className="px-4 py-3"><div className="h-3 w-24 rounded bg-gray-200 dark:bg-gray-700" /></td>
      <td className="px-4 py-3"><div className="h-3 w-20 rounded bg-gray-200 dark:bg-gray-700" /></td>
      <td className="px-4 py-3"><div className="h-6 w-24 rounded-lg bg-gray-200 dark:bg-gray-700" /></td>
    </tr>
  );
}

function NovoClienteModal({
  onSave,
  onClose,
}: {
  onSave: (c: Cliente) => void;
  onClose: () => void;
}) {
  const [nome, setNome] = useState("");
  const [cpf, setCpf] = useState("");
  const [email, setEmail] = useState("");
  const [telefone, setTelefone] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const cpfDigits = cpf.replace(/\D/g, "");
  const cpfValid = cpfDigits.length === 11;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!cpfValid) return;
    setSaving(true);
    setErr(null);
    const body: ClienteInput = { nome: nome.trim(), cpf: cpfDigits };
    if (email.trim()) body.email = email.trim();
    if (telefone.trim()) body.telefone = telefone.trim();
    try {
      const created = await api.clientes.create(body);
      onSave(created);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Erro ao criar cliente");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-2xl w-full max-w-md mx-4 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">Novo cliente</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
            aria-label="Fechar"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>

        {err && (
          <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-3 text-sm text-red-700 dark:text-red-400">
            {err}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Nome *</label>
            <Input
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              placeholder="Nome completo"
              required
              autoFocus
              className="mt-0.5"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">CPF *</label>
            <Input
              value={cpf}
              onChange={(e) => setCpf(e.target.value)}
              placeholder="000.000.000-00"
              maxLength={14}
              className="mt-0.5"
            />
            {cpf && !cpfValid && (
              <p className="text-xs text-red-600 dark:text-red-400 mt-1">CPF deve ter 11 dígitos</p>
            )}
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">E-mail</label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="cliente@exemplo.com"
              className="mt-0.5"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Telefone</label>
            <Input
              value={telefone}
              onChange={(e) => setTelefone(e.target.value)}
              placeholder="(11) 90000-0000"
              className="mt-0.5"
            />
          </div>

          <div className="flex gap-2 justify-end pt-1">
            <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={saving}>
              Cancelar
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={saving || !nome.trim() || !cpfValid}
            >
              {saving ? "Criando…" : "Criar cliente"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function ClientesPage() {
  const navigate = useNavigate();
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [buscaInput, setBuscaInput] = useState("");
  const [page, setPage] = useState(1);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    setLoading(true);
    setErr(null);
    api.clientes
      .list({ page, page_size: PAGE_SIZE, q: busca || undefined })
      .then((res) => { setClientes(res.items); setTotal(res.total); })
      .catch((e: unknown) =>
        setErr(e instanceof Error ? e.message : "Erro ao carregar clientes"),
      )
      .finally(() => setLoading(false));
  }, [page, busca]);

  function handleBusca() {
    setPage(1);
    setBusca(buscaInput.trim());
  }

  const paginated = clientes;

  return (
    <div className="space-y-4">
      {showModal && (
        <NovoClienteModal
          onSave={(created) => {
            setClientes((prev) => [created, ...prev]);
            setTotal((t) => t + 1);
            setShowModal(false);
          }}
          onClose={() => setShowModal(false)}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Clientes</h1>
          {!loading && !err && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
              {total} cliente{total !== 1 ? "s" : ""} na carteira
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setShowModal(true)}>
            + Novo cliente
          </Button>
          <Button size="sm" onClick={() => navigate("/cotacao")}>
            + Nova cotação
          </Button>
        </div>
      </div>

      {/* Busca */}
      <div className="flex gap-2 max-w-sm">
        <Input
          placeholder="Buscar por nome ou e-mail…"
          value={buscaInput}
          onChange={(e) => setBuscaInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleBusca(); }}
        />
        <Button size="sm" variant="outline" onClick={handleBusca}>Buscar</Button>
      </div>

      {/* Erro */}
      {err && (
        <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-400">
          {err}
        </div>
      )}

      {/* Empty state: sem clientes cadastrados */}
      {!loading && !err && clientes.length === 0 && !busca && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 py-16 text-center">
          <p className="text-4xl mb-3">👥</p>
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Nenhum cliente cadastrado</p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Adicione o primeiro cliente para começar
          </p>
          <button
            onClick={() => setShowModal(true)}
            className="mt-4 text-xs px-3 py-1.5 rounded-lg border border-indigo-200 dark:border-indigo-700 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 transition-colors"
          >
            + Novo cliente
          </button>
        </div>
      )}

      {/* Empty state: busca sem resultado */}
      {!loading && !err && clientes.length === 0 && busca && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 py-12 text-center">
          <p className="text-3xl mb-2">🔍</p>
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Nenhum cliente encontrado para "{busca}"
          </p>
          <button
            onClick={() => { setBuscaInput(""); setBusca(""); }}
            className="mt-3 text-xs text-blue-600 dark:text-blue-400 underline"
          >
            Limpar busca
          </button>
        </div>
      )}

      {/* Tabela com card wrapper */}
      {(loading || (!err && clientes.length > 0)) && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-50 dark:bg-gray-700/60 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                  <th className="px-4 py-3">Nome</th>
                  <th className="px-4 py-3">E-mail</th>
                  <th className="px-4 py-3">Telefone</th>
                  <th className="px-4 py-3">Profissão</th>
                  <th className="px-4 py-3">Cadastro</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {loading && [...Array(5)].map((_, i) => <SkeletonRow key={i} />)}

                {!loading && paginated.map((c) => (
                  <tr
                    key={c.id}
                    className="border-b border-gray-100 dark:border-gray-700 hover:bg-blue-50/40 dark:hover:bg-gray-700/40 cursor-pointer transition-colors group"
                    onClick={() => navigate(`/clientes/${c.id}`)}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <Avatar nome={c.nome} />
                        <span className="font-medium text-gray-900 dark:text-white group-hover:text-indigo-700 dark:group-hover:text-indigo-300 transition-colors">
                          {c.nome}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                      {c.email ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                      {c.telefone ?? "—"}
                    </td>
                    <td className="px-4 py-3 capitalize text-gray-600 dark:text-gray-400">
                      {c.profissao?.replace("_", " ") ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                      {fmtData(c.criado_em)}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        className="text-xs px-2.5 py-1 rounded-lg border border-indigo-200 dark:border-indigo-700 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 transition-colors whitespace-nowrap"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/cotacao?cliente=${c.id}`);
                        }}
                      >
                        Nova cotação
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!loading && total > PAGE_SIZE && (
            <div className="px-4 py-3 border-t border-gray-100 dark:border-gray-700">
              <Pagination
                page={page}
                total={total}
                perPage={PAGE_SIZE}
                onChange={setPage}
              />
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
                {total} cliente{total !== 1 ? "s" : ""}
                {busca ? ` encontrado${total !== 1 ? "s" : ""}` : " na carteira"}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
