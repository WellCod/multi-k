import { DomainOptions } from "@/components/DomainOptions";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import FipeSelector, { type FipeResult } from "@/components/FipeSelector";
import { step2MotoSchema, riskStepSchemas, type Step2Data } from "./types";
import { Field } from "./shared";

export function Step2Moto({
  stage = "object",
  defaultValues,
  onBack,
  onNext,
}: {
  stage?: "object" | "profile";
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
    resolver: zodResolver(riskStepSchemas.moto[stage]),
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
      {stage === "object" && <>
      <FipeSelector
        tipo="motos"
        savedVehicle={defaultValues}
        onInvalidate={() => {
          for (const field of ["codigo_fipe", "marca", "modelo", "ano_modelo", "combustivel", "valor_fipe"] as const) setValue(field, "", { shouldValidate: true });
        }}
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
            <DomainOptions tipo="categoria_moto" />
          </Select>
        </Field>
      </div>

        <Field label="CEP de pernoite" error={errors.cep_pernoite?.message}>
          <Input placeholder="00000-000" {...register("cep_pernoite")} />
        </Field>
      </>}
      {stage === "profile" && <>
        <Field label="Finalidade" error={errors.finalidade?.message}>
          <Select {...register("finalidade")}>
            <option value="">—</option>
            <DomainOptions tipo="finalidade_moto" />
          </Select>
        </Field>

      <div className="flex gap-4">
        <label className="flex items-center gap-2 text-sm text-ink ">
          <input type="checkbox" {...register("garagem")} />
          Tem garagem
        </label>
      </div>

      </>}
      <div className="pt-2 flex justify-between">
        <Button type="button" variant="outline" onClick={onBack}>
          ← Voltar
        </Button>
        <Button type="submit">Próximo →</Button>
      </div>
    </form>
  );
}
