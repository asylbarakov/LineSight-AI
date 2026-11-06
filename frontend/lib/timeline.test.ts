import { describe, expect, it } from "vitest";
import type { Finding } from "./types";
import { findingMarkerStyle, findingTimecode, isVideoDuration, layoutFindingMarkers } from "./timeline";

const finding = (id: string, timecode_sec: number): Finding => ({
  id, timecode_sec, type: "insulator", priority: "high", confidence: 0.9,
  frame_path: null, bbox: null, status: "new",
});

describe("finding timeline", () => {
  it("positions start, fractional timestamps and end using video duration", () => {
    const markers = layoutFindingMarkers([finding("start", 0), finding("mid", 12.375), finding("end", 30)], 30, 600);
    expect(markers.map((m) => m.percent)).toEqual([0, 41.25, 100]);
    expect(markers[1].finding.timecode_sec).toBe(12.375);
  });

  it("keeps identical timestamps individually reachable in distinct lanes", () => {
    const markers = layoutFindingMarkers([finding("b", 5), finding("a", 5), finding("c", 5)], 10, 500);
    expect(markers.map((m) => [m.finding.id, m.percent, m.lane])).toEqual([
      ["a", 50, 0], ["b", 50, 1], ["c", 50, 2],
    ]);
  });

  it("reflows close findings on narrow screens without moving their timestamps", () => {
    const input = [finding("a", 1), finding("b", 2)];
    const wide = layoutFindingMarkers(input, 10, 600);
    const narrow = layoutFindingMarkers(input, 10, 100);
    expect(wide.map((m) => m.lane)).toEqual([0, 0]);
    expect(narrow.map((m) => m.lane)).toEqual([0, 1]);
    expect(narrow.map((m) => m.percent)).toEqual(wide.map((m) => m.percent));
  });

  it("reuses a lane once there is enough space", () => {
    expect(layoutFindingMarkers([finding("a", 1), finding("b", 1), finding("c", 9)], 10, 100)
      .map((m) => m.lane)).toEqual([0, 1, 0]);
  });

  it.each([0, -1, NaN, Infinity])("does not place markers against invalid duration %s", (duration) => {
    expect(isVideoDuration(duration)).toBe(false);
    expect(layoutFindingMarkers([finding("a", 1)], duration, 100)).toEqual([]);
  });

  it("handles loading dimensions, empty findings and invalid/out-of-range timestamps", () => {
    expect(layoutFindingMarkers([finding("a", 1)], 10, 0)).toEqual([]);
    expect(layoutFindingMarkers([], 10, 100)).toEqual([]);
    expect(layoutFindingMarkers([finding("a", -1), finding("b", NaN), finding("c", 11), finding("d", 3)], 10, 100)
      .map((m) => m.finding.id)).toEqual(["d"]);
  });

  it("does not reorder API data", () => {
    const input = [finding("later", 8), finding("earlier", 2)];
    layoutFindingMarkers(input, 10, 100);
    expect(input.map((f) => f.id)).toEqual(["later", "earlier"]);
  });

  it("distinguishes visibility and insufficient data from priority colors", () => {
    expect(findingMarkerStyle({ type: "low_visibility", priority: "high" }).insufficient).toBe(true);
    expect(findingMarkerStyle({ type: "insulator", priority: "insufficient_data" }).insufficient).toBe(true);
    const colors = ["high", "medium", "low"].map((priority) =>
      findingMarkerStyle({ type: "insulator", priority: priority as Finding["priority"] }).color);
    expect(new Set(colors).size).toBe(3);
  });

  it("shows fractional timestamps without rounding the actual seek target", () => {
    expect(findingTimecode(12.375)).toBe("00:12.375");
    expect(findingTimecode(73.4)).toBe("01:13.4");
    expect(findingTimecode(59.9999)).toBe("01:00");
    expect(findingTimecode(0)).toBe("00:00");
    expect(findingTimecode(NaN)).toBe("—");
  });
});
