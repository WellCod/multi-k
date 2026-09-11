import { DataTable } from "@/components/DataTable";
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
    "border border-line rounded px-3 py-2 text-sm bg-surface text-ink focus:outline-none focus:ring-2 focus:ring-action";

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
        placeholder="Identificador da seguradora"
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
        <span className="text-sm text-muted ">%</span>
      </div>
      {err && <span className="text-xs text-danger">{err}</span>}
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
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink ">
            Comissões por CIA
          </h1>
          <p className="text-sm text-muted mt-1">
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
        <div className="rounded border border-line bg-canvas p-4 text-sm text-danger ">
          {err}
        </div>
      )}

      <div className="bg-surface border border-line rounded overflow-hidden">
        {adding && (
          <div className="px-4 border-b border-line bg-canvas ">
            <EditRow
              onSave={handleSave}
              onCancel={() => setAdding(false)}
            />
          </div>
        )}

        {loading ? (
          <div className="py-8 text-center text-sm text-muted ">
            Carregando…
          </div>
        ) : configs.length === 0 && !adding ? (
          <div className="py-8 text-center">
            <p className="text-sm text-muted ">
              Nenhuma configuração. Clique em "+ Nova configuração" para adicionar.
            </p>
          </div>
        ) : (
          <DataTable className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted uppercase tracking-wide">
                <th className="px-4 py-3 font-medium">CIA</th>
                <th className="px-4 py-3 font-medium">Ramo</th>
                <th className="px-4 py-3 font-medium">Comissão padrão</th>
                <th className="px-4 py-3 font-medium">Atualizado</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line ">
              {configs.map((c) => {
                const key = `${c.cia}|${c.ramo}`;
                if (editing === key) {
                  return (
                    <tr key={key} className="bg-canvas ">
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
                  <tr key={key} className="hover:bg-canvas transition-colors">
                    <td className="px-4 py-3 font-mono font-medium text-ink ">
                      {c.cia}
                    </td>
                    <td className="px-4 py-3 capitalize text-ink ">
                      {c.ramo}
                    </td>
                    <td className="px-4 py-3 font-semibold text-success tabular-nums">
                      {pctDisplay(c.pct_padrao)}
                    </td>
                    <td className="px-4 py-3 text-muted text-xs">
                      {new Date(c.atualizado_em).toLocaleDateString("pt-BR")}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={() => setEditing(key)}
                          className="text-xs px-3 py-1 rounded border border-line text-muted hover:bg-canvas transition-colors"
                        >
                          Editar
                        </button>
                        <button
                          onClick={() => handleDelete(c.cia, c.ramo)}
                          disabled={deleting === key}
                          className="text-xs px-3 py-1 rounded border border-line text-danger hover:bg-canvas transition-colors disabled:opacity-50"
                        >
                          {deleting === key ? "…" : "Excluir"}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </DataTable>
        )}
      </div>
    </div>
  );
}
