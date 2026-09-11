import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { type Dominio, type Seguradora } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { step4Schema, type Step4Data } from "./types";
import { Field } from "./shared";

export function Step4({
  ramo,
  coberturasIniciais,
  dominios,
  defaultValues,
  onBack,
  onNext,
  submitting,
  serverError,
  seguradoras,
  selecionadas,
  onSelecionadas,
}: {
  ramo: string;
  coberturasIniciais?: string[];
  seguradoras: Seguradora[];
  selecionadas: string[];
  onSelecionadas: (ids: string[]) => void;
  dominios: Dominio[];
  defaultValues?: Step4Data;
  onBack: () => void;
  onNext: (data: Step4Data) => void;
  submitting?: boolean;
  serverError?: string | null;
}) {
  const coberturas = dominios.filter(d => d.tipo === (ramo === "imovel" ? "cobertura_imovel" : "cobertura_auto"));
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
    defaultValues: {
      inicio_vigencia: today,
      fim_vigencia: nextYear,
      ...defaultValues,
      coberturas: defaultValues?.coberturas ?? coberturasIniciais ?? [],
    },
  });

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-4">
      <fieldset className="border border-line rounded p-3 space-y-2" aria-describedby={errors.coberturas ? "coverage-error" : undefined}>
        <legend className="text-sm font-medium px-1">Coberturas desejadas</legend>
        {coberturas.map(item => <label key={item.codigo} className="flex items-center gap-2 text-sm">
          <input type="checkbox" value={item.codigo} {...register("coberturas")} />{item.descricao}
        </label>)}
        {!coberturas.length && <p className="text-xs text-warning">Coberturas indisponíveis. Recarregue a página para tentar novamente.</p>}
        {errors.coberturas && <p id="coverage-error" role="alert" className="text-xs text-danger">{errors.coberturas.message}</p>}
      </fieldset>
      <fieldset className="border border-line rounded p-3">
        <legend className="text-sm font-medium px-1">Seguradoras a consultar</legend>
        <div className="flex flex-wrap gap-4">{seguradoras.map(item => <label key={item.id} className="flex items-center gap-2">
          <input type="checkbox" checked={selecionadas.includes(item.id)} onChange={event => onSelecionadas(event.target.checked ? [...selecionadas, item.id] : selecionadas.filter(id => id !== item.id))} />
          {item.logo_url && <img className="h-6 w-6 object-contain" src={item.logo_url} alt="" />}{item.nome}
        </label>)}</div>
        {!selecionadas.length && <p className="text-warning text-xs">Selecione ao menos uma seguradora.</p>}
      </fieldset>
      <Field label="Parcelamento do prêmio" error={errors.plano_pagamento?.message}>
        <Select {...register("plano_pagamento")}>
          <option value="">—</option>
          {planos.map(d => <option key={d.codigo} value={d.codigo}>{d.descricao}</option>)}
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
        <div className="rounded border border-line bg-canvas p-4 text-sm text-danger ">
          {serverError}
        </div>
      )}

      <div className="pt-2 flex justify-between">
        <Button type="button" variant="outline" onClick={onBack} disabled={submitting}>
          ← Voltar
        </Button>
        <Button type="submit" disabled={submitting || !selecionadas.length}>
          {submitting ? "Enviando…" : "Solicitar cotação →"}
        </Button>
      </div>
    </form>
  );
}
