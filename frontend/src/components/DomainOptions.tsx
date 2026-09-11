import { useEffect, useState } from "react";
import { api, type Dominio } from "@/lib/api";

export function DomainOptions({ tipo }: { tipo: string }) {
  const [items, setItems] = useState<Dominio[] | null>(null);
  useEffect(() => {
    let disposed = false;
    api.dominios.list(tipo).then(data => { if (!disposed) setItems(data); }).catch(() => { if (!disposed) setItems([]); });
    return () => { disposed = true; };
  }, [tipo]);
  if (!items) return <option disabled>Carregando opções…</option>;
  if (!items.length) return <option disabled>Opções indisponíveis — contate o administrador</option>;
  return <>{items.map(item => <option key={`${item.cia ?? ""}:${item.codigo}`} value={item.codigo}>{item.descricao}</option>)}</>;
}
