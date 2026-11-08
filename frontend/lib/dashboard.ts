import type { InspectionStatus, InspectionSummary, Metrics } from "./types";

export function mergeDashboardData(previous: {inspections: InspectionSummary[] | null; metrics: Metrics | null},
  list: PromiseSettledResult<InspectionSummary[]>, metrics: PromiseSettledResult<Metrics>) {
  return {inspections: list.status === "fulfilled" ? list.value : previous.inspections,
    metrics: metrics.status === "fulfilled" ? metrics.value : previous.metrics};
}

/** One in-flight refresh; mutation/focus bursts queue at most one follow-up. */
export function startDashboardPolling(load: () => Promise<boolean>, visible = () => true) {
  let stopped = false, running = false, queued = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const refresh = async () => {
    if (stopped) return;
    clearTimeout(timer);
    if (running) { queued = true; return; }
    if (!visible()) { timer = setTimeout(refresh, 30000); return; }
    running = true;
    let active = true;
    try { active = await load(); }
    catch { /* Retry transport failures without synthesizing data. */ }
    finally {
      running = false;
      if (!stopped) {
        if (queued) { queued = false; void refresh(); }
        else timer = setTimeout(refresh, active ? 5000 : 30000);
      }
    }
  };
  void refresh();
  return {refresh: () => { void refresh(); }, stop: () => { stopped = true; clearTimeout(timer); }};
}

/** Only server aggregates are authoritative. Missing fields from an older API stay unavailable. */
export function dashboardSummary(rows: InspectionSummary[] | null, metrics: Metrics | null) {
  return {total: metrics?.inspections_total ?? null, detectedDefects: metrics?.detected_defects_total ?? null, confirmedDefects: metrics?.confirmed_defects_total ?? null};
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
