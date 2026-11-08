export type ScanOffset = {x: number; y: number};
export function lineScanOffset(x: number, y: number, box: {left: number; top: number; width: number; height: number}, enabled: boolean): ScanOffset {
  if (!enabled || !Number.isFinite(x + y) || box.width <= 0 || box.height <= 0) return {x: 0, y: 0};
  const clamp = (value: number) => Math.max(-1, Math.min(1, value));
  return {x: clamp((x - box.left) / box.width * 2 - 1) * 5, y: clamp((y - box.top) / box.height * 2 - 1) * 3};
}

export function cablePaths(offset: ScanOffset) {
  return [[305, 316, 650.5, 484.1], [325, 406, 643.5, 515.6], [105, 406, 713.5, 515.6]].map(([x1,y1,x2,y2]) => {
    const start = {x: x1 + offset.x, y: y1 + offset.y};
    const end = {x: x2 + offset.x * .4, y: y2 + offset.y * .4};
    const n = (value: number) => value.toFixed(2);
    return `M${n(start.x)} ${n(start.y)} Q${n((start.x + end.x) / 2)} ${n((start.y + end.y) / 2 + 100)} ${n(end.x)} ${n(end.y)}`;
  });
}

export function smoothScanOffset(current: ScanOffset, target: ScanOffset, milliseconds: number): ScanOffset {
  const mix = 1 - Math.exp(-Math.max(0, milliseconds) / 85);
  return {x: current.x + (target.x - current.x) * mix, y: current.y + (target.y - current.y) * mix};
}
