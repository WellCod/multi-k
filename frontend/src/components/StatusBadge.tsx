const STATUS_META: Record<string, { label: string; color: string }> = {
  aguardando: {
    label: "Aguardando",
    color: "text-gray-500 bg-gray-100 dark:bg-gray-700 dark:text-gray-300",
  },
  processando: {
    label: "Processando",
    color: "text-blue-700 bg-blue-100 dark:bg-blue-900 dark:text-blue-300",
  },
  sucesso: {
    label: "Sucesso",
    color: "text-green-700 bg-green-100 dark:bg-green-900 dark:text-green-300",
  },
  restricao: {
    label: "Com restrição",
    color: "text-yellow-700 bg-yellow-100 dark:bg-yellow-900 dark:text-yellow-300",
  },
  erro: {
    label: "Não realizada",
    color: "text-red-700 bg-red-100 dark:bg-red-900 dark:text-red-300",
  },
};

export function StatusBadge({ status }: { status: string }) {
  const meta = STATUS_META[status] ?? {
    label: status,
    color: "text-gray-700 bg-gray-100 dark:bg-gray-700 dark:text-gray-300",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${meta.color}`}
    >
      {meta.label}
    </span>
  );
}
