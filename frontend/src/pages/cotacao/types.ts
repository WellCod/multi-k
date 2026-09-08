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
  sexo: z.enum(["M", "F", ""]).optional(),
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
  condutor_sexo: z.enum(["M", "F", ""]).optional(),
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
  cilindrada: z
    .string()
    .transform(Number)
    .pipe(z.number().int().min(50).max(2500)),
  categoria: z.string().min(1, "Obrigatório"),
  finalidade: z.string().min(1, "Obrigatório"),
  garagem: z.boolean().optional(),
});

export const step2ImovelSchema = z.object({
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

export const step3Schema = z.object({
  coberturas: z.array(z.string()).min(1, "Selecione ao menos uma cobertura"),
});

export const step4Schema = z
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

export type Step1Data = z.infer<typeof step1Schema>;
export type Step2Data = Record<string, unknown>;
export type Step3Data = z.infer<typeof step3Schema>;
export type Step4Data = z.infer<typeof step4Schema>;
