import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Cliente } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function fmtData(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR");
}

const MOCK_CLIENTES: Cliente[] = [
  {
    id: "mock-c1",
    nome: "Ana Beatriz Costa",
    email: "ana.costa@clientes.demo",
    telefone: "11998760001",
    data_nascimento: "1985-04-12",
    sexo: "F",
    estado_civil: "casado",
    profissao: "assalariado",
    usuario_id: "mock-u1",
    criado_em: new Date(Date.now() - 30 * 86400000).toISOString(),
  },
  {
    id: "mock-c2",
    nome: "Carlos Eduardo Lima",
    email: "carlos.lima@clientes.demo",
    telefone: "11997650002",
    data_nascimento: "1978-11-25",
    sexo: "M",
    estado_civil: "casado",
    profissao: "empresario",
    usuario_id: "mock-u1",
    criado_em: new Date(Date.now() - 60 * 86400000).toISOString(),
  },
  {
    id: "mock-c3",
    nome: "Fernanda Souza",
    email: "fernanda.souza@clientes.demo",
    telefone: "11996540003",
    data_nascimento: "1992-07-08",
    sexo: "F",
    estado_civil: "solteiro",
    profissao: "autonomo",
    usuario_id: "mock-u1",
    criado_em: new Date(Date.now() - 15 * 86400000).toISOString(),
  },
  {
    id: "mock-c4",
    nome: "Ricardo Oliveira",
    email: null,
    telefone: "11995430004",
    data_nascimento: "1965-02-19",
    sexo: "M",
    estado_civil: "viuvo",
    profissao: "aposentado",
    usuario_id: "mock-u1",
    criado_em: new Date(Date.now() - 90 * 86400000).toISOString(),
  },
  {
    id: "mock-c5",
    nome: "Juliana Martins Pereira",
    email: "juliana.martins@clientes.demo",
    telefone: "11994320005",
    data_nascimento: "1990-09-30",
    sexo: "F",
    estado_civil: "casado",
    profissao: "servidor_publico",
    usuario_id: "mock-u1",
    criado_em: new Date(Date.now() - 5 * 86400000).toISOString(),
  },
];

export function ClientesPage() {
  const navigate = useNavigate();
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [loading, setLoading] = useState(true);
  const [busca, setBusca] = useState("");

  useEffect(() => {
    api.clientes
      .list()
      .then((data) => setClientes(data.length > 0 ? data : MOCK_CLIENTES))
      .catch(() => setClientes(MOCK_CLIENTES))
      .finally(() => setLoading(false));
  }, []);

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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Clientes</h1>
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

      {loading ? (
        <p className="text-sm text-gray-500">Carregando…</p>
      ) : filtrados.length === 0 ? (
        <p className="text-sm text-gray-500">
          {busca ? "Nenhum cliente encontrado para esta busca." : "Nenhum cliente cadastrado."}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 border-b text-left">
                <th className="px-4 py-2 font-medium">Nome</th>
                <th className="px-4 py-2 font-medium">E-mail</th>
                <th className="px-4 py-2 font-medium">Telefone</th>
                <th className="px-4 py-2 font-medium">Profissão</th>
                <th className="px-4 py-2 font-medium">Cadastro</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {filtrados.map((c) => (
                <tr
                  key={c.id}
                  className="border-b hover:bg-gray-50 cursor-pointer"
                  onClick={() => navigate(`/clientes/${c.id}`)}
                >
                  <td className="px-4 py-3 font-medium">{c.nome}</td>
                  <td className="px-4 py-3 text-gray-600">{c.email ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-600">{c.telefone ?? "—"}</td>
                  <td className="px-4 py-3 capitalize text-gray-600">
                    {c.profissao?.replace("_", " ") ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{fmtData(c.criado_em)}</td>
                  <td className="px-4 py-3">
                    <button
                      className="text-xs text-indigo-600 hover:underline whitespace-nowrap"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/cotacao`);
                      }}
                    >
                      Nova cotação
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-gray-400 mt-2 px-1">
            {filtrados.length} cliente{filtrados.length !== 1 ? "s" : ""}
            {busca ? ` encontrado${filtrados.length !== 1 ? "s" : ""}` : " na carteira"}
          </p>
        </div>
      )}
    </div>
  );
}
