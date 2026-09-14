import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { type Dominio } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { step2ImovelSchema, riskStepSchemas, type Step2Data } from "./types";
import { Field } from "./shared";

export function Step2Imovel({
  stage = "object",
  dominios,
  defaultValues,
  onBack,
  onNext,
}: {
  stage?: "object" | "profile";
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
    resolver: zodResolver(riskStepSchemas.imovel[stage]),
    defaultValues: defaultValues as z.infer<typeof step2ImovelSchema>,
  });

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-4">
      {stage === "object" && <>
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

      </>}
      {stage === "profile" && <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
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

      }
      <div className="pt-2 flex justify-between">
        <Button type="button" variant="outline" onClick={onBack}>
          ← Voltar
        </Button>
        <Button type="submit">Próximo →</Button>
      </div>
    </form>
  );
}
