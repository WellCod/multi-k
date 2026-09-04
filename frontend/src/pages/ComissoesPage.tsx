import { useEffect, useState } from "react";
import { api, type ComissaoConfigOut } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const RAMOS = ["auto", "imovel", "vida", "empresarial"];

function pctDisplay(pct: string): string {
  return `${(parseFloat(pct) * 100).toFixed(2)}%`;
}

function pctToDecimal(pct: number): string {
  return (pct / 100).toFixed(4);
}

interface EditRowProps {
  initial?: ComissaoConfigOut;
  onSave: (cia: string, ramo: string, pct: string) => Promise<void>;
  onCancel: () => void;
  fixCia?: string;
  fixRamo?: string;
}

function EditRow({ initial, onSave, onCancel, fixCia, fixRamo }: EditRowProps) {
  const [cia, setCia] = useState(fixCia ?? initial?.cia ?? "");
  const [ramo, setRamo] = useState(fixRamo ?? initial?.ramo ?? "auto");
  const [pct, setPct] = useState(initial ? parseFloat(initial.pct_padrao) * 100 : 15);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const inputClass =
    "border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cia.trim()) { setErr("CIA é obrigatória"); return; }
    if (pct <= 0 || pct > 30) { setErr("Comissão deve ser entre 0.01% e 30%"); return; }
    setSaving(true);
    setErr(null);
    try {
      await onSave(cia.trim().toLowerCase(), ramo, pctToDecimal(pct));
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-2 py-2">
      <Input
        value={cia}
        onChange={(e) => setCia(e.target.value)}
        placeholder="CIA (ex: fake)"
        className="w-28"
        disabled={!!fixCia}
        required
      />
      <select
        value={ramo}
        onChange={(e) => setRamo(e.target.value)}
        className={`${inputClass} w-32`}
        disabled={!!fixRamo}
      >
        {RAMOS.map((r) => <option key={r} value={r}>{r}</option>)}
      </select>
      <div className="flex items-center gap-1">
        <Input
          type="number"
          value={pct}
          onChange={(e) => setPct(parseFloat(e.target.value) || 0)}
          min={0.01}
          max={30}
          step={0.01}
          className="w-24"
        />
        <span className="text-sm text-gray-500 dark:text-gray-400">%</span>
      </div>
      {err && <span className="text-xs text-red-500">{err}</span>}
      <Button type="submit" size="sm" disabled={saving}>
        {saving ? "Salvando…" : "Salvar"}
      </Button>
      <Button type="button" size="sm" variant="outline" onClick={onCancel}>
        Cancelar
      </Button>
    </form>
  );
}

export function ComissoesPage() {
  const [configs, setConfigs] = useState<ComissaoConfigOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<string | null>(null); // "cia|ramo"
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    api.comissoes.list()
      .then(setConfigs)
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleSave = async (cia: string, ramo: string, pct: string) => {
    await api.comissoes.set(cia, ramo, pct);
    setAdding(false);
    setEditing(null);
    load();
  };

  const handleDelete = async (cia: string, ramo: string) => {
    const key = `${cia}|${ramo}`;
    setDeleting(key);
    try {
      await api.comissoes.delete(cia, ramo);
      load();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Erro ao excluir");
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
            Comissões por CIA
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Comissão padrão preenchida automaticamente ao transmitir proposta
          </p>
        </div>
        {!adding && (
          <Button size="sm" onClick={() => setAdding(true)}>
            + Nova configuração
          </Button>
        )}
      </div>

      {err && (
        <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-400">
          {err}
        </div>
      )}

      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
        {adding && (
          <div className="px-4 border-b border-gray-100 dark:border-gray-700 bg-blue-50 dark:bg-blue-900/20">
            <EditRow
              onSave={handleSave}
              onCancel={() => setAdding(false)}
            />
          </div>
        )}

        {loading ? (
          <div className="py-12 text-center text-sm text-gray-400 dark:text-gray-500">
            Carregando…
          </div>
        ) : configs.length === 0 && !adding ? (
          <div className="py-12 text-center">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Nenhuma configuração. Clique em "+ Nova configuração" para adicionar.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-700 text-left text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                <th className="px-4 py-3 font-medium">CIA</th>
                <th className="px-4 py-3 font-medium">Ramo</th>
                <th className="px-4 py-3 font-medium">Comissão padrão</th>
                <th className="px-4 py-3 font-medium">Atualizado</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {configs.map((c) => {
                const key = `${c.cia}|${c.ramo}`;
                if (editing === key) {
                  return (
                    <tr key={key} className="bg-blue-50 dark:bg-blue-900/20">
                      <td colSpan={5} className="px-4">
                        <EditRow
                          initial={c}
                          fixCia={c.cia}
                          fixRamo={c.ramo}
                          onSave={handleSave}
                          onCancel={() => setEditing(null)}
                        />
                      </td>
                    </tr>
                  );
                }
                return (
                  <tr key={key} className="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                    <td className="px-4 py-3 font-mono font-medium text-gray-900 dark:text-white">
                      {c.cia}
                    </td>
                    <td className="px-4 py-3 capitalize text-gray-700 dark:text-gray-300">
                      {c.ramo}
                    </td>
                    <td className="px-4 py-3 font-semibold text-green-700 dark:text-green-400 tabular-nums">
                      {pctDisplay(c.pct_padrao)}
                    </td>
                    <td className="px-4 py-3 text-gray-400 dark:text-gray-500 text-xs">
                      {new Date(c.atualizado_em).toLocaleDateString("pt-BR")}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1.5 justify-end">
                        <button
                          onClick={() => setEditing(key)}
                          className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                        >
                          Editar
                        </button>
                        <button
                          onClick={() => handleDelete(c.cia, c.ramo)}
                          disabled={deleting === key}
                          className="text-xs px-2.5 py-1 rounded-lg border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors disabled:opacity-50"
                        >
                          {deleting === key ? "…" : "Excluir"}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
