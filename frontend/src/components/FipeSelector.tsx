import { useState, useEffect } from "react";
import { useFipeMarcas, useFipeModelos, useFipeAnos, useFipePreco } from "@/hooks/useFipe";

export interface FipeResult {
  codigo_fipe: string;
  marca: string;
  modelo: string;
  ano_modelo: string;
  combustivel: string;
  valor: string;
  valor_fipe: string;
}

interface Props {
  tipo: "carros" | "motos";
  onChange: (fipe: FipeResult) => void;
  error?: string;
}

function formatBRL(valor: string): string {
  const clean = valor.replace(/[R$\s]/g, "").replace(",", ".");
  const num = parseFloat(clean);
  if (isNaN(num)) return valor;
  return num.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function Skeleton() {
  return (
    <div className="h-9 w-full rounded border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-700 animate-pulse" />
  );
}

const labelCls = "block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1";
const selectCls =
  "flex h-9 w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50";
const inputCls =
  "flex h-9 w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500";

export default function FipeSelector({ tipo, onChange, error }: Props) {
  const [marcaId, setMarcaId] = useState<string | null>(null);
  const [marcaNome, setMarcaNome] = useState("");
  const [modeloId, setModeloId] = useState<string | null>(null);
  const [modeloNome, setModeloNome] = useState("");
  const [anoId, setAnoId] = useState<string | null>(null);
  const [filtroMarca, setFiltroMarca] = useState("");

  const marcas = useFipeMarcas(tipo);
  const modelos = useFipeModelos(tipo, marcaId);
  const anos = useFipeAnos(tipo, marcaId, modeloId);
  const precoState = useFipePreco(tipo, marcaId, modeloId, anoId);

  useEffect(() => {
    if (precoState.data && !precoState.loading) {
      const d = precoState.data;
      onChange({
        codigo_fipe: d.codigo_fipe,
        marca: d.marca || marcaNome,
        modelo: d.modelo || modeloNome,
        ano_modelo: d.ano_modelo,
        combustivel: d.combustivel,
        valor: d.valor,
        valor_fipe: d.valor,
      });
    }
  }, [precoState.data, precoState.loading]); // eslint-disable-line react-hooks/exhaustive-deps

  const marcasFiltradas = (marcas.data ?? []).filter((m) =>
    m.nome.toLowerCase().includes(filtroMarca.toLowerCase())
  );

  return (
    <div className="space-y-4">
      {/* Marca */}
      <div>
        <label className={labelCls}>Marca</label>
        {marcas.loading ? (
          <Skeleton />
        ) : marcas.error ? (
          <p className="text-xs text-red-500">Erro ao carregar marcas. Verifique sua conexão.</p>
        ) : (
          <div className="space-y-1">
            <input
              type="text"
              placeholder="Buscar marca..."
              value={filtroMarca}
              onChange={(e) => setFiltroMarca(e.target.value)}
              className={inputCls}
            />
            <select
              className={selectCls}
              value={marcaId ?? ""}
              onChange={(e) => {
                const opt = e.target.options[e.target.selectedIndex];
                setMarcaId(e.target.value || null);
                setMarcaNome(opt.text);
                setModeloId(null);
                setModeloNome("");
                setAnoId(null);
                setFiltroMarca("");
              }}
            >
              <option value="">Selecione a marca</option>
              {marcasFiltradas.map((m) => (
                <option key={m.codigo} value={m.codigo}>
                  {m.nome}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Modelo */}
      <div>
        <label className={labelCls}>Modelo</label>
        {modelos.loading ? (
          <Skeleton />
        ) : (
          <select
            className={selectCls}
            disabled={!marcaId}
            value={modeloId ?? ""}
            onChange={(e) => {
              const opt = e.target.options[e.target.selectedIndex];
              setModeloId(e.target.value || null);
              setModeloNome(opt.text);
              setAnoId(null);
            }}
          >
            <option value="">
              {marcaId ? "Selecione o modelo" : "Selecione a marca primeiro"}
            </option>
            {(modelos.data ?? []).map((m) => (
              <option key={m.codigo} value={m.codigo}>
                {m.nome}
              </option>
            ))}
          </select>
        )}
        {modelos.error && (
          <p className="mt-1 text-xs text-red-500">Erro ao carregar modelos.</p>
        )}
      </div>

      {/* Ano / Combustível */}
      <div>
        <label className={labelCls}>Ano / Combustível</label>
        {anos.loading ? (
          <Skeleton />
        ) : (
          <select
            className={selectCls}
            disabled={!modeloId}
            value={anoId ?? ""}
            onChange={(e) => setAnoId(e.target.value || null)}
          >
            <option value="">
              {modeloId ? "Selecione o ano" : "Selecione o modelo primeiro"}
            </option>
            {(anos.data ?? []).map((a) => (
              <option key={a.codigo} value={a.codigo}>
                {a.nome}
              </option>
            ))}
          </select>
        )}
        {anos.error && <p className="mt-1 text-xs text-red-500">Erro ao carregar anos.</p>}
      </div>

      {/* Resultado FIPE */}
      {precoState.loading && <Skeleton />}
      {precoState.data && !precoState.loading && (
        <div className="rounded border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/30 px-4 py-3 space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-blue-600 dark:text-blue-400">
            Tabela FIPE
          </p>
          <p className="text-sm text-gray-800 dark:text-gray-200">
            <span className="font-medium">Código:</span>{" "}
            <span className="font-mono">{precoState.data.codigo_fipe}</span>
          </p>
          <p className="text-base font-semibold text-blue-700 dark:text-blue-300">
            Valor FIPE: {formatBRL(precoState.data.valor)}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {precoState.data.combustivel} · Ref. {precoState.data.mes_referencia}
          </p>
        </div>
      )}
      {precoState.error && (
        <div className="rounded border border-yellow-200 dark:border-yellow-700 bg-yellow-50 dark:bg-yellow-900/30 px-4 py-3">
          <p className="text-sm text-yellow-700 dark:text-yellow-300">
            Não foi possível consultar o valor FIPE. Você pode continuar mesmo assim.
          </p>
        </div>
      )}

      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
    </div>
  );
}
