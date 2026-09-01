import { useEffect, useState } from "react";
import { api, type UsuarioAdmin } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function fmtData(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR");
}

function PapelBadge({ papel }: { papel: string }) {
  const cls =
    papel === "admin"
      ? "bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300"
      : "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}
    >
      {papel === "admin" ? "Admin" : "Corretor"}
    </span>
  );
}

function StatusBadge({ ativo }: { ativo: boolean }) {
  const cls = ativo
    ? "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300"
    : "bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}
    >
      {ativo ? "Ativo" : "Inativo"}
    </span>
  );
}

function CloseIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-5 w-5"
      viewBox="0 0 20 20"
      fill="currentColor"
    >
      <path
        fillRule="evenodd"
        d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function ModalWrapper({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-2xl w-full max-w-md mx-4 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">{title}</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
            aria-label="Fechar"
          >
            <CloseIcon />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function ErrorBox({ msg }: { msg: string }) {
  return (
    <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-3 text-sm text-red-700 dark:text-red-400">
      {msg}
    </div>
  );
}

const selectClass =
  "w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 mt-0.5";

function NovoUsuarioModal({
  onSave,
  onClose,
}: {
  onSave: (u: UsuarioAdmin) => void;
  onClose: () => void;
}) {
  const [email, setEmail] = useState("");
  const [nome, setNome] = useState("");
  const [papel, setPapel] = useState<"corretor" | "admin">("corretor");
  const [senha, setSenha] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (senha !== confirmar) {
      setErr("As senhas não conferem.");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      const created = await api.usuarios.criar({ email: email.trim(), nome: nome.trim(), papel, senha });
      onSave(created);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Erro ao criar usuário");
    } finally {
      setSaving(false);
    }
  }

  return (
    <ModalWrapper title="Novo usuário" onClose={onClose}>
      {err && <ErrorBox msg={err} />}
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400">E-mail *</label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="usuario@exemplo.com"
            required
            autoFocus
            className="mt-0.5"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Nome *</label>
          <Input
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            placeholder="Nome completo"
            required
            minLength={2}
            className="mt-0.5"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Papel *</label>
          <select
            value={papel}
            onChange={(e) => setPapel(e.target.value as "corretor" | "admin")}
            className={selectClass}
          >
            <option value="corretor">Corretor</option>
            <option value="admin">Admin</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Senha *</label>
          <Input
            type="password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            placeholder="Mínimo 8 caracteres"
            required
            minLength={8}
            className="mt-0.5"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400">
            Confirmar senha *
          </label>
          <Input
            type="password"
            value={confirmar}
            onChange={(e) => setConfirmar(e.target.value)}
            placeholder="Repita a senha"
            required
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
            disabled={saving || !email.trim() || !nome.trim() || !senha || !confirmar}
          >
            {saving ? "Criando…" : "Criar usuário"}
          </Button>
        </div>
      </form>
    </ModalWrapper>
  );
}

function EditarUsuarioModal({
  usuario,
  onSave,
  onClose,
}: {
  usuario: UsuarioAdmin;
  onSave: (u: UsuarioAdmin) => void;
  onClose: () => void;
}) {
  const [nome, setNome] = useState(usuario.nome);
  const [papel, setPapel] = useState<"corretor" | "admin">(
    usuario.papel as "corretor" | "admin",
  );
  const [ativo, setAtivo] = useState(usuario.ativo);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr(null);
    try {
      const updated = await api.usuarios.atualizar(usuario.id, {
        nome: nome.trim(),
        papel,
        ativo,
      });
      onSave(updated);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Erro ao atualizar usuário");
    } finally {
      setSaving(false);
    }
  }

  return (
    <ModalWrapper title="Editar usuário" onClose={onClose}>
      {err && <ErrorBox msg={err} />}
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Nome *</label>
          <Input
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            placeholder="Nome completo"
            required
            minLength={2}
            autoFocus
            className="mt-0.5"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Papel *</label>
          <select
            value={papel}
            onChange={(e) => setPapel(e.target.value as "corretor" | "admin")}
            className={selectClass}
          >
            <option value="corretor">Corretor</option>
            <option value="admin">Admin</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <input
            id="ativo-toggle"
            type="checkbox"
            checked={ativo}
            onChange={(e) => setAtivo(e.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <label
            htmlFor="ativo-toggle"
            className="text-sm text-gray-700 dark:text-gray-300 select-none"
          >
            Conta ativa
          </label>
        </div>
        <div className="flex gap-2 justify-end pt-1">
          <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={saving}>
            Cancelar
          </Button>
          <Button type="submit" size="sm" disabled={saving || !nome.trim()}>
            {saving ? "Salvando…" : "Salvar"}
          </Button>
        </div>
      </form>
    </ModalWrapper>
  );
}

function ResetSenhaModal({
  usuario,
  onClose,
}: {
  usuario: UsuarioAdmin;
  onClose: () => void;
}) {
  const [nova, setNova] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (nova !== confirmar) {
      setErr("As senhas não conferem.");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      await api.usuarios.resetSenha(usuario.id, nova);
      setDone(true);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Erro ao redefinir senha");
    } finally {
      setSaving(false);
    }
  }

  return (
    <ModalWrapper title={`Redefinir senha — ${usuario.nome}`} onClose={onClose}>
      {err && <ErrorBox msg={err} />}
      {done ? (
        <div className="space-y-3">
          <p className="text-sm text-green-700 dark:text-green-400">
            Senha redefinida com sucesso.
          </p>
          <div className="flex justify-end">
            <Button size="sm" onClick={onClose}>
              Fechar
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">
              Nova senha *
            </label>
            <Input
              type="password"
              value={nova}
              onChange={(e) => setNova(e.target.value)}
              placeholder="Mínimo 8 caracteres"
              required
              minLength={8}
              autoFocus
              className="mt-0.5"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">
              Confirmar nova senha *
            </label>
            <Input
              type="password"
              value={confirmar}
              onChange={(e) => setConfirmar(e.target.value)}
              placeholder="Repita a nova senha"
              required
              className="mt-0.5"
            />
          </div>
          <div className="flex gap-2 justify-end pt-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onClose}
              disabled={saving}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={saving || !nova || !confirmar}
            >
              {saving ? "Salvando…" : "Redefinir senha"}
            </Button>
          </div>
        </form>
      )}
    </ModalWrapper>
  );
}

function SkeletonRow() {
  return (
    <tr className="border-b border-gray-100 dark:border-gray-700 animate-pulse">
      <td className="px-4 py-3">
        <div className="h-3 w-36 rounded bg-gray-200 dark:bg-gray-700" />
      </td>
      <td className="px-4 py-3">
        <div className="h-3 w-44 rounded bg-gray-200 dark:bg-gray-700" />
      </td>
      <td className="px-4 py-3">
        <div className="h-5 w-20 rounded-full bg-gray-200 dark:bg-gray-700" />
      </td>
      <td className="px-4 py-3">
        <div className="h-5 w-16 rounded-full bg-gray-200 dark:bg-gray-700" />
      </td>
      <td className="px-4 py-3">
        <div className="h-3 w-20 rounded bg-gray-200 dark:bg-gray-700" />
      </td>
      <td className="px-4 py-3">
        <div className="h-6 w-40 rounded bg-gray-200 dark:bg-gray-700" />
      </td>
    </tr>
  );
}

type ModalState =
  | { type: "none" }
  | { type: "criar" }
  | { type: "editar"; usuario: UsuarioAdmin }
  | { type: "resetSenha"; usuario: UsuarioAdmin };

export function UsuariosPage() {
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [modal, setModal] = useState<ModalState>({ type: "none" });
  const [toggling, setToggling] = useState<string | null>(null);

  function load() {
    setLoading(true);
    setErr(null);
    api.usuarios
      .list()
      .then(setUsuarios)
      .catch((e: unknown) =>
        setErr(e instanceof Error ? e.message : "Erro ao carregar usuários"),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  function handleCriado(u: UsuarioAdmin) {
    setUsuarios((prev) => [u, ...prev]);
    setModal({ type: "none" });
  }

  function handleAtualizado(u: UsuarioAdmin) {
    setUsuarios((prev) => prev.map((x) => (x.id === u.id ? u : x)));
    setModal({ type: "none" });
  }

  async function handleToggleAtivo(u: UsuarioAdmin) {
    setToggling(u.id);
    try {
      const updated = await api.usuarios.atualizar(u.id, { ativo: !u.ativo });
      setUsuarios((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Erro ao alterar status");
    } finally {
      setToggling(null);
    }
  }

  return (
    <div className="space-y-5">
      {modal.type === "criar" && (
        <NovoUsuarioModal onSave={handleCriado} onClose={() => setModal({ type: "none" })} />
      )}
      {modal.type === "editar" && (
        <EditarUsuarioModal
          usuario={modal.usuario}
          onSave={handleAtualizado}
          onClose={() => setModal({ type: "none" })}
        />
      )}
      {modal.type === "resetSenha" && (
        <ResetSenhaModal
          usuario={modal.usuario}
          onClose={() => setModal({ type: "none" })}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Usuários</h1>
          {!loading && !err && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
              {usuarios.length} usuário{usuarios.length !== 1 ? "s" : ""}
            </p>
          )}
        </div>
        <Button size="sm" onClick={() => setModal({ type: "criar" })}>
          + Novo usuário
        </Button>
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
                <th className="px-4 py-3">Nome</th>
                <th className="px-4 py-3">E-mail</th>
                <th className="px-4 py-3">Papel</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Cadastro</th>
                <th className="px-4 py-3">Ações</th>
              </tr>
            </thead>
            <tbody>
              {loading && [...Array(4)].map((_, i) => <SkeletonRow key={i} />)}

              {!loading && !err && usuarios.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-16 text-center">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Nenhum usuário encontrado
                    </p>
                  </td>
                </tr>
              )}

              {!loading &&
                !err &&
                usuarios.map((u, idx) => (
                  <tr
                    key={u.id}
                    className={`border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors ${
                      idx % 2 === 0 ? "" : "bg-gray-50/50 dark:bg-gray-700/10"
                    }`}
                  >
                    <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                      {u.nome}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{u.email}</td>
                    <td className="px-4 py-3">
                      <PapelBadge papel={u.papel} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge ativo={u.ativo} />
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400 tabular-nums text-xs">
                      {fmtData(u.criado_em)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <button
                          onClick={() => setModal({ type: "editar", usuario: u })}
                          className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                        >
                          Editar
                        </button>
                        <button
                          onClick={() => setModal({ type: "resetSenha", usuario: u })}
                          className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                        >
                          Redefinir senha
                        </button>
                        <button
                          onClick={() => handleToggleAtivo(u)}
                          disabled={toggling === u.id}
                          className={`text-xs px-2.5 py-1 rounded-lg border transition-colors disabled:opacity-50 ${
                            u.ativo
                              ? "border-red-200 dark:border-red-700 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30"
                              : "border-green-200 dark:border-green-700 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30"
                          }`}
                        >
                          {toggling === u.id ? "…" : u.ativo ? "Desativar" : "Ativar"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
