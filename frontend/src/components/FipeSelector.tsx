import { useState, useEffect, useRef, useCallback } from "react";
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
  onInvalidate: () => void;
  savedVehicle?: { codigo_fipe?: unknown; marca?: unknown; modelo?: unknown; ano_modelo?: unknown };
  error?: string;
}

interface Option {
  codigo: string;
  nome: string;
}

function formatBRL(valor: string): string {
  // Parallelum already returns Brazilian-formatted strings like "R$ 74.463,00".
  // Re-parsing would corrupt the value (thousands dot gets treated as decimal).
  return valor || "—";
}

function Skeleton() {
  return (
    <div className="h-9 w-full rounded border border-line bg-canvas animate-pulse" />
  );
}

// Step indicator
function StepBar({ step }: { step: 1 | 2 | 3 }) {
  const steps = ["Marca", "Modelo", "Ano"];
  return (
    <div className="flex items-center gap-1 mb-4">
      {steps.map((label, i) => {
        const idx = i + 1;
        const done = idx < step;
        const active = idx === step;
        return (
          <div key={label} className="flex items-center gap-1 flex-1">
            <div className="flex items-center gap-2 min-w-0">
              <span
                className={[
                  "flex-shrink-0 w-5 h-5 rounded-full text-xs font-bold flex items-center justify-center",
                  done
                    ? "bg-surface text-success border border-line"
                    : active
                    ? "control-primary"
                    : "bg-surface text-muted ",
                ].join(" ")}
              >
                {done ? "✓" : idx}
              </span>
              <span
                className={[
                  "text-xs font-medium truncate",
                  active
                    ? "text-action "
                    : done
                    ? "text-success "
                    : "text-muted ",
                ].join(" ")}
              >
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div
                className={[
                  "flex-1 h-px mx-1",
                  done ? "bg-success" : "bg-surface ",
                ].join(" ")}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// Inline combobox with search
function ComboBox({
  label,
  options,
  value,
  placeholder,
  disabled,
  loading,
  onChange,
  onClear,
}: {
  label: string;
  options: Option[];
  value: string;
  placeholder: string;
  disabled?: boolean;
  loading?: boolean;
  onChange: (opt: Option) => void;
  onClear: () => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const listboxId = `listbox-${label.replace(/\s+/g, "-").toLowerCase()}`;

  const selectedLabel = options.find((o) => o.codigo === value)?.nome ?? "";

  const filtered = query
    ? options.filter((o) => o.nome.toLowerCase().includes(query.toLowerCase()))
    : options;

  const handleOpen = useCallback(() => {
    if (disabled) return;
    setQuery("");
    setOpen(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  }, [disabled]);

  const handleSelect = useCallback(
    (opt: Option) => {
      onChange(opt);
      setOpen(false);
      setQuery("");
    },
    [onChange]
  );

  const handleClear = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onClear();
      setOpen(false);
      setQuery("");
    },
    [onClear]
  );

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const baseCls =
    "w-full flex items-center justify-between h-9 px-3 rounded border text-sm transition-colors";
  const enabledCls =
    "border-line bg-surface text-ink cursor-pointer hover:border-line ";
  const disabledCls =
    "border-line bg-canvas text-muted cursor-not-allowed";

  if (loading) return <Skeleton />;

  return (
    <div ref={containerRef} className="relative">
      <p className="text-xs font-medium text-muted mb-1 uppercase tracking-wide">
        {label}
      </p>

      {/* Aria-live region for announcing current selection */}
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {value ? `${label} selecionado: ${selectedLabel}` : ""}
      </div>

      {/* Trigger */}
      {!open ? (
        <button
          type="button"
          role="combobox"
          aria-label={`Selecionar ${label} FIPE`}
          aria-expanded={false}
          aria-haspopup="listbox"
          aria-controls={listboxId}
          disabled={disabled}
          onClick={handleOpen}
          className={`${baseCls} ${disabled ? disabledCls : enabledCls}`}
        >
          <span className={value ? "text-ink " : "text-muted "}>
            {value ? selectedLabel : placeholder}
          </span>
          <span className="flex items-center gap-1 ml-2 flex-shrink-0">
            {value && !disabled && (
              <span
                role="button"
                aria-label={`Limpar seleção de ${label}`}
                onClick={handleClear}
                className="text-muted hover:text-muted text-lg leading-none"
              >
                ×
              </span>
            )}
            <svg
              className="w-4 h-4 text-muted"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </span>
        </button>
      ) : (
        <div className="rounded border border-line overflow-hidden shadow-panel bg-surface ">
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-label={`Buscar ${label} FIPE`}
            aria-expanded={true}
            aria-haspopup="listbox"
            aria-controls={listboxId}
            aria-autocomplete="list"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`Buscar ${label.toLowerCase()}...`}
            className="w-full px-3 py-2 text-sm bg-surface text-ink outline-none border-b border-line "
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setOpen(false);
                setQuery("");
              }
              if (e.key === "Enter" && filtered.length === 1) {
                handleSelect(filtered[0]);
              }
              if (e.key === "ArrowDown") {
                (listRef.current?.firstElementChild as HTMLElement)?.focus();
              }
            }}
          />
          <ul
            ref={listRef}
            id={listboxId}
            className="max-h-52 overflow-y-auto"
            role="listbox"
            aria-label={`Opções de ${label}`}
          >
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-sm text-muted italic">
                Nenhum resultado
              </li>
            ) : (
              filtered.map((opt) => (
                <li
                  key={opt.codigo}
                  role="option"
                  aria-selected={opt.codigo === value}
                  tabIndex={0}
                  onClick={() => handleSelect(opt)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") handleSelect(opt);
                    if (e.key === "ArrowDown")
                      (e.currentTarget.nextElementSibling as HTMLElement)?.focus();
                    if (e.key === "ArrowUp")
                      (e.currentTarget.previousElementSibling as HTMLElement)?.focus();
                  }}
                  className={[
                    "px-3 py-2 text-sm cursor-pointer outline-none",
                    opt.codigo === value
                      ? "bg-canvas text-action font-medium"
                      : "text-ink hover:bg-canvas focus:bg-canvas ",
                  ].join(" ")}
                >
                  {opt.nome}
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function FipeSelector({ tipo, onChange, onInvalidate, savedVehicle, error }: Props) {
  const [replacing, setReplacing] = useState(false);
  const [marcaId, setMarcaId] = useState("");
  const [marcaNome, setMarcaNome] = useState("");
  const [modeloId, setModeloId] = useState("");
  const [modeloNome, setModeloNome] = useState("");
  const [anoId, setAnoId] = useState("");

  const marcas = useFipeMarcas(tipo);
  const modelos = useFipeModelos(tipo, marcaId || null);
  const anos = useFipeAnos(tipo, marcaId || null, modeloId || null);
  const precoState = useFipePreco(tipo, marcaId || null, modeloId || null, anoId || null);

  const step: 1 | 2 | 3 = !marcaId ? 1 : !modeloId ? 2 : 3;

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

  if (savedVehicle?.codigo_fipe && !replacing) return (
    <div className="rounded border border-line bg-canvas p-4 space-y-3">
      <p className="text-xs text-muted">Veículo salvo</p>
      <p className="font-medium">{[savedVehicle.marca, savedVehicle.modelo, savedVehicle.ano_modelo].filter(Boolean).map(String).join(" · ")}</p>
      <p className="text-xs">Código FIPE: {String(savedVehicle.codigo_fipe)}</p>
      <button type="button" className="text-action underline" onClick={() => { setReplacing(true); onInvalidate(); }}>Trocar veículo</button>
    </div>
  );

  return (
    <div className="rounded border border-line bg-canvas p-4 space-y-3">
      <StepBar step={step} />

      <ComboBox
        label="Marca"
        options={marcas.data ?? []}
        value={marcaId}
        placeholder="Selecione a marca"
        loading={marcas.loading}
        onChange={(opt) => {
          onInvalidate();
          setMarcaId(opt.codigo);
          setMarcaNome(opt.nome);
          setModeloId("");
          setModeloNome("");
          setAnoId("");
        }}
        onClear={() => {
          onInvalidate();
          setMarcaId("");
          setMarcaNome("");
          setModeloId("");
          setModeloNome("");
          setAnoId("");
        }}
      />
      {marcas.error && (
        <p className="text-xs text-danger">Erro ao carregar marcas. Verifique sua conexão.</p>
      )}

      <ComboBox
        label="Modelo"
        options={modelos.data ?? []}
        value={modeloId}
        placeholder={marcaId ? "Selecione o modelo" : "Selecione a marca primeiro"}
        disabled={!marcaId}
        loading={!!marcaId && modelos.loading}
        onChange={(opt) => {
          onInvalidate();
          setModeloId(opt.codigo);
          setModeloNome(opt.nome);
          setAnoId("");
        }}
        onClear={() => {
          onInvalidate();
          setModeloId("");
          setModeloNome("");
          setAnoId("");
        }}
      />
      {modelos.error && (
        <p className="text-xs text-danger">Erro ao carregar modelos.</p>
      )}

      <ComboBox
        label="Ano / Combustível"
        options={anos.data ?? []}
        value={anoId}
        placeholder={modeloId ? "Selecione o ano" : "Selecione o modelo primeiro"}
        disabled={!modeloId}
        loading={!!modeloId && anos.loading}
        onChange={(opt) => { onInvalidate(); setAnoId(opt.codigo); }}
        onClear={() => { onInvalidate(); setAnoId(""); }}
      />
      {anos.error && (
        <p className="text-xs text-danger">Erro ao carregar anos.</p>
      )}

      {/* Resultado FIPE */}
      {precoState.loading && (
        <div className="mt-2">
          <Skeleton />
        </div>
      )}
      {precoState.data && !precoState.loading && (
        <div className="rounded border border-line bg-canvas px-4 py-3 space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-action ">
            Tabela FIPE
          </p>
          <p className="text-sm text-ink ">
            {precoState.data.marca} {precoState.data.modelo}
          </p>
          <p className="text-lg font-bold text-action ">
            {formatBRL(precoState.data.valor)}
          </p>
          <div className="flex flex-wrap gap-2 mt-1">
            <span className="inline-flex items-center rounded-full bg-canvas px-2 py-1 text-xs font-medium text-action ">
              Cód. {precoState.data.codigo_fipe}
            </span>
            <span className="inline-flex items-center rounded-full bg-canvas px-2 py-1 text-xs text-muted ">
              {precoState.data.combustivel}
            </span>
            <span className="inline-flex items-center rounded-full bg-canvas px-2 py-1 text-xs text-muted ">
              Ref. {precoState.data.mes_referencia}
            </span>
          </div>
        </div>
      )}
      {precoState.error && (
        <div className="rounded border border-line bg-canvas px-3 py-2">
          <p className="text-xs text-warning ">
            Não foi possível consultar o veículo. Selecione o ano novamente para tentar outra vez.
          </p>
        </div>
      )}

      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
