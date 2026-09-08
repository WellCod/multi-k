import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { api, type Dominio, type Cliente, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { stripCPF } from "@/lib/utils";
import { step1Schema, type Step1Data } from "./types";
import { Field } from "./shared";

export function Step1({
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
  const [cpfSearchError, setCpfSearchError] = useState<string | null>(null);

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
    setCpfSearchError(null);
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
    } catch (e) {
      if (!(e instanceof ApiError) || e.status >= 500) {
        setCpfSearchError("Falha ao buscar cliente. Preencha os dados manualmente.");
      }
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
        <p className="text-xs text-green-700 bg-green-50 dark:bg-green-900/30 dark:text-green-400 rounded px-2 py-1">
          Cliente encontrado: {foundCliente.nome}
        </p>
      )}
      {cpfSearchError && (
        <p className="text-xs text-yellow-800 bg-yellow-50 dark:bg-yellow-900/30 dark:text-yellow-400 border border-yellow-200 dark:border-yellow-700 rounded px-2 py-1">
          {cpfSearchError}
        </p>
      )}

      <Field label="Nome completo" error={errors.nome?.message}>
        <Input {...register("nome")} />
      </Field>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="E-mail" error={errors.email?.message}>
          <Input type="email" {...register("email")} />
        </Field>
        <Field label="Telefone">
          <Input {...register("telefone")} />
        </Field>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Data de nascimento" error={errors.data_nascimento?.message}>
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

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
