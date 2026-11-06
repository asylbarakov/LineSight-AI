import { useMemo } from "react";
import { inspectionActivity } from "@/lib/dashboard";
import type { InspectionSummary } from "@/lib/types";

export function DashboardCharts({ inspections, loading }: { inspections: InspectionSummary[] | null; loading: boolean }) {
  const activity = useMemo(() => inspectionActivity(inspections ?? []), [inspections]);
  const max = Math.max(1, ...activity.map(day => day.count));
  return <aside className="dashboard-analytics" aria-label="Аналитика инспекций">
    <section className="min-w-0 border-t border-line pt-5" aria-labelledby="activity-title">
      <h2 id="activity-title" className="section-title">Динамика инспекций</h2>
      <p className="mt-1 text-xs text-muted">Загрузки за последние 7 дней</p>
      {loading ? <div className="skeleton my-4 h-28" aria-label="Загрузка графика" /> : inspections === null ? <p className="py-6 text-sm text-muted">Данные графика недоступны.</p>
        : <div className="mt-4 grid h-28 grid-cols-7 items-end gap-2 border-b border-line" aria-label="Количество загруженных инспекций по дням">
          {activity.map(day => <div key={day.key} tabIndex={0} title={`${day.date.toLocaleDateString("ru-RU")}: загружено ${day.count}`}
            aria-label={`${day.date.toLocaleDateString("ru-RU")}: загружено ${day.count} инспекций`} className="flex h-full min-w-0 flex-col items-center justify-end gap-1 rounded-sm">
            <span className="text-xs tabular-nums text-muted">{day.count}</span>
            <div aria-hidden="true" className="w-full max-w-5 rounded-t-sm bg-chart" style={{height: `${day.count / max * 64}px`}} />
            <span className="pb-2 text-xs capitalize text-muted">{day.date.toLocaleDateString("ru-RU", {weekday: "short"})}</span>
          </div>)}
        </div>}
      <p className="mt-3 text-xs text-muted">По дате загрузки, не завершения анализа.</p>
    </section>
    <section className="min-w-0 border-t border-line pt-5" aria-labelledby="review-distribution-title">
      <h2 id="review-distribution-title" className="section-title">Решения по находкам</h2>
      <p className="mt-1 text-xs text-muted">Распределение статусов проверки</p>
      <p className="mt-4 flex items-center gap-2 text-sm text-muted"><span aria-hidden="true">—</span>Сводные данные недоступны</p>
      <p className="mt-2 max-w-prose text-xs text-muted">Решения доступны внутри инспекций.</p>
      <ul className="mt-4 grid grid-cols-2 gap-x-3 gap-y-2 text-xs text-muted" aria-label="Статусы проверки">
        <li>Новые</li><li>Подтверждённые</li><li>Отклонённые</li><li>Пересъёмка</li>
      </ul>
    </section>
  </aside>;
}
