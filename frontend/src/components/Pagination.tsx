import { Button } from "@/components/ui/button";

interface PaginationProps {
  page: number;
  total: number;
  perPage: number;
  onChange: (page: number) => void;
}

export function Pagination({ page, total, perPage, onChange }: PaginationProps) {
  const totalPages = Math.ceil(total / perPage);
  if (totalPages <= 1) return null;
  const start = (page - 1) * perPage + 1;
  const end = Math.min(page * perPage, total);

  return (
    <div className="flex items-center justify-between mt-3">
      <span className="text-xs text-gray-500 dark:text-gray-400">
        {start}–{end} de {total}
      </span>
      <div className="flex gap-1">
        <Button
          variant="outline"
          size="sm"
          disabled={page === 1}
          onClick={() => onChange(page - 1)}
        >
          ‹ Anterior
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={page === totalPages}
          onClick={() => onChange(page + 1)}
        >
          Próxima ›
        </Button>
      </div>
    </div>
  );
}
