import { useCallback, useEffect, useRef, useState } from "react";
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
import { stripCPF } from "@/lib/utils";

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
  data_nascimento: z.string().optional(),
  sexo: z.enum(["M", "F", ""]).optional(),
  estado_civil: z.string().optional(),
  profissao: z.string().optional(),
});

const step2AutoSchema = z.object({
  cep_pernoite: z
    .string()
    .transform((v) => v.replace(/\D/g, ""))
    .pipe(z.string().length(8, "CEP deve ter 8 dígitos")),
  marca: z.string().min(1, "Obrigatório"),
  modelo: z.string().min(1, "Obrigatório"),
  ano_fabricacao: z
    .string()
    .transform(Number)
    .pipe(z.number().int().min(1900).max(2100)),
  ano_modelo: z
    .string()
    .transform(Number)
    .pipe(z.number().int().min(1900).max(2100)),
  combustivel: z.string().min(1, "Obrigatório"),
  finalidade: z.string().min(1, "Obrigatório"),
  blindado: z.boolean().optional(),
  garagem: z.boolean().optional(),
});

const step2ResidenciaSchema = z.object({
  cep: z
    .string()
    .transform((v) => v.replace(/\D/g, ""))
    .pipe(z.string().length(8, "CEP deve ter 8 dígitos")),
  tipo_imovel: z.string().min(1, "Obrigatório"),
  tipo_construcao: z.string().min(1, "Obrigatório"),
  valor_imovel: z
    .string()
    .transform((v) => v.replace(/\D/g, ".").replace(",", "."))
    .pipe(z.string()),
});

const step3Schema = z.object({
  coberturas: z.array(z.string()).min(1, "Selecione ao menos uma cobertura"),
});

const step4Schema = z.object({
  plano_pagamento: z.string().min(1, "Selecione o plano"),
  inicio_vigencia: z.string().min(1, "Data de início obrigatória"),
  fim_vigencia: z.string().min(1, "Data de fim obrigatória"),
});

type Step1Data = z.infer<typeof step1Schema>;
type Step2Data = Record<string, unknown>;
type Step3Data = z.infer<typeof step3Schema>;
type Step4Data = z.infer<typeof step4Schema>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtReal(v: string | null) {
  if (!v) return "—";
  return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

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
    <div className="rounded-lg border border-gray-200 bg-white p-6 text-center space-y-4">
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
        <span className="text-sm font-medium text-gray-700">
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
  vigenciaInicio?: string;
  onClose: () => void;
  onSuccess: (p: Proposta) => void;
}

function TransmitirModal({
  cotacaoId,
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
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    try {
      const proposta = await api.cotacoes.transmitir(cotacaoId, {
        plano_pagamento: plano,
        n_parcelas: parcelas,
        comissao_pct: comissao,
        inicio_vigencia: vigencia,
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
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <h2 className="text-lg font-semibold mb-4">Transmitir proposta</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Parcelamento</label>
            <select
              className="w-full border rounded px-3 py-2 text-sm"
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
            <label className="block text-sm font-medium mb-1">Comissão (%)</label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              max="100"
              className="w-full border rounded px-3 py-2 text-sm"
              value={Number(comissao) * 100}
              onChange={(e) =>
                setComissao((Number(e.target.value) / 100).toFixed(4))
              }
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Início vigência</label>
            <input
              type="date"
              className="w-full border rounded px-3 py-2 text-sm"
              value={vigencia}
              onChange={(e) => setVigencia(e.target.value)}
            />
          </div>
          {err && <p className="text-red-600 text-sm">{err}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" disabled={loading}>
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
    sucesso: "bg-green-100 text-green-800",
    restricao: "bg-yellow-100 text-yellow-800",
    erro: "bg-red-100 text-red-800",
    processando: "bg-blue-100 text-blue-800",
    aguardando: "bg-gray-100 text-gray-600",
  };
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${map[status] ?? "bg-gray-100 text-gray-600"}`}
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
  onEmitir: () => void;
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
      <div className="bg-green-50 border border-green-200 rounded-lg p-5 space-y-1">
        <p className="font-semibold text-green-800">Proposta transmitida com sucesso!</p>
        <p className="text-sm text-green-700">
          Protocolo:{" "}
          <span className="font-mono font-semibold">{proposta.protocolo}</span>
        </p>
        <p className="text-sm text-green-700">
          {proposta.n_parcelas}× de {fmtReal(proposta.valor_parcela)}
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
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <h3 className="font-medium text-red-800 mb-2">Cotação não realizada</h3>
        <p className="text-sm text-red-700">
          {cotacao.mensagens[0] ??
            "A seguradora não pôde calcular o prêmio para este risco."}
        </p>
        <Button variant="outline" size="sm" className="mt-4" onClick={onRecotar}>
          Tentar novamente
        </Button>
      </div>
    );
  }

  const podeEmitir =
    cotacao.status === "sucesso" || cotacao.status === "restricao";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-gray-900">
          Resultados —{" "}
          {cotacao.ramo.charAt(0).toUpperCase() + cotacao.ramo.slice(1)}
        </h3>
        <StatusBadge status={cotacao.status} />
      </div>

      {cotacao.necessita_vistoria && (
        <p className="text-sm font-medium text-yellow-700 bg-yellow-50 border border-yellow-200 rounded px-3 py-2">
          Vistoria prévia obrigatória — prazo de emissão estendido.
        </p>
      )}

      {itens.length === 0 ? (
        <p className="text-sm text-gray-500 py-4">Processando resultados…</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 border-b text-left">
                <th className="px-4 py-2 font-medium">Seguradora</th>
                <th className="px-4 py-2 font-medium">Prêmio total</th>
                <th className="px-4 py-2 font-medium">Restrições</th>
                <th className="px-4 py-2 font-medium">Vistoria</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {itens.map((item, i) => (
                <tr key={i} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-3 font-semibold uppercase">{item.cia}</td>
                  <td className="px-4 py-3 font-mono">{fmtReal(item.premio_total)}</td>
                  <td className="px-4 py-3">
                    {item.restricoes.length === 0 ? (
                      <span className="text-gray-400">—</span>
                    ) : (
                      item.restricoes.map((r) => (
                        <span key={r.codigo} className="block text-xs text-yellow-700">
                          {r.codigo}: {r.mensagem}
                        </span>
                      ))
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {item.necessita_vistoria ? (
                      <span className="text-yellow-700 text-xs font-medium">Sim</span>
                    ) : (
                      <span className="text-gray-400 text-xs">Não</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={item.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center gap-3 flex-wrap">
        <a
          href={api.cotacoes.comparativoPdfUrl(cotacaoId)}
          target="_blank"
          rel="noreferrer"
          className="px-4 py-2 border rounded text-sm hover:bg-gray-50 transition-colors"
        >
          Baixar PDF
        </a>
        {podeEmitir && (
          <Button onClick={onEmitir}>Transmitir proposta</Button>
        )}
        <Button variant="outline" onClick={onRecotar}>
          Recotar
        </Button>
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
    } catch {
      // not found — proceed with blank form
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
        <p className="text-xs text-green-700 bg-green-50 rounded px-2 py-1">
          Cliente encontrado: {foundCliente.nome}
        </p>
      )}

      <Field label="Nome completo" error={errors.nome?.message}>
        <Input {...register("nome")} />
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field label="E-mail" error={errors.email?.message}>
          <Input type="email" {...register("email")} />
        </Field>
        <Field label="Telefone">
          <Input {...register("telefone")} />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Data de nascimento">
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

      <div className="grid grid-cols-2 gap-4">
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
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<z.infer<typeof step2AutoSchema>>({
    resolver: zodResolver(step2AutoSchema),
    defaultValues: defaultValues as z.infer<typeof step2AutoSchema>,
  });

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <Field label="Marca" error={errors.marca?.message}>
          <Input {...register("marca")} />
        </Field>
        <Field label="Modelo" error={errors.modelo?.message}>
          <Input {...register("modelo")} />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Ano fabricação" error={errors.ano_fabricacao?.message}>
          <Input type="number" {...register("ano_fabricacao")} />
        </Field>
        <Field label="Ano modelo" error={errors.ano_modelo?.message}>
          <Input type="number" {...register("ano_modelo")} />
        </Field>
      </div>

      <Field label="CEP de pernoite" error={errors.cep_pernoite?.message}>
        <Input placeholder="00000-000" {...register("cep_pernoite")} />
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Combustível" error={errors.combustivel?.message}>
          <Select {...register("combustivel")}>
            <option value="">—</option>
            {["gasolina", "etanol", "flex", "diesel", "eletrico", "gnv"].map(
              (c) => (
                <option key={c} value={c}>
                  {c.charAt(0).toUpperCase() + c.slice(1)}
                </option>
              ),
            )}
          </Select>
        </Field>
        <Field label="Finalidade" error={errors.finalidade?.message}>
          <Select {...register("finalidade")}>
            <option value="">—</option>
            <option value="pessoal">Pessoal</option>
            <option value="comercial">Comercial</option>
          </Select>
        </Field>
      </div>

      <div className="flex gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...register("blindado")} />
          Blindado
        </label>
        <label className="flex items-center gap-2 text-sm">
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
// Step 2 Residência
// ---------------------------------------------------------------------------

function Step2Residencia({
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
  } = useForm<z.infer<typeof step2ResidenciaSchema>>({
    resolver: zodResolver(step2ResidenciaSchema),
    defaultValues: defaultValues as z.infer<typeof step2ResidenciaSchema>,
  });

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-4">
      <Field label="CEP do imóvel" error={errors.cep?.message}>
        <Input placeholder="00000-000" {...register("cep")} />
      </Field>

      <div className="grid grid-cols-2 gap-4">
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

      <Field label="Valor do imóvel (R$)" error={errors.valor_imovel?.message}>
        <Input placeholder="300000,00" {...register("valor_imovel")} />
      </Field>

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
  const tipo = ramo === "auto" ? "cobertura_auto" : "cobertura_residencia";
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
            <span className="font-medium">{d.codigo}</span>
            <span className="text-gray-500">— {d.descricao}</span>
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
}: {
  dominios: Dominio[];
  defaultValues?: Step4Data;
  onBack: () => void;
  onNext: (data: Step4Data) => void;
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

      <div className="grid grid-cols-2 gap-4">
        <Field label="Início da vigência" error={errors.inicio_vigencia?.message}>
          <Input type="date" {...register("inicio_vigencia")} />
        </Field>
        <Field label="Fim da vigência" error={errors.fim_vigencia?.message}>
          <Input type="date" {...register("fim_vigencia")} />
        </Field>
      </div>

      <div className="pt-2 flex justify-between">
        <Button type="button" variant="outline" onClick={onBack}>
          ← Voltar
        </Button>
        <Button type="submit">Solicitar cotação →</Button>
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

const MOCK_COMPARATIVO: ItemComparativo[] = [
  {
    cia: "Yelum",
    cotacao_id_cia: "YLM-2026-001482",
    premio_total: "2340.00",
    restricoes: [],
    mensagens: [],
    necessita_vistoria: false,
    status: "sucesso",
  },
  {
    cia: "Porto Seguro",
    cotacao_id_cia: "PRT-2026-008821",
    premio_total: "2190.50",
    restricoes: [{ codigo: "R02", mensagem: "Veículo com mais de 10 anos exige vistoria" }],
    mensagens: [],
    necessita_vistoria: true,
    status: "restricao",
  },
  {
    cia: "Tokio Marine",
    cotacao_id_cia: null,
    premio_total: null,
    restricoes: [],
    mensagens: ["Proposta não aceita para este perfil"],
    necessita_vistoria: false,
    status: "erro",
  },
  {
    cia: "Bradesco Seguros",
    cotacao_id_cia: null,
    premio_total: null,
    restricoes: [],
    mensagens: [],
    necessita_vistoria: false,
    status: "processando",
  },
  {
    cia: "Azul Seguros",
    cotacao_id_cia: null,
    premio_total: null,
    restricoes: [],
    mensagens: [],
    necessita_vistoria: false,
    status: "aguardando",
  },
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

  // Comparativo + proposta state
  const [itensComparativo, setItensComparativo] = useState<ItemComparativo[]>([]);
  const [proposta, setProposta] = useState<Proposta | null>(null);
  const [showTransmitir, setShowTransmitir] = useState(false);

  const recotar = searchParams.get("recotar");

  // Carrega domínios
  useEffect(() => {
    api.dominios.list().then(setDominios).catch(() => {});
  }, []);

  // Se recotar param, pré-preenche dados do risco
  useEffect(() => {
    if (!recotar) return;
    let cancelled = false;
    api.cotacoes.get(recotar).then((c) => {
      if (cancelled) return;
      setRamo(c.ramo);
      setStep2Data(c.dados_risco as Record<string, unknown>);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [recotar]);

  // Busca comparativo após polling encerrar com status final
  useEffect(() => {
    if (!cotacaoId || !cotacao || polling) return;
    if (cotacao.status !== "sucesso" && cotacao.status !== "restricao") return;
    let cancelled = false;
    api.cotacoes
      .comparativo(cotacaoId)
      .then((items) => {
        if (cancelled) return;
        const apenasAdapterFake =
          items.length === 0 || items.every((i) => i.cia.toLowerCase() === "fake");
        setItensComparativo(apenasAdapterFake ? MOCK_COMPARATIVO : items);
      })
      .catch(() => { if (!cancelled) setItensComparativo(MOCK_COMPARATIVO); });
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
    setStep(5);
    persistRascunho({ step4: data, step: 5 });

    const dados: Record<string, unknown> = {
      ...(step2Data ?? {}),
      coberturas: step3Data?.coberturas ?? [],
      plano_pagamento: data.plano_pagamento,
      inicio_vigencia: data.inicio_vigencia,
      fim_vigencia: data.fim_vigencia,
      ...(step1Data
        ? {
            proponente: {
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

    try {
      const created = await api.cotacoes.create({
        ramo,
        dados,
        cliente_id: clienteId,
        versao_anterior_id: recotar ?? undefined,
      });
      setCotacaoId(created.id);
      startPolling(created.id);
    } catch (err) {
      if (err instanceof ApiError) {
        alert(err.message);
      }
    }
  };

  const handleRecotar = async () => {
    if (!cotacaoId) return;
    try {
      const created = await api.cotacoes.recotar(cotacaoId);
      setCotacaoId(created.id);
      setCotacao(null);
      setItensComparativo([]);
      navigate(`/cotacao?recotar=${cotacaoId}`);
      setStep(1);
    } catch {
      // ignore
    }
  };

  const handleCancel = () => {
    setPollCancelled(true);
    stopPolling();
  };

  const handleNewCotacao = () => {
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
      {/* Seletor de ramo — só no passo 1 */}
      {step === 1 && (
        <div className="mb-6 flex gap-3">
          {["auto", "residencia"].map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => handleRamoChange(r)}
              className={`px-4 py-2 rounded text-sm font-medium border transition-colors ${
                ramo === r
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-gray-700 border-gray-300 hover:border-blue-400"
              }`}
            >
              {r === "auto" ? "Auto" : "Residência"}
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
                    s <= step ? "bg-blue-500" : "bg-gray-200"
                  }`}
                />
              </div>
            );
          })}
        </div>
        <p className="text-xs text-gray-500">
          Passo {step} de 5 — {STEP_LABELS[step - 1]}
        </p>
      </div>

      {/* Steps */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
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

        {step === 2 && ramo === "residencia" && (
          <Step2Residencia
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
          />
        )}

        {step === 5 && (
          <div className="space-y-4">
            {polling && !pollCancelled && (
              <LoadingPanel seconds={pollingSeconds} onCancel={handleCancel} />
            )}

            {pollCancelled && (
              <div className="text-sm text-gray-600 bg-gray-50 rounded p-4">
                Consulta cancelada.{" "}
                <button
                  type="button"
                  className="text-blue-600 underline"
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
                onEmitir={() => setShowTransmitir(true)}
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
