import type { ItemComparativo } from "./api";

/** A tabela repete o cartão quando não há o que comparar: só vale a pena com
 *  dois prêmios lado a lado ou com cobertura canônica para confrontar. */
export function vaiComparar(items: ItemComparativo[]): boolean {
  const comPremio = items.filter((i) => i.premio_total != null).length;
  const comCobertura = items.some((i) => (i.coberturas_comparaveis ?? []).length > 0);
  return comPremio >= 2 || (comPremio >= 1 && comCobertura);
}
