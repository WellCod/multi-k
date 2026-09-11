import type { TableHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function DataTable({ className, density = "compact", ...props }: TableHTMLAttributes<HTMLTableElement> & { density?: "compact" | "comfortable" }) {
  return <table className={cn("data-table", className)} data-density={density} {...props} />;
}
