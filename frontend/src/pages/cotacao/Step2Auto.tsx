import { useId } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import FipeSelector, { type FipeResult } from "@/components/FipeSelector";
import { step2AutoSchema, type Step2Data } from "./types";
import { Field } from "./shared";

export function Step2Auto({
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
