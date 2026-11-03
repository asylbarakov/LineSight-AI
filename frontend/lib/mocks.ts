// Моки на каждый эндпоинт контракта (задача 15). Включаются NEXT_PUBLIC_USE_MOCKS=true.
import type { Decision, Finding, InspectionDetail, InspectionSummary, Metrics } from "./types";

const now = Date.now();
const iso = (minAgo: number) => new Date(now - minAgo * 60_000).toISOString();

export const mockInspections: InspectionSummary[] = [
  { id: "mock-1", title: "Облёт участка 1", created_at: iso(30), status: "done", findings_count: 4 },
  { id: "mock-2", title: "Облёт участка 2", created_at: iso(5), status: "processing", findings_count: 0 },
  { id: "mock-3", title: "Битый файл", created_at: iso(120), status: "failed", findings_count: 0 },
];

export function mockDetail(id: string): InspectionDetail {
  const base = mockInspections.find((i) => i.id === id) ?? mockInspections[0];
  return {
    id: base.id,
    title: base.title,
    filename: "flight.mp4",
    status: base.status,
    error_code: base.status === "failed" ? "E_DECODE" : null,
    error_message: null,
    progress: base.status === "processing" ? 0.42 : base.status === "done" ? 1 : 0,
    duration_sec: 42.5,
    fps: base.status === "done" ? 11.3 : null,
    stage_times: base.status === "done" ? { decode: 3.1, detect: 18.4, track: 0.6, findings: 0.1, db: 0.2 } : null,
    created_at: base.created_at,
    started_at: base.created_at,
    finished_at: base.status === "done" ? base.created_at : null,
  };
}

export let mockFindings: Finding[] = [
  { id: "f1", type: "insulator_crack", priority: "high", confidence: 0.93, timecode_sec: 20.5, frame_path: null,
    bbox: { x: 0.41, y: 0.22, w: 0.1, h: 0.18 }, status: "new" },
  { id: "f2", type: "insulator", priority: "medium", confidence: 0.81, timecode_sec: 8, frame_path: null,
    bbox: { x: 0.2, y: 0.4, w: 0.12, h: 0.2 }, status: "new" },
  { id: "f3", type: "tower", priority: "low", confidence: 0.64, timecode_sec: 31, frame_path: null,
    bbox: { x: 0.6, y: 0.1, w: 0.15, h: 0.6 }, status: "new" },
  { id: "f4", type: "low_visibility", priority: "insufficient_data", confidence: 0.82, timecode_sec: 12, frame_path: null,
    bbox: null, status: "new" },
];

export function mockPatch(id: string, status: Decision): Finding {
  mockFindings = mockFindings.map((f) => (f.id === id ? { ...f, status } : f));
  return mockFindings.find((f) => f.id === id)!;
}

export const mockMetrics: Metrics = {
  inspections_total: 3,
  avg_processing_sec: 41.2,
  avg_fps: 10.8,
  failed_share: 0.33,
  recent_runs: [
    { id: "mock-1", title: "Облёт участка 1", status: "done", error_code: null, fps: 11.3,
      stage_times: { decode: 3.1, detect: 18.4, track: 0.6, findings: 0.1, db: 0.2 } },
    { id: "mock-3", title: "Битый файл", status: "failed", error_code: "E_DECODE", fps: null, stage_times: null },
  ],
};
