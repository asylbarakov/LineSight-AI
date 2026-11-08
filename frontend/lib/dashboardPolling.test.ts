import { afterEach, expect, it, vi } from "vitest";
import * as dashboard from "./dashboard";

afterEach(() => vi.useRealTimers());
const start = (load: () => Promise<boolean>, visible = () => true) => {
  const fn = (dashboard as unknown as {startDashboardPolling?: (load: () => Promise<boolean>, visible: () => boolean) => {refresh: () => void; stop: () => void}}).startDashboardPolling;
  expect(fn).toBeTypeOf("function");
  return fn!(load, visible);
};
it("polls delayed processing at five seconds and idle data at thirty", async () => {
  vi.useFakeTimers(); let calls = 0;
  const p = start(async () => ++calls === 1);
  await vi.advanceTimersByTimeAsync(0); expect(calls).toBe(1);
  await vi.advanceTimersByTimeAsync(5000); expect(calls).toBe(2);
  await vi.advanceTimersByTimeAsync(29999); expect(calls).toBe(2);
  await vi.advanceTimersByTimeAsync(1); expect(calls).toBe(3); p.stop();
});
it("coalesces mutation/focus refreshes during an in-flight request and stops timers", async () => {
  vi.useFakeTimers(); let calls = 0; let release!: () => void;
  const pending = new Promise<void>(r => { release = r; });
  const p = start(async () => { calls++; if(calls === 1) await pending; return false; });
  p.refresh(); p.refresh(); expect(calls).toBe(1);
  release(); await vi.advanceTimersByTimeAsync(0); expect(calls).toBe(2);
  p.stop(); await vi.advanceTimersByTimeAsync(60000); expect(calls).toBe(2);
});
it("skips hidden tabs and recovers after failed requests", async () => {
  vi.useFakeTimers(); let visible = false, calls = 0;
  const p = start(async () => { if(++calls === 1) throw Error("offline"); return false; }, () => visible);
  await vi.advanceTimersByTimeAsync(30000); expect(calls).toBe(0);
  visible = true; p.refresh(); await vi.advanceTimersByTimeAsync(0); expect(calls).toBe(1);
  await vi.advanceTimersByTimeAsync(5000); expect(calls).toBe(2); p.stop();
});
