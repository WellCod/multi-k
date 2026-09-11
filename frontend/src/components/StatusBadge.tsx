const STATUS_META: Record<string, { label: string; color: string }> = {
  aguardando: {
    label: "Aguardando",
    color: "text-muted bg-canvas ",
  },
  processando: {
    label: "Processando",
    color: "text-muted bg-canvas",
  },
  pendente: { label: "Aguardando", color: "text-muted bg-canvas" },
  cancelado: { label: "Cancelada", color: "text-muted bg-canvas" },
  sucesso: {
    label: "Sucesso",
    color: "text-success bg-canvas ",
  },
  restricao: {
    label: "Com restrição",
    color: "text-warning bg-canvas ",
  },
  erro: {
    label: "Não realizada",
    color: "text-danger bg-canvas ",
  },
};

export function StatusBadge({ status }: { status: string }) {
  const meta = STATUS_META[status] ?? {
    label: status,
    color: "text-ink bg-canvas ",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${meta.color}`}
    >
      {meta.label}
    </span>
  );
}
