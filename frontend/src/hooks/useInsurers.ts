import { useEffect, useState } from "react";
import { api, type Seguradora } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function useInsurers() {
  const { user } = useAuth();
  const [items, setItems] = useState<Seguradora[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!user) return;
    let disposed = false;
    setItems([]);
    setError("");
    api.dominios.seguradoras().then(data => { if (!disposed) setItems(data); }).catch(() => { if (!disposed) setError("Não foi possível carregar as seguradoras. Atualize a página para tentar novamente."); });
    return () => { disposed = true; };
  }, [user]);
  return { items, error };
}
