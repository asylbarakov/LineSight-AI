export function KPICard({ label, value, description, loading }: { label: string; value: number | null; description: string; loading?: boolean }) {
  return <article className="summary-metric" aria-label={label}>
    <p className="text-label font-medium text-muted">{label}</p>
    {loading ? <div className="skeleton my-1 h-7 w-12" aria-label="Загрузка показателя" />
      : <p className={`mt-1 text-readout font-medium tabular-nums ${value === null ? "text-muted" : "text-fg"}`}>
        {value === null ? <span aria-label={`Недоступно. ${description}`}>—</span> : value.toLocaleString("ru-RU")}
      </p>}
    <p className="mt-0.5 text-xs text-muted" title={description}>{value === null && !loading ? "Нет сводки" : description}</p>
  </article>;
}
