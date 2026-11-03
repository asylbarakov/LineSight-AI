// Типы по контракту API (README, раздел «Контракт»).

export type InspectionStatus = "queued" | "processing" | "done" | "failed";
export type ErrorCode = "E_VIDEO_INVALID" | "E_DECODE" | "E_MODEL" | "E_TIMEOUT";
export type Priority = "high" | "medium" | "low" | "insufficient_data";
export type FindingStatus = "new" | "confirmed" | "rejected" | "reshoot";
export type Decision = Exclude<FindingStatus, "new">;

export interface BBox { x: number; y: number; w: number; h: number }

export interface Finding {
  id: string;
  type: string;
  priority: Priority;
  confidence: number;
  timecode_sec: number;
  frame_path: string | null;
  bbox: BBox | null;
  status: FindingStatus;
}

export interface InspectionSummary {
  id: string;
  title: string;
  created_at: string | null;
  status: InspectionStatus;
  findings_count: number;
}

export interface StageTimes { [stage: string]: number }

export interface InspectionDetail {
  id: string;
  title: string;
  filename: string;
  status: InspectionStatus;
  error_code: ErrorCode | null;
  error_message: string | null;
  progress: number;
  duration_sec: number | null;
  fps: number | null;
  stage_times: StageTimes | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface MetricsRun {
  id: string;
  title: string;
  status: InspectionStatus;
  error_code: ErrorCode | null;
  fps: number | null;
  stage_times: StageTimes | null;
}

export interface Metrics {
  inspections_total: number;
  avg_processing_sec: number | null;
  avg_fps: number | null;
  failed_share: number;
  recent_runs: MetricsRun[];
}
