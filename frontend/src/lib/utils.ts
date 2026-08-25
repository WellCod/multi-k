import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBRL(value: string | number | null | undefined): string {
  if (value == null || value === "") return "—";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "—";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(num);
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  // Usa meio-dia para evitar conversão UTC-3 que mostraria o dia anterior
  return new Date(iso + "T12:00:00").toLocaleDateString("pt-BR");
}

export function formatDatetime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
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
