import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { type Dominio } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { step3Schema, type Step3Data } from "./types";

export function Step3({
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
      <p className="text-sm text-muted">Selecione as coberturas desejadas:</p>
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
            <span className="text-muted text-xs">({d.codigo})</span>
          </label>
        ))}
      </div>
      {errors.coberturas && (
        <p className="text-xs text-danger">{errors.coberturas.message}</p>
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
