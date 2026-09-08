import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { type Dominio } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { step4Schema, type Step4Data } from "./types";
import { Field } from "./shared";

export function Step4({
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
