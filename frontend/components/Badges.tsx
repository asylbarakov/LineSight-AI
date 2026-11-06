import { FINDING_STATUS_RU, PRIORITY_RU, STATUS_RU } from "@/lib/texts";
import type { FindingStatus, InspectionStatus, Priority } from "@/lib/types";

const base = "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-label font-medium whitespace-nowrap";

const STATUS_CLS: Record<InspectionStatus, string> = {
  queued: "border-line bg-surface2 text-muted",
  processing: "border-accent/40 bg-accent-soft text-accent",
  done: "border-line bg-surface2 text-fg",
  failed: "border-danger/40 bg-danger-soft text-danger",
};

export function StatusBadge({ status }: { status: InspectionStatus }) {
  return (
    <span className={`${base} ${STATUS_CLS[status]}`} data-testid="status-badge">
      {status === "processing" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />}
      {STATUS_RU[status]}
    </span>
  );
}

const PRIORITY_CLS: Record<Priority, string> = {
  high: "border-danger/40 bg-danger-soft text-danger",
  medium: "border-warn/40 bg-warn-soft text-warn",
  low: "border-line bg-accent-soft text-accent",
  insufficient_data: "border-line bg-surface2 text-muted",
};

export function PriorityBadge({ priority }: { priority: Priority }) {
  return <span className={`${base} ${PRIORITY_CLS[priority]}`}>{PRIORITY_RU[priority]}</span>;
}

const FINDING_CLS: Record<FindingStatus, string> = {
  new: "border-line bg-surface2 text-muted",
  confirmed: "border-ok/40 bg-ok-soft text-ok",
  rejected: "border-danger/40 bg-danger-soft text-danger",
  reshoot: "border-warn/40 bg-warn-soft text-warn",
};

export function FindingStatusBadge({ status }: { status: FindingStatus }) {
  return <span className={`${base} ${FINDING_CLS[status]}`}>{FINDING_STATUS_RU[status]}</span>;
}

export function MockBadge() {
  return <span className={`${base} border-warn/50 bg-warn-soft text-warn`}>Макет</span>;
}
