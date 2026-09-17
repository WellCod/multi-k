import { z } from "zod";
import { stripCPF } from "@/lib/utils";

/** Data local em YYYY-MM-DD. toISOString() usaria UTC e erraria o dia. */
const isoLocal = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Mesmos limites no schema e nos atributos do input, para o navegador barrar
 *  no próprio seletor em vez de só reclamar ao enviar. */
export function limitesNascimento() {
  const hoje = new Date();
  const cem = new Date(hoje.getFullYear() - 100, hoje.getMonth(), hoje.getDate());
  return { min: isoLocal(cem), max: isoLocal(hoje) };
}

export const step1Schema = z.object({
  nome: z.string().min(2, "Nome muito curto"),
  // J2 §4: o segurado pode ser PF (CPF) ou PJ (CNPJ).
  cpf: z
    .string()
    .transform(stripCPF)
    .pipe(
      z.string().refine(
        (v) => v.length === 11 || v.length === 14,
        "Informe um CPF (11 dígitos) ou CNPJ (14 dígitos)"
      )
    ),
  cep: z
    .string()
    .transform((v) => v.replace(/\D/g, ""))
    .pipe(z.string().length(8, "CEP deve ter 8 dígitos").or(z.literal("")))
    .optional(),
  nome_social: z.string().trim().optional(),
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
  sexo: z.string().optional(),
  estado_civil: z.string().optional(),
  profissao: z.string().optional(),
});

export const step2AutoSchema = z.object({
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
  leilao: z.boolean().optional().default(false),
  ja_segurado: z.boolean().optional().default(false),
  bonus_anterior: z.coerce.number().int().min(0).max(10).optional().default(0),
  tipo_negocio: z.enum(["novo", "renovacao"]).optional().default("novo"),
  ci_code: z.string().trim().optional(),
  // Select vazio é "não informado", não zero.
  insurer_code: z.preprocess(
    (value) => (value === "" || value === null ? undefined : value),
    z.coerce.number().int().positive().optional()
  ),
  condutor_diferente: z.boolean().optional().default(false),
  condutor_cpf: z
    .string()
    .transform((v) => v.replace(/\D/g, ""))
    .pipe(z.string().length(11, "CPF deve ter 11 dígitos").or(z.literal("")))
    .optional(),
  condutor_nome: z.string().optional(),
  condutor_sexo: z.string().optional(),
  condutor_nascimento: z.string().optional(),
  condutor_parentesco: z.string().optional(),
});

export const step2MotoSchema = z.object({
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
  cilindrada: z.coerce.number().int().min(50).max(2500),
  categoria: z.string().min(1, "Obrigatório"),
  finalidade: z.string().min(1, "Obrigatório"),
  garagem: z.boolean().optional(),
});

export const step3Schema = z.object({
  coberturas: z.array(z.string()).min(1, "Selecione ao menos uma cobertura"),
});

const autoObjectFields = { cep_pernoite: true, codigo_fipe: true, placa: true, marca: true, modelo: true, ano_modelo: true, combustivel: true, valor_fipe: true } as const;
const motoObjectFields = { ...autoObjectFields, cilindrada: true, categoria: true } as const;

// O CI é exigido pela classe de bônus, não pela natureza do negócio: bônus
// transferido em negócio novo também precisa (Justos, 17/09/2026).
const autoProfileSchema = step2AutoSchema.omit(autoObjectFields).superRefine((data, ctx) => {
  if ((data.bonus_anterior ?? 0) > 0 && !data.ci_code) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Bônus maior que zero exige o código CI da apólice anterior", path: ["ci_code"] });
  }
});

export const riskStepSchemas = {
  auto: { object: step2AutoSchema.pick(autoObjectFields), profile: autoProfileSchema },
  moto: { object: step2MotoSchema.pick(motoObjectFields), profile: step2MotoSchema.omit(motoObjectFields) },
};

const calendarDate = z.string().refine(value => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T12:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}, "Informe uma data válida");

export const step4Schema = z
  .object({
    coberturas: step3Schema.shape.coberturas,
    plano_pagamento: z.string().min(1, "Selecione o plano"),
    inicio_vigencia: calendarDate,
    fim_vigencia: calendarDate,
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

export type Step1Data = z.infer<typeof step1Schema>;
export type Step2Data = Record<string, unknown>;
export type Step3Data = z.infer<typeof step3Schema>;
export type Step4Data = z.infer<typeof step4Schema>;
