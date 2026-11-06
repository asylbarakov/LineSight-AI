import { describe, expect, it } from "vitest";
import { groupTimelineFindings } from "./timeline";
import { replaceFinding, rollbackFinding } from "./review";
import type { Finding } from "./types";

const finding = (id: string, time: number, status: Finding["status"] = "new"): Finding => ({
  id, timecode_sec: time, status, type: "insulator_damage", priority: "high", confidence: .8, frame_path: null, bbox: null,
});

describe("responsive timeline groups", () => {
  it("keeps every original fractional timestamp and selects a member of an overlap group", () => {
    const source = [finding("a", 10.125), finding("b", 10.126), finding("c", 80)];
    const groups = groupTimelineFindings(source, 100, 500);
    expect(groups.map(g => g.findings.map(f => f.id))).toEqual([["a", "b"], ["c"]]);
    expect(groups[0].percent).toBe(10.125);
    expect(groups[0].findings[1].timecode_sec).toBe(10.126);
    expect(source.map(f => f.id)).toEqual(["a", "b", "c"]);
  });
  it("regroups on narrow tracks and excludes invalid times without clamping", () => {
    const rows = [finding("a", 0), finding("b", 10), finding("c", 100), finding("d", 101), finding("e", NaN)];
    expect(groupTimelineFindings(rows, 100, 600)).toHaveLength(3);
    expect(groupTimelineFindings(rows, 100, 200).map(g => g.findings.length)).toEqual([2, 1]);
    expect(groupTimelineFindings(rows, 0, 200)).toEqual([]);
  });
});

describe("concurrent engineer decisions", () => {
  it("rolls back only the failed decision, preserving a different successful decision", () => {
    const a = finding("a", 1), b = finding("b", 2);
    const optimistic = replaceFinding(replaceFinding([a, b], {...a, status: "confirmed"}), {...b, status: "reshoot"});
    const saved = replaceFinding(optimistic, {...b, status: "reshoot", confidence: .9});
    expect(rollbackFinding(saved, a, "confirmed")).toEqual([a, {...b, status: "reshoot", confidence: .9}]);
  });
  it("does not overwrite a newer decision when an older request fails", () => {
    const previous = finding("a", 1);
    const latest = {...previous, status: "rejected" as const};
    expect(rollbackFinding([latest], previous, "confirmed")).toEqual([latest]);
  });
});
