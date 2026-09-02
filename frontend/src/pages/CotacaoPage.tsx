import { useCallback, useEffect, useRef, useState, useId } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  api,
  type Cotacao,
  type Dominio,
  type Cliente,
  type ItemComparativo,
  type Proposta,
  ApiError,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Tooltip } from "@/components/Tooltip";
import { formatBRL, stripCPF } from "@/lib/utils";
import FipeSelector, { type FipeResult } from "@/components/FipeSelector";

const STORAGE_KEY = "mk_cotacao_rascunho";
const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 120_000;

// ---------------------------------------------------------------------------
// Rascunho — sessionStorage apenas (PII não persiste além da sessão)
// ---------------------------------------------------------------------------

interface Rascunho {
  ramo: string;
  step: number;
  step2?: Step2Data;
  step3?: Step3Data;
  step4?: Step4Data;
  clienteId?: string;
}

function saveRascunho(r: Rascunho) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(r));
}

function loadRascunho(): Rascunho | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Rascunho) : null;
  } catch {
    return null;
  }
}

function clearRascunho() {
  sessionStorage.removeItem(STORAGE_KEY);
}

// ---------------------------------------------------------------------------
// Step schemas
// ---------------------------------------------------------------------------

const step1Schema = z.object({
  nome: z.string().min(2, "Nome muito curto"),
  cpf: z
    .string()
    .transform(stripCPF)
    .pipe(z.string().length(11, "CPF deve ter 11 dígitos")),
  email: z.string().email("E-mail inválido").optional().or(z.literal("")),
  telefone: z.string().optional(),
  data_nascimento: z
    .string()
    .optional()
    .refine(
      (val) => {
        if (!val) return true;
        const d = new Date(val);
        if (isNaN(d.getTime())) return false;
        const hoje = new Date();
        hoje.setHours(0, 0, 0, 0);
        if (d > hoje) return false;
        const minDate = new Date();
        minDate.setFullYear(minDate.getFullYear() - 100);
        return d >= minDate;
      },
      { message: "Data inválida (deve ser entre hoje e 100 anos atrás)" }
    ),
  sexo: z.enum(["M", "F", ""]).optional(),
  estado_civil: z.string().optional(),
  profissao: z.string().optional(),
});

const step2AutoSchema = z.object({
  cep_pernoite: z
    .string()
    .transform((v) => v.replace(/\D/g, ""))
    .pipe(z.string().length(8, "CEP deve ter 8 dígitos")),
  codigo_fipe: z.string().min(1, "Selecione o veículo na tabela FIPE"),
  placa: z.string().optional(),
  marca: z.string().optional(),
  modelo: z.string().optional(),
  ano_modelo: z.string().optional(),
  combustivel: z.string().optional(),
  valor_fipe: z.string().optional(),
  finalidade: z.string().min(1, "Obrigatório"),
  blindado: z.boolean().optional(),
  garagem: z.boolean().optional(),
  zero_km: z.boolean().optional().default(false),
  ja_segurado: z.boolean().optional().default(false),
  bonus_anterior: z.coerce.number().int().min(0).max(10).optional().default(0),
  // Condutor principal (Justos main_driver) — opcional
  condutor_diferente: z.boolean().optional().default(false),
  condutor_cpf: z
    .string()
    .transform((v) => v.replace(/\D/g, ""))
    .pipe(z.string().length(11, "CPF deve ter 11 dígitos").or(z.literal("")))
    .optional(),
  condutor_nome: z.string().optional(),
  condutor_sexo: z.enum(["M", "F", ""]).optional(),
  condutor_nascimento: z.string().optional(),
  condutor_parentesco: z.string().optional(),
});

const step2MotoSchema = z.object({
  cep_pernoite: z
    .string()
    .transform((v) => v.replace(/\D/g, ""))
    .pipe(z.string().length(8, "CEP deve ter 8 dígitos")),
  codigo_fipe: z.string().min(1, "Selecione o veículo na tabela FIPE"),
  placa: z.string().optional(),
  marca: z.string().optional(),
  modelo: z.string().optional(),
  ano_modelo: z.string().optional(),
  combustivel: z.string().optional(),
  valor_fipe: z.string().optional(),
  cilindrada: z
    .string()
    .transform(Number)
    .pipe(z.number().int().min(50).max(2500)),
  categoria: z.string().min(1, "Obrigatório"),
  finalidade: z.string().min(1, "Obrigatório"),
  garagem: z.boolean().optional(),
});

const step2ImovelSchema = z.object({
  cep: z
    .string()
    .transform((v) => v.replace(/\D/g, ""))
    .pipe(z.string().length(8, "CEP deve ter 8 dígitos")),
  tipo_imovel: z.string().min(1, "Obrigatório"),
  tipo_construcao: z.string().min(1, "Obrigatório"),
  valor_imovel: z
    .string()
    .transform((v) => v.replace(/\./g, "").replace(",", "."))
    .pipe(z.coerce.number().positive("Valor do imóvel deve ser maior que zero"))
    .transform(String),
  valor_conteudo: z
    .string()
    .optional()
    .transform((v) => (v ? v.replace(/\./g, "").replace(",", ".") : "0"))
    .pipe(z.coerce.number().min(0))
    .transform(String),
  alarme: z.boolean().optional().default(false),
  cerca_eletrica: z.boolean().optional().default(false),
  grades: z.boolean().optional().default(false),
});

const step3Schema = z.object({
  coberturas: z.array(z.string()).min(1, "Selecione ao menos uma cobertura"),
});

const step4Schema = z
  .object({
    plano_pagamento: z.string().min(1, "Selecione o plano"),
    inicio_vigencia: z.string().min(1, "Data de início obrigatória"),
    fim_vigencia: z.string().min(1, "Data de fim obrigatória"),
  })
  .superRefine((data, ctx) => {
    if (
      data.inicio_vigencia &&
      data.fim_vigencia &&
      data.fim_vigencia <= data.inicio_vigencia
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Fim da vigência deve ser posterior ao início",
        path: ["fim_vigencia"],
      });
    }
  });

type Step1Data = z.infer<typeof step1Schema>;
type Step2Data = Record<string, unknown>;
type Step3Data = z.infer<typeof step3Schema>;
type Step4Data = z.infer<typeof step4Schema>;

// ---------------------------------------------------------------------------
// Loading panel (polling)
// ---------------------------------------------------------------------------

function LoadingPanel({
  seconds,
  onCancel,
}: {
  seconds: number;
  onCancel: () => void;
}) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6 text-center space-y-4">
      <div className="flex items-center justify-center gap-3">
        <svg
          className="animate-spin h-5 w-5 text-blue-500"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
          Consultando seguradoras… {seconds}s
        </span>
      </div>
      <Button variant="outline" size="sm" onClick={onCancel}>
        Cancelar
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Transmitir modal
// ---------------------------------------------------------------------------

const PARCELAMENTOS = ["AVISTA", "2X", "3X", "6X", "10X"];

interface TransmitirModalProps {
  cotacaoId: string;
  cia?: string;
  vigenciaInicio?: string;
  onClose: () => void;
  onSuccess: (p: Proposta) => void;
}

function TransmitirModal({
  cotacaoId,
  cia = "fake",
  vigenciaInicio,
  onClose,
  onSuccess,
}: TransmitirModalProps) {
  const [plano, setPlano] = useState("AVISTA");
  const [parcelas, setParcelas] = useState(1);
  const [comissao, setComissao] = useState("0.1500");
  const [vigencia, setVigencia] = useState(
    vigenciaInicio ?? new Date().toISOString().slice(0, 10),
  );
  // Justos-specific: policy_type mensal/anual
  const [policyType, setPolicyType] = useState<"monthly" | "annual">("monthly");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [comissaoErr, setComissaoErr] = useState<string | null>(null);

  const isJustos = cia === "justos";

  const handleComissaoChange = (pct: number) => {
    if (pct < 0 || pct > 30) {
      setComissaoErr("Comissão deve ser entre 0% e 30%");
    } else {
      setComissaoErr(null);
    }
    setComissao((pct / 100).toFixed(4));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const pct = Number(comissao) * 100;
    if (pct < 0 || pct > 30) {
      setComissaoErr("Comissão deve ser entre 0% e 30%");
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const dadosNegocio = isJustos
        ? { policy_type: policyType, ...(policyType === "annual" ? { installments: parcelas } : {}) }
        : {};
      const proposta = await api.cotacoes.transmitir(cotacaoId, {
        plano_pagamento: plano,
        n_parcelas: parcelas,
        comissao_pct: comissao,
        inicio_vigencia: vigencia,
        cia,
        dados_negocio: dadosNegocio,
      });
      onSuccess(proposta);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Erro ao transmitir");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6">
        <h2 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">Transmitir proposta</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          {isJustos && (
            <div>
              <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-200">Tipo de pagamento</label>
              <div className="flex gap-4">
                {(["monthly", "annual"] as const).map((t) => (
                  <label key={t} className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                    <input
                      type="radio"
                      name="policy_type"
                      value={t}
                      checked={policyType === t}
                      onChange={() => setPolicyType(t)}
                    />
                    {t === "monthly" ? "Mensal" : "Anual"}
                  </label>
                ))}
              </div>
            </div>
          )}
          <div>
            <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-200">Parcelamento</label>
            <select
              className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              value={plano}
              onChange={(e) => {
                setPlano(e.target.value);
                setParcelas(
                  e.target.value === "AVISTA"
                    ? 1
                    : Number(e.target.value.replace("X", "")),
                );
              }}
            >
              {PARCELAMENTOS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-200">Comissão (%)</label>
            <input
              type="number"
              step="0.5"
              min="0"
              max="30"
              className={`w-full border rounded px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 ${comissaoErr ? "border-red-500 dark:border-red-500" : "border-gray-300 dark:border-gray-600"}`}
              value={Number(comissao) * 100}
              onChange={(e) => handleComissaoChange(Number(e.target.value))}
            />
            {comissaoErr && (
              <p className="text-xs text-red-600 dark:text-red-400 mt-1" role="alert">
                {comissaoErr}
              </p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-200">Início vigência</label>
            <input
              type="date"
              className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              value={vigencia}
              onChange={(e) => setVigencia(e.target.value)}
            />
          </div>
          {err && (
            <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 px-4 py-3 flex items-start gap-3">
              <div className="flex-1 text-sm text-red-700 dark:text-red-400">{err}</div>
              <button
                type="button"
                onClick={() => setErr(null)}
                className="text-red-400 hover:text-red-600 dark:hover:text-red-200 leading-none text-lg flex-shrink-0"
                aria-label="Fechar erro"
              >
                ×
              </button>
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" disabled={loading || !!comissaoErr}>
              {loading ? "Transmitindo…" : "Confirmar"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    sucesso: "bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300",
    restricao: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300",
    erro: "bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300",
    processando: "bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300",
    aguardando: "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300",
  };
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${map[status] ?? "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"}`}
    >
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Comparativo inline — substituiu o ResultPanel no passo 5
// ---------------------------------------------------------------------------

interface ComparativoInlineProps {
  cotacao: Cotacao;
  cotacaoId: string;
  itens: ItemComparativo[];
  proposta: Proposta | null;
  onEmitir: (cia: string) => void;
  onRecotar: () => void;
}

function ComparativoInline({
  cotacao,
  cotacaoId,
  itens,
  proposta,
  onEmitir,
  onRecotar,
}: ComparativoInlineProps) {
  const navigate = useNavigate();

  // Proposta gerada com sucesso
  if (proposta) {
    return (
      <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 rounded-lg p-5 space-y-1">
        <p className="font-semibold text-green-800 dark:text-green-300">Proposta transmitida com sucesso!</p>
        <p className="text-sm text-green-700 dark:text-green-400">
          Protocolo:{" "}
          <span className="font-mono font-semibold">{proposta.protocolo}</span>
        </p>
        <p className="text-sm text-green-700 dark:text-green-400">
          {proposta.n_parcelas}× de {formatBRL(proposta.valor_parcela)}
        </p>
        {cotacao.cliente_id && (
          <Button
            className="mt-3"
            size="sm"
            variant="outline"
            onClick={() => navigate(`/clientes/${cotacao.cliente_id}`)}
          >
            Ver timeline do cliente
          </Button>
        )}
      </div>
    );
  }

  // Erro da seguradora
  if (cotacao.status === "erro") {
    return (
      <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-6">
        <h3 className="font-medium text-red-800 dark:text-red-300 mb-2">Cotação não realizada</h3>
        <p className="text-sm text-red-700 dark:text-red-400">
          {cotacao.mensagens[0] ??
            "A seguradora não pôde calcular o prêmio para este risco."}
        </p>
        <Tooltip text="Reenvia os mesmos dados para a seguradora tentar calcular novamente">
          <Button variant="outline" size="sm" className="mt-4" onClick={onRecotar}>
            Tentar novamente
          </Button>
        </Tooltip>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-gray-900 dark:text-white">
          Resultados —{" "}
          {cotacao.ramo.charAt(0).toUpperCase() + cotacao.ramo.slice(1)}
        </h3>
        <StatusBadge status={cotacao.status} />
      </div>

      {cotacao.necessita_vistoria && (
        <p className="text-sm font-medium text-yellow-700 dark:text-yellow-300 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-800 rounded px-3 py-2">
          Vistoria prévia obrigatória — prazo de emissão estendido.
        </p>
      )}

      {itens.length === 0 ? (
        <p className="text-sm text-gray-500 py-4">Processando resultados…</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 text-left">
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Seguradora</th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Mensal</th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Anual</th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Observações</th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Vistoria</th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Status</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {(() => {
                const aprovados = itens.filter(
                  (it) => (it.status === "sucesso" || it.status === "restricao") && it.premio_total,
                );
                const minPreco =
                  aprovados.length > 0
                    ? Math.min(...aprovados.map((it) => parseFloat(it.premio_total!)))
                    : null;
                return itens.map((item, i) => {
                  const isBest =
                    minPreco !== null &&
                    item.premio_total !== null &&
                    parseFloat(item.premio_total) === minPreco;
                  return (
                    <tr
                      key={i}
                      className={
                        isBest
                          ? "border-b border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20"
                          : "border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                      }
                    >
                      <td className="px-4 py-3 font-semibold uppercase">
                        {item.cia}
                        {isBest && (
                          <span className="ml-2 inline-block text-[10px] font-bold uppercase tracking-wide text-green-700 dark:text-green-400 bg-green-100 dark:bg-green-900/50 border border-green-300 dark:border-green-700 rounded px-1.5 py-0.5">
                            Melhor preço
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono">{formatBRL(item.premio_total)}</td>
                      <td className="px-4 py-3 font-mono text-gray-500 dark:text-gray-400">
                        {item.annual_total ? formatBRL(item.annual_total) : <span className="text-gray-300 dark:text-gray-600">—</span>}
                      </td>
                      <td className="px-4 py-3 max-w-xs">
                        {item.restricoes.length === 0 && item.mensagens.length === 0 ? (
                          <span className="text-gray-400">—</span>
                        ) : (
                          <>
                            {item.restricoes.map((r) => (
                              <span key={r.codigo} className="block text-xs text-yellow-700 dark:text-yellow-400">
                                {r.codigo}: {r.mensagem}
                              </span>
                            ))}
                            {item.mensagens.map((m, j) => (
                              <span key={j} className="block text-xs text-blue-600 dark:text-blue-400">
                                {m}
                              </span>
                            ))}
                          </>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {item.necessita_vistoria ? (
                          <span className="text-yellow-700 dark:text-yellow-400 text-xs font-medium">Sim</span>
                        ) : (
                          <span className="text-gray-400 text-xs">Não</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={item.status} />
                      </td>
                      <td className="px-4 py-3">
                        {(item.status === "sucesso" || item.status === "restricao") && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => onEmitir(item.cia)}
                          >
                            Emitir
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                });
              })()}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center gap-3 flex-wrap">
        <a
          href={api.cotacoes.comparativoPdfUrl(cotacaoId)}
          target="_blank"
          rel="noreferrer"
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        >
          Baixar PDF
        </a>
        <Tooltip text="Refaz a cotação com os mesmos dados do risco, gerando um novo comparativo">
          <Button variant="outline" onClick={onRecotar}>
            Refazer cotação
          </Button>
        </Tooltip>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Field row helper
// ---------------------------------------------------------------------------

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 1 — Proponente
// ---------------------------------------------------------------------------

function Step1({
  dominios,
  defaultValues,
  onNext,
}: {
  dominios: Dominio[];
  defaultValues?: Partial<Step1Data & { cpf?: string }>;
  onNext: (data: Step1Data, cliente: Cliente | null) => void;
}) {
  const [searching, setSearching] = useState(false);
  const [foundCliente, setFoundCliente] = useState<Cliente | null>(null);
  const [cpfSearchError, setCpfSearchError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<Step1Data & { cpf?: string }>({
    resolver: zodResolver(step1Schema),
    defaultValues: defaultValues ?? {},
  });

  const estadosCivis = dominios.filter((d) => d.tipo === "estado_civil");
  const profissoes = dominios.filter((d) => d.tipo === "profissao");

  const searchByCpf = async (cpf: string) => {
    const digits = stripCPF(cpf);
    if (digits.length !== 11) return;
    setSearching(true);
    setCpfSearchError(null);
    try {
      const results = await api.clientes.busca(digits);
      if (results.length > 0) {
        const c = results[0];
        setFoundCliente(c);
        setValue("nome", c.nome);
        if (c.email) setValue("email", c.email);
        if (c.telefone) setValue("telefone", c.telefone);
        if (c.estado_civil) setValue("estado_civil", c.estado_civil);
        if (c.profissao) setValue("profissao", c.profissao);
        if (c.data_nascimento) setValue("data_nascimento", c.data_nascimento);
        if (c.sexo) setValue("sexo", c.sexo as "M" | "F");
      }
    } catch (e) {
      if (!(e instanceof ApiError) || e.status >= 500) {
        setCpfSearchError("Falha ao buscar cliente. Preencha os dados manualmente.");
      }
    } finally {
      setSearching(false);
    }
  };

  const onSubmit = async (data: Step1Data & { cpf?: string }) => {
    if (!foundCliente) {
      try {
        const created = await api.clientes.create({
          nome: data.nome,
          cpf: stripCPF(data.cpf ?? ""),
          email: data.email || undefined,
          telefone: data.telefone || undefined,
          data_nascimento: data.data_nascimento || undefined,
          sexo: data.sexo || undefined,
          estado_civil: data.estado_civil || undefined,
          profissao: data.profissao || undefined,
        });
        onNext(data, created);
      } catch {
        onNext(data, null);
      }
    } else {
      onNext(data, foundCliente);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <Field label="CPF" error={errors.cpf?.message}>
        <Input
          placeholder="000.000.000-00"
          {...register("cpf")}
          onBlur={(e) => searchByCpf(e.target.value)}
          disabled={searching}
        />
      </Field>
      {searching && <p className="text-xs text-gray-500">Buscando cliente…</p>}
      {foundCliente && (
        <p className="text-xs text-green-700 bg-green-50 dark:bg-green-900/30 dark:text-green-400 rounded px-2 py-1">
          Cliente encontrado: {foundCliente.nome}
        </p>
      )}
      {cpfSearchError && (
        <p className="text-xs text-yellow-800 bg-yellow-50 dark:bg-yellow-900/30 dark:text-yellow-400 border border-yellow-200 dark:border-yellow-700 rounded px-2 py-1">
          {cpfSearchError}
        </p>
      )}

      <Field label="Nome completo" error={errors.nome?.message}>
        <Input {...register("nome")} />
      </Field>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="E-mail" error={errors.email?.message}>
          <Input type="email" {...register("email")} />
        </Field>
        <Field label="Telefone">
          <Input {...register("telefone")} />
        </Field>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Data de nascimento" error={errors.data_nascimento?.message}>
          <Input type="date" {...register("data_nascimento")} />
        </Field>
        <Field label="Sexo">
          <Select {...register("sexo")}>
            <option value="">—</option>
            <option value="M">Masculino</option>
            <option value="F">Feminino</option>
          </Select>
        </Field>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Estado civil">
          <Select {...register("estado_civil")}>
            <option value="">—</option>
            {estadosCivis.map((d) => (
              <option key={d.codigo} value={d.codigo}>
                {d.descricao}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Profissão">
          <Select {...register("profissao")}>
            <option value="">—</option>
            {profissoes.length > 0
              ? profissoes.map((d) => (
                  <option key={d.codigo} value={d.codigo}>
                    {d.descricao}
                  </option>
                ))
              : [
                  ["autonomo", "Autônomo"],
                  ["assalariado", "Assalariado"],
                  ["empresario", "Empresário"],
                  ["aposentado", "Aposentado"],
                  ["estudante", "Estudante"],
                  ["servidor_publico", "Servidor público"],
                ].map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
          </Select>
        </Field>
      </div>

      <div className="pt-2 flex justify-end">
        <Button type="submit">Próximo →</Button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Step 2 Auto
// ---------------------------------------------------------------------------

function Step2Auto({
  defaultValues,
  onBack,
  onNext,
}: {
  defaultValues?: Step2Data;
  onBack: () => void;
  onNext: (data: Step2Data) => void;
}) {
  const condutorId = useId();
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<z.infer<typeof step2AutoSchema>>({
    resolver: zodResolver(step2AutoSchema),
    defaultValues: defaultValues as z.infer<typeof step2AutoSchema>,
  });

  const condutorDiferente = watch("condutor_diferente");

  function handleFipe(fipe: FipeResult) {
    setValue("codigo_fipe", fipe.codigo_fipe, { shouldValidate: true });
    setValue("marca", fipe.marca);
    setValue("modelo", fipe.modelo);
    setValue("ano_modelo", fipe.ano_modelo);
    setValue("combustivel", fipe.combustivel);
    setValue("valor_fipe", fipe.valor_fipe);
  }

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-4">
      <FipeSelector
        tipo="carros"
        onChange={handleFipe}
        error={errors.codigo_fipe?.message}
      />

      <Field label="Placa (opcional)" error={undefined}>
        <Input
          placeholder="ABC-1234 ou ABC1D23"
          {...register("placa")}
        />
      </Field>

      <Field label="CEP de pernoite" error={errors.cep_pernoite?.message}>
        <Input placeholder="00000-000" {...register("cep_pernoite")} />
      </Field>

      <Field label="Finalidade" error={errors.finalidade?.message}>
        <Select {...register("finalidade")}>
          <option value="">—</option>
          <option value="pessoal">Pessoal / Lazer</option>
          <option value="comercial">Comercial</option>
          <option value="app">Uber / App de transporte</option>
          <option value="taxi">Táxi</option>
        </Select>
      </Field>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
          <input type="checkbox" {...register("blindado")} />
          Blindado
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
          <input type="checkbox" {...register("garagem")} />
          Tem garagem
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
          <input type="checkbox" {...register("zero_km")} />
          0 km
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
          <input type="checkbox" {...register("ja_segurado")} />
          Já tem seguro
        </label>
      </div>

      <Field label="Bônus atual (0–10)" error={undefined}>
        <Select {...register("bonus_anterior")}>
          {Array.from({ length: 11 }, (_, i) => (
            <option key={i} value={i}>
              {i === 0 ? "0 — Sem bônus" : `${i}`}
            </option>
          ))}
        </Select>
      </Field>

      {/* Condutor principal */}
      <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
        <label
          htmlFor={condutorId}
          className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 cursor-pointer"
        >
          <input
            id={condutorId}
            type="checkbox"
            {...register("condutor_diferente")}
          />
          Condutor principal diferente do segurado
        </label>

        {condutorDiferente && (
          <div className="space-y-3 pt-1">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="CPF do condutor" error={errors.condutor_cpf?.message}>
                <Input placeholder="000.000.000-00" {...register("condutor_cpf")} />
              </Field>
              <Field label="Nome completo">
                <Input {...register("condutor_nome")} />
              </Field>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Field label="Sexo">
                <Select {...register("condutor_sexo")}>
                  <option value="">—</option>
                  <option value="M">Masculino</option>
                  <option value="F">Feminino</option>
                </Select>
              </Field>
              <Field label="Nascimento">
                <Input type="date" {...register("condutor_nascimento")} />
              </Field>
              <Field label="Parentesco">
                <Select {...register("condutor_parentesco")}>
                  <option value="">—</option>
                  <option value="conjuge">Cônjuge</option>
                  <option value="filho">Filho(a)</option>
                  <option value="pai">Pai / Mãe</option>
                  <option value="irmao">Irmão(ã)</option>
                  <option value="outro">Outro</option>
                </Select>
              </Field>
            </div>
          </div>
        )}
      </div>

      <div className="pt-2 flex justify-between">
        <Button type="button" variant="outline" onClick={onBack}>
          ← Voltar
        </Button>
        <Button type="submit">Próximo →</Button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Step 2 Moto
// ---------------------------------------------------------------------------

function Step2Moto({
  defaultValues,
  onBack,
  onNext,
}: {
  defaultValues?: Step2Data;
  onBack: () => void;
  onNext: (data: Step2Data) => void;
}) {
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<z.infer<typeof step2MotoSchema>>({
    resolver: zodResolver(step2MotoSchema),
    defaultValues: defaultValues as z.infer<typeof step2MotoSchema>,
  });

  function handleFipe(fipe: FipeResult) {
    setValue("codigo_fipe", fipe.codigo_fipe, { shouldValidate: true });
    setValue("marca", fipe.marca);
    setValue("modelo", fipe.modelo);
    setValue("ano_modelo", fipe.ano_modelo);
    setValue("combustivel", fipe.combustivel);
    setValue("valor_fipe", fipe.valor_fipe);
  }

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-4">
      <FipeSelector
        tipo="motos"
        onChange={handleFipe}
        error={errors.codigo_fipe?.message}
      />

      <Field label="Placa (opcional)" error={undefined}>
        <Input placeholder="ABC-1234 ou ABC1D23" {...register("placa")} />
      </Field>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Cilindrada (cc)" error={errors.cilindrada?.message}>
          <Input type="number" placeholder="150" {...register("cilindrada")} />
        </Field>
        <Field label="Categoria" error={errors.categoria?.message}>
          <Select {...register("categoria")}>
            <option value="">—</option>
            <option value="urbana">Urbana</option>
            <option value="esportiva">Esportiva</option>
            <option value="trail">Trail / Adventure</option>
            <option value="custom">Custom / Touring</option>
            <option value="scooter">Scooter</option>
          </Select>
        </Field>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="CEP de pernoite" error={errors.cep_pernoite?.message}>
          <Input placeholder="00000-000" {...register("cep_pernoite")} />
        </Field>
        <Field label="Finalidade" error={errors.finalidade?.message}>
          <Select {...register("finalidade")}>
            <option value="">—</option>
            <option value="pessoal">Pessoal / Lazer</option>
            <option value="comercial">Comercial / Delivery</option>
            <option value="app">Uber / App de transporte</option>
            <option value="taxi">Táxi</option>
          </Select>
        </Field>
      </div>

      <div className="flex gap-4">
        <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
          <input type="checkbox" {...register("garagem")} />
          Tem garagem
        </label>
      </div>

      <div className="pt-2 flex justify-between">
        <Button type="button" variant="outline" onClick={onBack}>
          ← Voltar
        </Button>
        <Button type="submit">Próximo →</Button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Step 2 Imóvel
// ---------------------------------------------------------------------------

function Step2Imovel({
  dominios,
  defaultValues,
  onBack,
  onNext,
}: {
  dominios: Dominio[];
  defaultValues?: Step2Data;
  onBack: () => void;
  onNext: (data: Step2Data) => void;
}) {
  const tiposImovel = dominios.filter((d) => d.tipo === "tipo_imovel");
  const tiposConstrucao = dominios.filter((d) => d.tipo === "tipo_construcao");

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<z.infer<typeof step2ImovelSchema>>({
    resolver: zodResolver(step2ImovelSchema),
    defaultValues: defaultValues as z.infer<typeof step2ImovelSchema>,
  });

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-4">
      <Field label="CEP do imóvel" error={errors.cep?.message}>
        <Input placeholder="00000-000" {...register("cep")} />
      </Field>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Tipo de imóvel" error={errors.tipo_imovel?.message}>
          <Select {...register("tipo_imovel")}>
            <option value="">—</option>
            {tiposImovel.map((d) => (
              <option key={d.codigo} value={d.codigo}>
                {d.descricao}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Tipo de construção" error={errors.tipo_construcao?.message}>
          <Select {...register("tipo_construcao")}>
            <option value="">—</option>
            {tiposConstrucao.map((d) => (
              <option key={d.codigo} value={d.codigo}>
                {d.descricao}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Valor do imóvel (R$)" error={errors.valor_imovel?.message}>
          <Input placeholder="300000,00" {...register("valor_imovel")} />
        </Field>
        <Field
          label="Valor do conteúdo (R$)"
          error={errors.valor_conteudo?.message}
        >
          <Input placeholder="0,00 (opcional)" {...register("valor_conteudo")} />
        </Field>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...register("alarme")} />
          Alarme
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...register("cerca_eletrica")} />
          Cerca elétrica
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...register("grades")} />
          Grades
        </label>
      </div>

      <div className="pt-2 flex justify-between">
        <Button type="button" variant="outline" onClick={onBack}>
          ← Voltar
        </Button>
        <Button type="submit">Próximo →</Button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Step 3 — Coberturas
// ---------------------------------------------------------------------------

function Step3({
  ramo,
  dominios,
  defaultValues,
  onBack,
  onNext,
}: {
  ramo: string;
  dominios: Dominio[];
  defaultValues?: Step3Data;
  onBack: () => void;
  onNext: (data: Step3Data) => void;
}) {
  const tipo = ramo === "auto" || ramo === "moto" ? "cobertura_auto" : "cobertura_imovel";
  const coberturas = dominios.filter((d) => d.tipo === tipo);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Step3Data>({
    resolver: zodResolver(step3Schema),
    defaultValues: defaultValues ?? { coberturas: [] },
  });

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-4">
      <p className="text-sm text-gray-600">Selecione as coberturas desejadas:</p>
      <div className="space-y-2">
        {coberturas.map((d) => (
          <label key={d.codigo} className="flex items-center gap-3 text-sm">
            <input
              type="checkbox"
              value={d.codigo}
              {...register("coberturas")}
              className="rounded"
            />
            <span className="font-medium">{d.descricao}</span>
            <span className="text-gray-400 text-xs">({d.codigo})</span>
          </label>
        ))}
      </div>
      {errors.coberturas && (
        <p className="text-xs text-red-600">{errors.coberturas.message}</p>
      )}

      <div className="pt-2 flex justify-between">
        <Button type="button" variant="outline" onClick={onBack}>
          ← Voltar
        </Button>
        <Button type="submit">Próximo →</Button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Step 4 — Vigência + parcelamento
// ---------------------------------------------------------------------------

function Step4({
  dominios,
  defaultValues,
  onBack,
  onNext,
  submitting,
  serverError,
}: {
  dominios: Dominio[];
  defaultValues?: Step4Data;
  onBack: () => void;
  onNext: (data: Step4Data) => void;
  submitting?: boolean;
  serverError?: string | null;
}) {
  const planos = dominios.filter(
    (d) => d.tipo === "plano_pagamento" || d.tipo === "parcelamento",
  );
  const today = new Date().toISOString().slice(0, 10);
  const nextYear = new Date(
    new Date().setFullYear(new Date().getFullYear() + 1),
  )
    .toISOString()
    .slice(0, 10);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Step4Data>({
    resolver: zodResolver(step4Schema),
    defaultValues: defaultValues ?? {
      inicio_vigencia: today,
      fim_vigencia: nextYear,
    },
  });

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-4">
      <Field label="Parcelamento do prêmio" error={errors.plano_pagamento?.message}>
        <Select {...register("plano_pagamento")}>
          <option value="">—</option>
          {planos.length > 0
            ? planos.map((d) => (
                <option key={d.codigo} value={d.codigo}>
                  {d.descricao}
                </option>
              ))
            : [
                ["AVISTA", "À vista"],
                ["2X", "2× sem juros"],
                ["3X", "3× sem juros"],
                ["6X", "6× sem juros"],
                ["10X", "10× sem juros"],
              ].map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
        </Select>
      </Field>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Início da vigência" error={errors.inicio_vigencia?.message}>
          <Input type="date" {...register("inicio_vigencia")} />
        </Field>
        <Field label="Fim da vigência" error={errors.fim_vigencia?.message}>
          <Input type="date" {...register("fim_vigencia")} />
        </Field>
      </div>

      {serverError && (
        <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-400">
          {serverError}
        </div>
      )}

      <div className="pt-2 flex justify-between">
        <Button type="button" variant="outline" onClick={onBack} disabled={submitting}>
          ← Voltar
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? "Enviando…" : "Solicitar cotação →"}
        </Button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Main CotacaoPage
// ---------------------------------------------------------------------------

const STEP_LABELS = [
  "Proponente",
  "Dados do risco",
  "Coberturas",
  "Vigência",
  "Resultado",
];


export function CotacaoPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [dominios, setDominios] = useState<Dominio[]>([]);
  const [ramo, setRamo] = useState<string>(() => {
    return loadRascunho()?.ramo ?? "auto";
  });
  const [step, setStep] = useState<number>(() => {
    return loadRascunho()?.step ?? 1;
  });
  const [step1Data, setStep1Data] = useState<Step1Data | undefined>(undefined);
  const [step2Data, setStep2Data] = useState<Step2Data | undefined>(
    () => loadRascunho()?.step2,
  );
  const [step3Data, setStep3Data] = useState<Step3Data | undefined>(
    () => loadRascunho()?.step3,
  );
  const [step4Data, setStep4Data] = useState<Step4Data | undefined>(
    () => loadRascunho()?.step4,
  );
  const [clienteId, setClienteId] = useState<string | undefined>(
    () => loadRascunho()?.clienteId,
  );

  // Polling state
  const [cotacaoId, setCotacaoId] = useState<string | null>(null);
  const [cotacao, setCotacao] = useState<Cotacao | null>(null);
  const [polling, setPolling] = useState(false);
  const [pollingSeconds, setPollingSeconds] = useState(0);
  const [pollCancelled, setPollCancelled] = useState(false);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollingSecRef = useRef(0);

  // Criação de cotação
  const [criando, setCriando] = useState(false);
  const [cotacaoErrMsg, setCotacaoErrMsg] = useState<string | null>(null);

  // Comparativo + proposta state
  const [itensComparativo, setItensComparativo] = useState<ItemComparativo[]>([]);
  const [proposta, setProposta] = useState<Proposta | null>(null);
  const [showTransmitir, setShowTransmitir] = useState(false);
  const [transmitirCia, setTransmitirCia] = useState("fake");

  // Recotar error
  const [recotarError, setRecotarError] = useState<string | null>(null);

  // Cancel confirmation
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  const recotar = searchParams.get("recotar");
  const clienteParam = searchParams.get("cliente");

  // Carrega domínios
  useEffect(() => {
    api.dominios.list().then(setDominios).catch(() => {});
  }, []);

  // Se cliente param, começa nova cotação pré-vinculada (descarta rascunho anterior)
  useEffect(() => {
    if (!clienteParam) return;
    clearRascunho();
    setStep(1);
    setStep2Data(undefined);
    setStep3Data(undefined);
    setStep4Data(undefined);
    setClienteId(clienteParam);
  }, [clienteParam]);

  // Se recotar param, pré-preenche dados do risco
  useEffect(() => {
    if (!recotar) return;
    let cancelled = false;
    api.cotacoes.get(recotar).then((c) => {
      if (cancelled) return;
      setRamo(c.ramo);
      setStep2Data(c.dados_risco as Record<string, unknown>);
      if (c.cliente_id) setClienteId(c.cliente_id);
    }).catch(() => {
      if (!cancelled) setRecotarError("Não foi possível carregar os dados da cotação anterior.");
    });
    return () => { cancelled = true; };
  }, [recotar]);

  // Busca comparativo após polling encerrar com status final
  useEffect(() => {
    if (!cotacaoId || !cotacao || polling) return;
    if (cotacao.status !== "sucesso" && cotacao.status !== "restricao") return;
    let cancelled = false;
    api.cotacoes
      .comparativo(cotacaoId)
      .then((items) => { if (!cancelled) setItensComparativo(items); })
      .catch(() => { if (!cancelled) setItensComparativo([]); });
    return () => { cancelled = true; };
  }, [cotacaoId, cotacao, polling]);

  const persistRascunho = useCallback(
    (patch: Partial<Rascunho>) => {
      const current = loadRascunho() ?? { ramo, step };
      saveRascunho({ ...current, ...patch });
    },
    [ramo, step],
  );

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearTimeout(pollRef.current);
      pollRef.current = null;
    }
    setPolling(false);
  }, []);

  // Cleanup do polling ao desmontar o componente
  useEffect(() => () => { if (pollRef.current) clearTimeout(pollRef.current); }, []);

  const startPolling = useCallback(
    (id: string) => {
      stopPolling();
      const start = Date.now();
      pollingSecRef.current = 0;
      setPollingSeconds(0);
      setPolling(true);
      setPollCancelled(false);

      const tick = async () => {
        if (Date.now() - start > POLL_TIMEOUT_MS) {
          stopPolling();
          return;
        }
        pollingSecRef.current += POLL_INTERVAL_MS / 1000;
        setPollingSeconds(Math.floor(pollingSecRef.current));

        try {
          const c = await api.cotacoes.get(id);
          setCotacao(c);
          if (c.status !== "aguardando" && c.status !== "processando") {
            stopPolling();
            clearRascunho();
            return;
          }
        } catch {
          // erro de rede — mantém polling
        }

        pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);
      };

      pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);
    },
    [stopPolling],
  );

  const handleRamoChange = (r: string) => {
    setRamo(r);
    persistRascunho({ ramo: r });
  };

  const handleStep1 = (data: Step1Data, cliente: Cliente | null) => {
    setStep1Data(data);
    setClienteId(cliente?.id);
    setStep(2);
    persistRascunho({ step: 2, clienteId: cliente?.id });
  };

  const handleStep2 = (data: Step2Data) => {
    setStep2Data(data);
    setStep(3);
    persistRascunho({ step2: data, step: 3 });
  };

  const handleStep3 = (data: Step3Data) => {
    setStep3Data(data);
    setStep(4);
    persistRascunho({ step3: data, step: 4 });
  };

  const handleStep4 = async (data: Step4Data) => {
    setStep4Data(data);
    setCotacaoErrMsg(null);
    persistRascunho({ step4: data });

    // Remove UI-only flag e campos do condutor quando não há condutor diferente
    const step2Limpo = { ...(step2Data ?? {}) };
    if (!step2Limpo.condutor_diferente) {
      delete step2Limpo.condutor_diferente;
      delete step2Limpo.condutor_cpf;
      delete step2Limpo.condutor_nome;
      delete step2Limpo.condutor_sexo;
      delete step2Limpo.condutor_nascimento;
      delete step2Limpo.condutor_parentesco;
    } else {
      delete step2Limpo.condutor_diferente;
    }

    const dados: Record<string, unknown> = {
      ...step2Limpo,
      coberturas: step3Data?.coberturas ?? [],
      plano_pagamento: data.plano_pagamento,
      inicio_vigencia: data.inicio_vigencia,
      fim_vigencia: data.fim_vigencia,
      ...(step1Data
        ? {
            proponente: {
              cpf: step1Data.cpf,
              telefone: step1Data.telefone,
              nome: step1Data.nome,
              email: step1Data.email,
              estado_civil: step1Data.estado_civil,
              profissao: step1Data.profissao,
              data_nascimento: step1Data.data_nascimento,
              sexo: step1Data.sexo,
            },
          }
        : {}),
    };

    setCriando(true);
    try {
      const created = await api.cotacoes.create({
        ramo,
        dados,
        cliente_id: clienteId,
        versao_anterior_id: recotar ?? undefined,
      });
      setCotacaoId(created.id);
      setStep(5);
      persistRascunho({ step: 5 });
      startPolling(created.id);
    } catch (err) {
      setCotacaoErrMsg(
        err instanceof ApiError ? err.message : "Erro ao solicitar cotação. Tente novamente."
      );
    } finally {
      setCriando(false);
    }
  };

  const handleRecotar = () => {
    if (!cotacaoId) return;
    navigate(`/cotacao?recotar=${cotacaoId}`);
  };

  const handleCancel = () => {
    setPollCancelled(true);
    stopPolling();
    clearRascunho();
  };

  const handleNewCotacao = () => {
    if (step > 1) { setShowCancelConfirm(true); return; }
    clearRascunho();
    setStep(1);
    setStep1Data(undefined);
    setStep2Data(undefined);
    setStep3Data(undefined);
    setStep4Data(undefined);
    setCotacaoId(null);
    setCotacao(null);
    setItensComparativo([]);
    setProposta(null);
    setShowTransmitir(false);
    navigate("/cotacao");
  };

  const confirmDiscard = () => {
    setShowCancelConfirm(false);
    clearRascunho();
    setStep(1);
    setStep1Data(undefined);
    setStep2Data(undefined);
    setStep3Data(undefined);
    setStep4Data(undefined);
    setCotacaoId(null);
    setCotacao(null);
    setItensComparativo([]);
    setProposta(null);
    setShowTransmitir(false);
    navigate("/cotacao");
  };

  return (
    <div className="max-w-2xl mx-auto">
      {showCancelConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={(e) => { if (e.target === e.currentTarget) setShowCancelConfirm(false); }}
        >
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-xl w-full max-w-sm mx-4 p-6 space-y-4">
            <h2 className="text-base font-semibold text-gray-900 dark:text-white">Descartar cotação?</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              O rascunho atual será perdido. Deseja continuar?
            </p>
            <div className="flex gap-2 justify-end">
              <Button type="button" variant="outline" size="sm" onClick={() => setShowCancelConfirm(false)}>
                Continuar editando
              </Button>
              <Button type="button" size="sm" onClick={confirmDiscard}
                className="bg-red-600 hover:bg-red-700 text-white border-red-600">
                Descartar
              </Button>
            </div>
          </div>
        </div>
      )}

      {recotarError && (
        <div className="mb-4 text-sm text-yellow-800 dark:text-yellow-300 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-700 rounded px-4 py-3">
          {recotarError}
        </div>
      )}

      {/* Seletor de ramo — só no passo 1 */}
      {step === 1 && (
        <div className="mb-6 flex gap-3">
          {(["auto", "moto", "imovel"] as const).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => handleRamoChange(r)}
              className={`px-4 py-2 rounded text-sm font-medium border transition-colors ${
                ramo === r
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 border-gray-300 dark:border-gray-600 hover:border-blue-400"
              }`}
            >
              {r === "auto" ? "Auto" : r === "moto" ? "Moto" : "Imóvel"}
            </button>
          ))}
        </div>
      )}

      {/* Barra de progresso */}
      <div className="mb-6">
        <div className="flex items-center gap-1 mb-2">
          {STEP_LABELS.map((_label, i) => {
            const s = i + 1;
            return (
              <div key={s} className="flex items-center gap-1 flex-1">
                <div
                  className={`h-1.5 flex-1 rounded-full transition-colors ${
                    s <= step ? "bg-blue-500" : "bg-gray-200 dark:bg-gray-600"
                  }`}
                />
              </div>
            );
          })}
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Passo {step} de 5 — {STEP_LABELS[step - 1]}
        </p>
      </div>

      {/* Steps */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        {step === 1 && (
          <Step1
            dominios={dominios}
            defaultValues={step1Data}
            onNext={handleStep1}
          />
        )}

        {step === 2 && ramo === "auto" && (
          <Step2Auto
            defaultValues={step2Data}
            onBack={() => setStep(1)}
            onNext={handleStep2}
          />
        )}

        {step === 2 && ramo === "moto" && (
          <Step2Moto
            defaultValues={step2Data}
            onBack={() => setStep(1)}
            onNext={handleStep2}
          />
        )}

        {step === 2 && ramo === "imovel" && (
          <Step2Imovel
            dominios={dominios}
            defaultValues={step2Data}
            onBack={() => setStep(1)}
            onNext={handleStep2}
          />
        )}

        {step === 3 && (
          <Step3
            ramo={ramo}
            dominios={dominios}
            defaultValues={step3Data}
            onBack={() => setStep(2)}
            onNext={handleStep3}
          />
        )}

        {step === 4 && (
          <Step4
            dominios={dominios}
            defaultValues={step4Data}
            onBack={() => setStep(3)}
            onNext={handleStep4}
            submitting={criando}
            serverError={cotacaoErrMsg}
          />
        )}

        {step === 5 && (
          <div className="space-y-4">
            {polling && !pollCancelled && (
              <LoadingPanel seconds={pollingSeconds} onCancel={handleCancel} />
            )}

            {pollCancelled && (
              <div className="text-sm text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-gray-700/50 rounded p-4">
                Consulta cancelada.{" "}
                <button
                  type="button"
                  className="text-blue-600 dark:text-blue-400 underline"
                  onClick={() => {
                    if (cotacaoId) startPolling(cotacaoId);
                  }}
                >
                  Retomar
                </button>
              </div>
            )}

            {cotacao && (
              <ComparativoInline
                cotacao={cotacao}
                cotacaoId={cotacaoId!}
                itens={itensComparativo}
                proposta={proposta}
                onEmitir={(cia) => { setTransmitirCia(cia); setShowTransmitir(true); }}
                onRecotar={handleRecotar}
              />
            )}

            <div className="pt-2 flex justify-between">
              <Button variant="outline" onClick={() => setStep(4)}>
                ← Voltar
              </Button>
              <Button variant="ghost" onClick={handleNewCotacao}>
                Nova cotação
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Modal de transmissão — fora do card para cobrir tela toda */}
      {showTransmitir && cotacaoId && (
        <TransmitirModal
          cotacaoId={cotacaoId}
          cia={transmitirCia}
          vigenciaInicio={step4Data?.inicio_vigencia}
          onClose={() => setShowTransmitir(false)}
          onSuccess={(p) => {
            setProposta(p);
            setShowTransmitir(false);
          }}
        />
      )}
    </div>
  );
}
