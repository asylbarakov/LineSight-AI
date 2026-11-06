import { afterEach, expect, it, vi } from "vitest";
import { scrollToElement } from "./motion";
afterEach(() => vi.unstubAllGlobals());
it.each([true, false])("respects reduced motion = %s when revealing a selected finding", reduce => {
  vi.stubGlobal("window", { matchMedia: () => ({matches: reduce}) });
  const element = {scrollIntoView: vi.fn()};
  scrollToElement(element as unknown as Element);
  expect(element.scrollIntoView).toHaveBeenCalledWith({behavior: reduce ? "auto" : "smooth", block: "nearest"});
});
