import { Button } from "@/components/ui/button";

export { Field } from "@/components/primitives";

export { StatusBadge } from "@/components/StatusBadge";

export function LoadingPanel({
  seconds,
  onCancel,
}: {
  seconds: number;
  onCancel: () => void;
}) {
  return (
    <div className="rounded border border-line bg-surface p-6 text-center space-y-4">
      <div className="flex items-center justify-center gap-3">
        <svg
          className="animate-spin h-5 w-5 text-action"
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
        <span className="text-sm font-medium text-ink ">
          Consultando seguradoras… {seconds}s
        </span>
      </div>
      <Button variant="outline" size="sm" onClick={onCancel}>
        Cancelar
      </Button>
    </div>
  );
}
