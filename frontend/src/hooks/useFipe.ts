import { useState, useEffect } from "react";

const BASE = (import.meta.env.VITE_API_URL ?? "/api") as string;

export type FipeMarca = { codigo: string; nome: string };
export type FipeModelo = { codigo: string; nome: string };
export type FipeAno = { codigo: string; nome: string };
export type FipePreco = {
  codigo_fipe: string;
  marca: string;
  modelo: string;
  ano_modelo: string;
  combustivel: string;
  valor: string;
  mes_referencia: string;
};

type Estado<T> = { data: T | null; loading: boolean; error: string | null };

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { credentials: "include" });
  if (!res.ok) throw new Error(`FIPE ${res.status}`);
  return res.json() as Promise<T>;
}

function useGet<T>(url: string | null): Estado<T> {
  const [state, setState] = useState<Estado<T>>({
    data: null,
    loading: false,
    error: null,
  });

  useEffect(() => {
    if (!url) {
      setState({ data: null, loading: false, error: null });
      return;
    }
    let cancelled = false;
    setState({ data: null, loading: true, error: null });
    get<T>(url)
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : "Erro ao consultar FIPE";
          setState({ data: null, loading: false, error: msg });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [url]);

  return state;
}

export function useFipeMarcas(tipo: "carros" | "motos") {
  return useGet<FipeMarca[]>(`/fipe/marcas?tipo=${tipo}`);
}

export function useFipeModelos(tipo: "carros" | "motos", marcaId: string | null) {
  const url = marcaId ? `/fipe/modelos?tipo=${tipo}&marca_id=${marcaId}` : null;
  return useGet<FipeModelo[]>(url);
}

export function useFipeAnos(
  tipo: "carros" | "motos",
  marcaId: string | null,
  modeloId: string | null
) {
  const url =
    marcaId && modeloId
      ? `/fipe/anos?tipo=${tipo}&marca_id=${marcaId}&modelo_id=${modeloId}`
      : null;
  return useGet<FipeAno[]>(url);
}

export function useFipePreco(
  tipo: "carros" | "motos",
  marcaId: string | null,
  modeloId: string | null,
  anoId: string | null
) {
  const url =
    marcaId && modeloId && anoId
      ? `/fipe/preco?tipo=${tipo}&marca_id=${marcaId}&modelo_id=${modeloId}&ano_id=${anoId}`
      : null;
  return useGet<FipePreco>(url);
}
