import { describe, expect, it } from "vitest";
import { initialSidebarCollapsed } from "./layout";

describe("initial navigation layout", () => {
  it("uses compact navigation on a laptop without an explicit preference", () => {
    expect(initialSidebarCollapsed(null, 1024)).toBe(true);
    expect(initialSidebarCollapsed(null, 1279)).toBe(true);
    expect(initialSidebarCollapsed(null, 1280)).toBe(false);
    expect(initialSidebarCollapsed(null, 390)).toBe(false);
  });
  it("preserves either saved choice at every breakpoint", () => {
    expect(initialSidebarCollapsed("false", 1024)).toBe(false);
    expect(initialSidebarCollapsed("true", 1920)).toBe(true);
    expect(initialSidebarCollapsed("invalid", 1024)).toBe(true);
  });
});
