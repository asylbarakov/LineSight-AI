"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { MockBadge } from "@/components/Badges";
import { InspectionTable } from "@/components/InspectionTable";
import { KPICard } from "@/components/KPICard";
import { USE_MOCKS } from "@/lib/api";
import { dashboardSummary, filterInspections, INSPECTION_FILTERS, type InspectionFilter } from "@/lib/dashboard";
import { DashboardCharts } from "./DashboardCharts";
import { useDashboardData } from "./useDashboardData";

const PAGE_SIZE = 6;
export function Dashboard() {
  const { inspections, metrics, errors, refreshing, updatedAt, refresh } = useDashboardData();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<InspectionFilter>("all");
  const [page, setPage] = useState(1);
  const filtered = useMemo(() => filterInspections(inspections ?? [], query, status), [inspections, query, status]);
  const summary = dashboardSummary(inspections, metrics);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const rows = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const hasError = !!(errors.inspections || errors.metrics);
  const listLoading = inspections === null && !errors.inspections;
  const resetFilters = () => { setQuery(""); setStatus("all"); setPage(1); };

  return <div className="dashboard-workspace space-y-6" data-dashboard>
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div><div className="flex items-center gap-3"><h1 className="page-title">Обзор инспекций</h1>{USE_MOCKS && <MockBadge />}</div>
        <p className="mt-2 max-w-prose text-base text-muted">Видеоинспекции линий электропередачи</p></div>
      <Link href="/inspections#new-inspection" className="btn-primary"><span aria-hidden="true">+</span>Новая инспекция</Link>
    </header>

    {hasError && <div className="flex flex-wrap items-center justify-between gap-3 border-l-2 border-warn py-2 pl-4" role="alert">
      <div><p className="text-sm font-medium">Не все данные удалось обновить</p>
        {errors.inspections && <p className="mt-1 text-xs text-muted">Инспекции: {errors.inspections}</p>}
        {errors.metrics && <p className="mt-1 text-xs text-muted">Метрики: {errors.metrics}</p>}
        <p className="mt-1 text-xs text-muted">Последние полученные данные сохранены.</p></div>
      <button type="button" onClick={refresh} disabled={refreshing} className="btn">{refreshing ? "Обновление…" : "Повторить сейчас"}</button>
    </div>}

    <section className="summary-strip" aria-label="Ключевые показатели">
      <KPICard label="Всего инспекций" value={summary.total} description="За всё время" loading={summary.total === null && refreshing} />
      <KPICard label="Обнаружено дефектов" value={summary.detectedDefects} description="Сводка по дефектным находкам модели недоступна. Недостаточная видимость и обычные наблюдения не являются дефектами." />
      <KPICard label="Подтверждено дефектов" value={summary.confirmedDefects} description="Сводка недоступна. Учитываются только дефектные находки, явно подтверждённые инженером." />
    </section>

    <div className="dashboard-body">
      <section className="min-w-0" aria-labelledby="recent-inspections-title">
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 id="recent-inspections-title" className="section-title">Последние инспекции</h2>
          <Link href="/inspections" className="quiet-link">Все инспекции <span aria-hidden="true">↗</span></Link></div>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <label className="min-w-0 flex-1"><span className="sr-only">Поиск инспекций</span>
            <input type="search" value={query} onChange={event => { setQuery(event.target.value); setPage(1); }}
              placeholder="Найти по названию или ID" className="h-11 w-full rounded-md border border-control bg-field px-3 text-sm" /></label>
          <label><span className="sr-only">Статус инспекции</span><select value={status} onChange={event => { setStatus(event.target.value as InspectionFilter); setPage(1); }}
            className="h-11 w-full rounded-md border border-control bg-field pl-3 pr-8 text-sm sm:w-auto">
            {INSPECTION_FILTERS.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select></label>
        </div>
        <div className="mt-4"><InspectionTable rows={rows} loading={listLoading}
          emptyMessage={inspections === null ? "Список инспекций недоступен. Повторите загрузку." : query || status !== "all" ? "Инспекции по вашему запросу не найдены" : "Инспекций пока нет. Загрузите первое видео для анализа."} /></div>
        {!listLoading && inspections !== null && filtered.length === 0 && (query || status !== "all") &&
          <div className="text-center"><button type="button" onClick={resetFilters} className="quiet-link text-accent">Сбросить поиск и фильтр</button></div>}
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3 text-xs text-muted">
          <p>{inspections === null ? "Список не загружен" : `Показано ${rows.length} из ${filtered.length}`} · Статус обработки видео</p>
          {pageCount > 1 && <nav className="flex items-center gap-2" aria-label="Страницы инспекций">
            <button type="button" onClick={() => setPage(currentPage - 1)} disabled={currentPage === 1} className="icon-button disabled:opacity-40" aria-label="Предыдущая страница">←</button>
            <span>{currentPage} / {pageCount}</span>
            <button type="button" onClick={() => setPage(currentPage + 1)} disabled={currentPage === pageCount} className="icon-button disabled:opacity-40" aria-label="Следующая страница">→</button>
          </nav>}
        </div>
      </section>
      <DashboardCharts inspections={inspections} loading={listLoading} />
    </div>

    <footer className="flex flex-wrap items-center justify-between gap-x-5 gap-y-1 border-t border-line pt-3 text-xs text-muted">
      <p>{updatedAt ? `Обновлено ${updatedAt.toLocaleTimeString("ru-RU", {hour: "2-digit", minute: "2-digit"})}` : "Данные ещё не получены"}</p>
      <button type="button" onClick={refresh} disabled={refreshing} className="quiet-link disabled:opacity-50">{refreshing ? "Обновление…" : "Обновить данные"}</button>
    </footer>
  </div>;
}
