import { formatBRL } from "@/lib/utils";

export function Money({ value }: { value: string | null | undefined }) {
  return <span className="tabular-nums whitespace-nowrap">{formatBRL(value)}</span>;
}
