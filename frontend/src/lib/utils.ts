import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBRL(value: string | number | null | undefined): string {
  if (value == null || value === "") return "—";
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(String(value));
  if (!match) return "—";
  // Formatting never converts a decimal string to a binary floating point value.
  const integer = match[2].replace(/^0+(?=\d)/, "").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const fraction = (match[3] ?? "").padEnd(2, "0");
  if (fraction.slice(2).replace(/0/g, "")) return "Valor com precisão inválida";
  return `${match[1]}R$\u00a0${integer},${fraction.slice(0, 2)}`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  // Datas sem horário representam dias de calendário, não instantes UTC.
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${iso}T12:00:00` : iso);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString("pt-BR");
}

export function formatDatetime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatCPF(digits: string): string {
  return digits.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4");
}

export function stripCPF(value: string): string {
  return value.replace(/\D/g, "");
}
