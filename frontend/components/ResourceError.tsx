export function ResourceError({ error, loading, onRetry }: { error: string; loading: boolean; onRetry: () => void }) {
  return <div className="panel flex flex-wrap items-center justify-between gap-4 p-4" role="alert">
    <div><p className="text-base font-medium text-danger">Данные не удалось обновить</p><p className="mt-1 text-base text-muted">{error}</p></div>
    <button type="button" onClick={onRetry} disabled={loading} className="btn">{loading ? "Загрузка…" : "Повторить"}</button>
  </div>;
}
