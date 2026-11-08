"use client";

import { INSPECTION_FILTERS, type InspectionFilter } from "@/lib/dashboard";

export function InspectionFilters({ query, status, onQueryChange, onStatusChange }: {
  query: string; status: InspectionFilter;
  onQueryChange: (query: string) => void; onStatusChange: (status: InspectionFilter) => void;
}) {
  return <div className="flex flex-col gap-2 sm:flex-row" role="search" aria-label="Поиск инспекций">
    <label className="min-w-0 flex-1"><span className="sr-only">Поиск инспекций</span>
      <input type="search" name="inspection-search" autoComplete="off" value={query} onChange={event => onQueryChange(event.target.value)}
        placeholder="Название или ID…" className="h-11 w-full rounded-md border border-control bg-field px-3 text-sm" /></label>
    <label><span className="sr-only">Статус инспекции</span>
      <select name="inspection-status" value={status} onChange={event => onStatusChange(event.target.value as InspectionFilter)}
        className="h-11 w-full rounded-md border border-control bg-field pl-3 pr-8 text-sm sm:w-auto">
        {INSPECTION_FILTERS.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
      </select></label>
  </div>;
}
