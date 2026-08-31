import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Cliente } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/Pagination";

const PAGE_SIZE = 15;

function fmtData(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR");
}

export function ClientesPage() {
  const navigate = useNavigate();
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    api.clientes
      .list()
      .then(setClientes)
      .catch((e: unknown) =>
        setErr(e instanceof Error ? e.message : "Erro ao carregar clientes"),
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    setPage(1);
  }, [busca]);

  const filtrados = useMemo(() => {
    const q = busca.trim().toLowerCase();
    if (!q) return clientes;
    return clientes.filter(
      (c) =>
        c.nome.toLowerCase().includes(q) ||
        c.email?.toLowerCase().includes(q) ||
        c.telefone?.includes(q),
    );
  }, [clientes, busca]);

  const paginated = filtrados.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
            Clientes
          </h1>
          {!loading && !err && clientes.length > 0 && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
              {clientes.length} cliente{clientes.length !== 1 ? "s" : ""} na
              carteira
            </p>
          )}
        </div>
        <Button size="sm" onClick={() => navigate("/cotacao")}>
          Nova cotação
        </Button>
      </div>

      <Input
        placeholder="Buscar por nome, e-mail ou telefone…"
        value={busca}
        onChange={(e) => setBusca(e.target.value)}
        className="max-w-sm"
      />

      {loading && (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Carregando…
        </p>
      )}

      {err && (
        <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-400">
          {err}
        </div>
      )}

      {!loading && !err && clientes.length === 0 && (
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-8 text-center text-sm text-gray-500 dark:text-gray-400">
          Nenhum cliente cadastrado ainda.
        </div>
      )}

      {!loading && !err && clientes.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 text-left">
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">
                  Nome
                </th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">
                  E-mail
                </th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">
                  Telefone
                </th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">
                  Profissão
                </th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">
                  Cadastro
                </th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300" />
              </tr>
            </thead>
            <tbody>
              {filtrados.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-sm text-gray-500 dark:text-gray-400"
                  >
                    Nenhum cliente encontrado para esta busca.
                  </td>
                </tr>
              ) : (
                paginated.map((c) => (
                  <tr
                    key={c.id}
                    className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer"
                    onClick={() => navigate(`/clientes/${c.id}`)}
                  >
                    <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                      {c.nome}
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
                        className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline whitespace-nowrap"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate("/cotacao");
                        }}
                      >
                        Nova cotação
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          {filtrados.length > 0 && (
            <div className="px-1">
              <Pagination
                page={page}
                total={filtrados.length}
                perPage={PAGE_SIZE}
                onChange={setPage}
              />
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
                {filtrados.length} cliente{filtrados.length !== 1 ? "s" : ""}
                {busca
                  ? ` encontrado${filtrados.length !== 1 ? "s" : ""}`
                  : " na carteira"}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
