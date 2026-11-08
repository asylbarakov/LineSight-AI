import { describe, expect, it } from "vitest";
import { dashboardSummary, filterInspections, inspectionActivity, summarizeInspections } from "./dashboard";
import * as dashboard from "./dashboard";
import type { InspectionStatus, InspectionSummary } from "./types";

const row = (id: string, status: InspectionStatus, created_at: string | null, title = id, findings_count = 0): InspectionSummary =>
  ({ id, status, created_at, title, findings_count });

describe("Dashboard inspections", () => {
  it("keeps last-good aggregates on API failure and never invents zero on initial failure", () => {
    const merge = (dashboard as unknown as {mergeDashboardData?: (previous: unknown, list: unknown, metrics: unknown) => {metrics: unknown}}).mergeDashboardData;
    expect(merge).toBeTypeOf("function");
    const failed = {status: "rejected", reason: Error("offline")};
    const previous = {inspections: [], metrics: {inspections_total: 4, detected_defects_total: 2, confirmed_defects_total: 0}};
    expect(merge!(previous, failed, failed).metrics).toEqual(previous.metrics);
    expect(merge!({inspections: null, metrics: null}, failed, failed).metrics).toBeNull();
  });
  it("replaces recovered aggregates after a delayed worker result or review update", () => {
    const metrics = {inspections_total: 1, detected_defects_total: 1, confirmed_defects_total: 1, avg_processing_sec: null, avg_fps: null, failed_share: 0, recent_runs: []};
    const current = dashboard.mergeDashboardData({inspections: [], metrics: {...metrics, detected_defects_total: 0, confirmed_defects_total: 0}},
      {status: "fulfilled", value: []}, {status: "fulfilled", value: metrics});
    expect(dashboardSummary(current.inspections, current.metrics)).toEqual({total: 1, detectedDefects: 1, confirmedDefects: 1});
  });
  it("exposes exactly three KPI values without treating all findings as defects", () => {
    const rows = [row("a", "done", null, "Inspection", 27)];
    expect(dashboardSummary(rows, null)).toEqual({total: null, detectedDefects: null, confirmedDefects: null});
    expect(dashboardSummary(null, null)).toEqual({total: null, detectedDefects: null, confirmedDefects: null});
  });
  it("keeps absent defect aggregates unavailable even with zero inspections or counts of all confirmed observations", () => {
    const metrics = {inspections_total: 0, avg_processing_sec: null, avg_fps: null, failed_share: 0, recent_runs: [], findings_total: 30, findings_confirmed_total: 10};
    expect(dashboardSummary([], metrics)).toEqual({total: 0, detectedDefects: null, confirmedDefects: null});
  });
  it("keeps a real zero total and prefers the metrics aggregate over a potentially partial list", () => {
    const metrics = {inspections_total: 0, avg_processing_sec: null, avg_fps: null, failed_share: 0, recent_runs: []};
    expect(dashboardSummary([row("a", "done", null)], metrics).total).toBe(0);
    expect(dashboardSummary([], {...metrics, inspections_total: 42}).total).toBe(42);
  });
  it("uses persisted defect aggregates including zero without counting observations", () => {
    const metrics = {inspections_total: 4, detected_defects_total: 2, confirmed_defects_total: 1, avg_processing_sec: null, avg_fps: null, failed_share: 0, recent_runs: []};
    expect(dashboardSummary([], metrics)).toEqual({total: 4, detectedDefects: 2, confirmedDefects: 1});
    expect(dashboardSummary([], {...metrics, detected_defects_total: 0, confirmed_defects_total: 0})).toEqual({total: 4, detectedDefects: 0, confirmedDefects: 0});
  });
  it("combines case-insensitive Russian search and status without mutating source data", () => {
    const rows = [row("a", "done", "2026-11-03T00:00:00Z", "Северная ЛЭП"), row("b", "failed", "2026-11-04T00:00:00Z", "Северная ЛЭП")];
    expect(filterInspections(rows, "  СЕВЕРНАЯ ", "done").map((r) => r.id)).toEqual(["a"]);
    expect(rows.map((r) => r.id)).toEqual(["a", "b"]);
  });

  it("searches identifiers, sorts recent first and tolerates missing/invalid dates", () => {
    const rows = [row("old", "queued", null), row("flight-123", "done", "2026-11-03T10:00:00Z"), row("new", "processing", "2026-11-04T10:00:00Z"), row("invalid", "failed", "bad-date")];
    expect(filterInspections(rows, "123", "all").map((r) => r.id)).toEqual(["flight-123"]);
    expect(filterInspections(rows, "", "all").slice(0, 2).map((r) => r.id)).toEqual(["new", "flight-123"]);
    expect(filterInspections(rows, "missing", "all")).toEqual([]);
  });

  it("keeps processing states separate from engineer review and counts real findings", () => {
    const result = summarizeInspections([row("q", "queued", null), row("p", "processing", null), row("d", "done", null, "Готово", 3), row("f", "failed", null)]);
    expect(result).toEqual({ queued: 1, processing: 1, done: 1, failed: 1, findings: 3, active: 2, total: 4 });
    expect(summarizeInspections([]).total).toBe(0);
  });

  it("returns seven chronological local calendar days including zero activity", () => {
    const now = new Date(2026, 10, 5, 12);
    const days = inspectionActivity([], now);
    expect(days).toHaveLength(7);
    expect(days[0].date.getDate()).toBe(30);
    expect(days[6].date.getDate()).toBe(5);
    expect(days.every((day) => day.count === 0)).toBe(true);
  });

  it("buckets uploads across month boundaries, excluding future and invalid dates", () => {
    const now = new Date(2026, 10, 5, 12);
    const date = (month: number, day: number, hour = 10) => new Date(2026, month, day, hour).toISOString();
    const days = inspectionActivity([
      row("a", "done", date(9, 30)), row("b", "failed", date(10, 5)), row("c", "processing", date(10, 5, 11)),
      row("future", "queued", date(10, 6)), row("later-today", "queued", date(10, 5, 14)),
      row("old", "done", date(9, 29)), row("bad", "failed", "bad"), row("none", "done", null),
    ], now);
    expect(days.map((day) => day.count)).toEqual([1, 0, 0, 0, 0, 0, 2]);
  });
});
