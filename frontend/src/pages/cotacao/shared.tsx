import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

export function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    sucesso: "bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300",
    restricao: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300",
    erro: "bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300",
    processando: "bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300",
    aguardando: "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300",
  };
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${map[status] ?? "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"}`}
    >
      {status}
    </span>
  );
}

export function LoadingPanel({
  seconds,
  onCancel,
}: {
  seconds: number;
  onCancel: () => void;
}) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6 text-center space-y-4">
      <div className="flex items-center justify-center gap-3">
        <svg
          className="animate-spin h-5 w-5 text-blue-500"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
          Consultando seguradoras… {seconds}s
        </span>
      </div>
      <Button variant="outline" size="sm" onClick={onCancel}>
        Cancelar
      </Button>
    </div>
  );
}
