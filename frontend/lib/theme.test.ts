import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { describe, expect, it, vi } from "vitest";
import { parseTheme, resolveTheme, THEME_INIT_SCRIPT, THEME_STORAGE_KEY } from "./theme";

describe("pre-paint theme initialization", () => {
  function bootstrap(saved: unknown, systemDark: boolean, blockedStorage = false, blockedMedia = false) {
    const setAttribute = vi.fn();
    const getItem = vi.fn(() => { if (blockedStorage) throw new Error("Storage denied"); return saved; });
    runInNewContext(THEME_INIT_SCRIPT, {
      localStorage: { getItem },
      window: { matchMedia: () => { if (blockedMedia) throw new Error("Media unavailable"); return { matches: systemDark }; } },
      document: { documentElement: { setAttribute } },
    });
    expect(getItem).toHaveBeenCalledWith(THEME_STORAGE_KEY);
    return setAttribute;
  }

  it.each([
    ["dark", false, "dark"], ["light", true, "light"],
    [null, true, "dark"], [null, false, "dark"],
    ["invalid", true, "dark"], ["<script>", false, "dark"],
  ])("applies saved=%s, systemDark=%s before React renders", (saved, systemDark, expected) => {
    const apply = bootstrap(saved, systemDark as boolean);
    expect(apply).toHaveBeenCalledTimes(1);
    expect(apply).toHaveBeenCalledWith("data-theme", expected);
  });

  it("defaults to dark even when localStorage throws", () => {
    expect(bootstrap(null, true, true)).toHaveBeenCalledWith("data-theme", "dark");
  });

  it("retains saved choice when matchMedia is unavailable", () => {
    expect(bootstrap("dark", false, false, true)).toHaveBeenCalledWith("data-theme", "dark");
  });

  it("still initializes safely when both browser APIs are unavailable", () => {
    expect(bootstrap(null, false, true, true)).toHaveBeenCalledWith("data-theme", "dark");
  });

  it("resolves removed/invalid preferences to dark and accepts only valid themes", () => {
    expect(resolveTheme(null, true)).toBe("dark");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("system", false)).toBe("dark");
    expect(parseTheme(undefined)).toBeNull();
    expect(parseTheme("DARK")).toBeNull();
  });
});

const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
function tokens(selector: string) {
  const start = css.indexOf(`${selector} {`);
  if (start < 0) throw new Error(`Missing theme selector: ${selector}`);
  const block = css.slice(start, css.indexOf("}", start));
  return Object.fromEntries([...block.matchAll(/--([\w-]+)-rgb:\s*([\d ]+);/g)]
    .map((match) => [match[1], match[2].trim().split(/\s+/).map(Number)]));
}
const dark = tokens(":root");
const palettes = { dark, light: { ...dark, ...tokens(':root[data-theme="light"]') } };

function luminance(rgb: number[]) {
  const values = rgb.map((channel) => {
    const value = channel / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
}
function contrast(a: number[], b: number[]) {
  const first = luminance(a), second = luminance(b);
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}

describe("theme accessibility", () => {
  it("keeps readable chart data above 3:1 against every panel surface", () => {
    for (const palette of Object.values(palettes)) {
      expect(contrast(palette.chart, palette.surface)).toBeGreaterThanOrEqual(3);
    }
  });

  for (const [name, palette] of Object.entries(palettes)) {
    it(`${name}: text, priority and status colors meet 4.5:1 on every UI surface`, () => {
      for (const foreground of ["fg", "muted", "accent", "ok", "warn", "danger"]) {
        for (const background of ["bg", "surface", "surface-2", "field"]) {
          expect(contrast(palette[foreground], palette[background]), `${foreground} on ${background}`).toBeGreaterThanOrEqual(4.5);
        }
      }
    });

    it(`${name}: buttons, badges, toasts and active navigation meet 4.5:1`, () => {
      expect(contrast(palette["accent-fg"], palette.accent)).toBeGreaterThanOrEqual(4.5);
      for (const color of ["accent", "ok", "warn", "danger"]) {
        expect(contrast(palette[color], palette[`${color}-soft`]), `${color} on soft background`).toBeGreaterThanOrEqual(4.5);
      }
    });

    it(`${name}: field boundaries, focus and finding markers meet 3:1`, () => {
      expect(contrast(palette.control, palette.field)).toBeGreaterThanOrEqual(3);
      for (const background of ["bg", "surface", "surface-2"]) {
        for (const indicator of ["accent", "danger", "warn", "ok", "muted"]) {
          expect(contrast(palette[indicator], palette[background]), `${indicator} on ${background}`).toBeGreaterThanOrEqual(3);
        }
      }
    });

    it(`${name}: sidebar labels remain readable on normal and selected navigation`, () => {
      for (const foreground of ["sidebar-fg", "sidebar-muted"]) {
        for (const background of ["sidebar", "sidebar-active"]) {
          expect(contrast(palette[foreground], palette[background]), `${foreground} on ${background}`).toBeGreaterThanOrEqual(4.5);
        }
      }
    });
  }
});
