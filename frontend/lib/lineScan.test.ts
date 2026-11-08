import { expect, it } from "vitest";
import { cablePaths, lineScanOffset, smoothScanOffset } from "./lineScan";

it("bounds parallax depth and keeps touch/reduced-motion coordinates stationary", () => {
  const box = {left: 0, top: 0, width: 640, height: 440};
  expect(lineScanOffset(320, 220, box, true)).toEqual({x: 0, y: 0});
  expect(lineScanOffset(900, -90, box, true)).toEqual({x: 5, y: -3});
  expect(lineScanOffset(900, 440, box, false)).toEqual({x: 0, y: 0});
  expect(lineScanOffset(NaN, 0, box, true)).toEqual({x: 0, y: 0});
});
it("keeps sagging cable endpoints connected to both parallax layers", () => {
  expect(cablePaths({x: 0, y: 0})[0]).toBe("M305.00 316.00 Q477.75 500.05 650.50 484.10");
  expect(cablePaths({x: 5, y: -3})[0]).toBe("M310.00 313.00 Q481.25 497.95 652.50 482.90");
  expect(cablePaths({x: 0, y: 0})).toHaveLength(3);
});
it("interpolates toward the pointer without overshoot or frame-rate dependence", () => {
  const target = {x: 5, y: -3};
  const first = smoothScanOffset({x: 0, y: 0}, target, 16);
  expect(first.x).toBeGreaterThan(0); expect(first.x).toBeLessThan(5);
  const twice = smoothScanOffset(first, target, 16);
  expect(twice.x).toBeCloseTo(smoothScanOffset({x: 0, y: 0}, target, 32).x);
  expect(smoothScanOffset(target, target, 16)).toEqual(target);
});
