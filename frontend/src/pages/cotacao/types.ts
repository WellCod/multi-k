import { z } from "zod";
import { stripCPF } from "@/lib/utils";

export const step1Schema = z.object({
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
  ja_segurado: z.boolean().optional().default(false),
  bonus_anterior: z.coerce.number().int().min(0).max(10).optional().default(0),
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

const moneyInput = z.string().trim()
  .transform(value => value.includes(",") ? value.replace(/\./g, "").replace(",", ".") : value)
  .refine(value => /^\d+(?:\.\d{1,2})?$/.test(value), "Informe um valor com até duas casas decimais");

export const step2ImovelSchema = z.object({
  cep: z
    .string()
    .transform((v) => v.replace(/\D/g, ""))
    .pipe(z.string().length(8, "CEP deve ter 8 dígitos")),
  tipo_imovel: z.string().min(1, "Obrigatório"),
  tipo_construcao: z.string().min(1, "Obrigatório"),
  valor_imovel: moneyInput.refine(value => /[1-9]/.test(value), "Valor do imóvel deve ser maior que zero"),
  valor_conteudo: z.string().optional().transform(value => value || "0").pipe(moneyInput),
  alarme: z.boolean().optional().default(false),
  cerca_eletrica: z.boolean().optional().default(false),
  grades: z.boolean().optional().default(false),
});

export const step3Schema = z.object({
  coberturas: z.array(z.string()).min(1, "Selecione ao menos uma cobertura"),
});

const autoObjectFields = { cep_pernoite: true, codigo_fipe: true, placa: true, marca: true, modelo: true, ano_modelo: true, combustivel: true, valor_fipe: true } as const;
const motoObjectFields = { ...autoObjectFields, cilindrada: true, categoria: true } as const;
const imovelObjectFields = { cep: true, tipo_imovel: true, tipo_construcao: true, valor_imovel: true, valor_conteudo: true } as const;

export const riskStepSchemas = {
  auto: { object: step2AutoSchema.pick(autoObjectFields), profile: step2AutoSchema.omit(autoObjectFields) },
  moto: { object: step2MotoSchema.pick(motoObjectFields), profile: step2MotoSchema.omit(motoObjectFields) },
  imovel: { object: step2ImovelSchema.pick(imovelObjectFields), profile: step2ImovelSchema.omit(imovelObjectFields) },
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
