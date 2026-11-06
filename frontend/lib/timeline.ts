import { fmtTimecode } from "./format";
import type { Finding } from "./types";

export function isVideoDuration(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

/** Keep fractional API timestamps visible; seeking always uses the original number. */
export function findingTimecode(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  const milliseconds = Math.round(seconds * 1000);
  const fraction = String(milliseconds % 1000).padStart(3, "0").replace(/0+$/, "");
  return `${fmtTimecode(Math.floor(milliseconds / 1000))}${fraction ? `.${fraction}` : ""}`;
}

export interface TimelineMarker {
  finding: Finding;
  percent: number;
  lane: number;
}

/** Separate nearby markers vertically, without shifting their actual time positions. */
export function layoutFindingMarkers(findings: Finding[], duration: number, width: number): TimelineMarker[] {
  if (!isVideoDuration(duration) || !Number.isFinite(width) || width <= 0) return [];
  const laneEnds: number[] = [];
  return findings
    .filter((f) => Number.isFinite(f.timecode_sec) && f.timecode_sec >= 0 && f.timecode_sec <= duration)
    .slice()
    .sort((a, b) => a.timecode_sec - b.timecode_sec || a.id.localeCompare(b.id))
    .map((finding) => {
      const percent = (finding.timecode_sec / duration) * 100;
      const x = (percent / 100) * width;
      let lane = laneEnds.findIndex((end) => x - end >= 28);
      if (lane === -1) lane = laneEnds.length;
      laneEnds[lane] = x;
      return { finding, percent, lane };
    });
}

export function findingMarkerStyle(finding: Pick<Finding, "type" | "priority">) {
  const insufficient = finding.type === "low_visibility" || finding.priority === "insufficient_data";
  return {
    insufficient,
    color: insufficient ? "var(--muted)" : {
      high: "var(--danger)", medium: "var(--warn)", low: "var(--accent)", insufficient_data: "var(--muted)",
    }[finding.priority],
  };
}

/** Pixel-based clustering adapts to the actual track width; original times are never rounded. */
export function groupTimelineFindings(findings: Finding[], duration: number, width: number) {
  if (!isVideoDuration(duration) || !Number.isFinite(width) || width <= 0) return [];
  const groups: { percent: number; findings: Finding[] }[] = [];
  const ordered = findings.filter(f => Number.isFinite(f.timecode_sec) && f.timecode_sec >= 0 && f.timecode_sec <= duration)
    .slice().sort((a, b) => a.timecode_sec - b.timecode_sec || a.id.localeCompare(b.id));
  for (const finding of ordered) {
    const percent = finding.timecode_sec / duration * 100;
    const previous = groups[groups.length - 1];
    if (previous && (percent - previous.percent) / 100 * width < 44) previous.findings.push(finding);
    else groups.push({ percent, findings: [finding] });
  }
  return groups;
}
