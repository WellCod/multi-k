interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string;
}

export function KpiCard({ label, value, sub }: KpiCardProps) {
  return (
    <div className="rounded border border-line bg-surface px-4 py-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted mb-1">
        {label}
      </p>
      <p className="text-xl font-bold text-ink ">{value}</p>
      {sub && <p className="text-xs text-muted mt-1">{sub}</p>}
    </div>
  );
}
