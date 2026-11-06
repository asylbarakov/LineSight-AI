import type { InspectionStatus, InspectionSummary, Metrics } from "./types";

/** These APIs expose no global defect classification or engineer-confirmed defect counts.
 * findings_count includes visibility/equipment observations and cannot substitute for either. */
export function dashboardSummary(rows: InspectionSummary[] | null, metrics: Metrics | null) {
  return {total: metrics?.inspections_total ?? rows?.length ?? null, detectedDefects: null, confirmedDefects: null};
}

export type InspectionFilter = "all" | InspectionStatus;
export const INSPECTION_FILTERS: { value: InspectionFilter; label: string }[] = [
  { value: "all", label: "Все статусы" }, { value: "queued", label: "В очереди" },
  { value: "processing", label: "Обрабатывается" }, { value: "done", label: "Обработано" }, { value: "failed", label: "Ошибка" },
];

const createdTime = (row: InspectionSummary) => {
  const value = row.created_at ? Date.parse(row.created_at) : NaN;
  return Number.isFinite(value) ? value : 0;
};

export function filterInspections(rows: InspectionSummary[], query: string, status: InspectionFilter) {
  const search = query.trim().toLocaleLowerCase("ru-RU");
  return rows.filter((row) => (status === "all" || row.status === status)
    && (!search || row.title.toLocaleLowerCase("ru-RU").includes(search) || row.id.toLowerCase().includes(search)))
    .sort((a, b) => createdTime(b) - createdTime(a) || a.id.localeCompare(b.id));
}

export function summarizeInspections(rows: InspectionSummary[]) {
  const counts = { queued: 0, processing: 0, done: 0, failed: 0, findings: 0 };
  for (const row of rows) { counts[row.status] += 1; counts.findings += row.findings_count; }
  return { ...counts, active: counts.queued + counts.processing, total: rows.length };
}

const localDateKey = (date: Date) => `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;

/** Counts uploads by local calendar date, not completions (the list API has no finished_at). */
export function inspectionActivity(rows: InspectionSummary[], now = new Date()) {
  const today = new Date(now);
  today.setHours(0, 0, 0, 0);
  const days = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today);
    date.setDate(date.getDate() - (6 - index));
    return { key: localDateKey(date), date, count: 0 };
  });
  const buckets = new Map(days.map((day) => [day.key, day]));
  for (const row of rows) {
    if (!row.created_at) continue;
    const date = new Date(row.created_at);
    if (!Number.isFinite(date.getTime()) || date.getTime() > now.getTime()) continue;
    const bucket = buckets.get(localDateKey(date));
    if (bucket) bucket.count += 1;
  }
  return days;
}
