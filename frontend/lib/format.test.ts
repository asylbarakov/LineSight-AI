import { describe, expect, it } from "vitest";
import { bboxToPixels, bboxToStyle, fmtPercent, fmtTimecode, frameName } from "./format";
import { errorText, typeRu } from "./texts";

describe("fmtTimecode", () => {
  it("форматирует секунды как мм:сс", () => {
    expect(fmtTimecode(0)).toBe("00:00");
    expect(fmtTimecode(73.4)).toBe("01:13");
    expect(fmtTimecode(600)).toBe("10:00");
  });
  it("отрицательные значения обрезает до нуля", () => {
    expect(fmtTimecode(-3)).toBe("00:00");
  });
});

describe("bbox", () => {
  const b = { x: 0.25, y: 0.5, w: 0.1, h: 0.2 };
  it("переводит доли в проценты", () => {
    expect(bboxToStyle(b)).toEqual({ left: "25.00%", top: "50.00%", width: "10.00%", height: "20.00%" });
  });
  it("переводит доли в пиксели", () => {
    expect(bboxToPixels(b, 1280, 720)).toEqual({ x: 320, y: 360, w: 128, h: 144 });
  });
  it("ограничивает значения диапазоном 0–1", () => {
    expect(bboxToStyle({ x: -1, y: 2, w: 0.5, h: 0.5 }).left).toBe("0.00%");
    expect(bboxToStyle({ x: -1, y: 2, w: 0.5, h: 0.5 }).top).toBe("100.00%");
  });
});

describe("тексты", () => {
  it("проценты и имя кадра", () => {
    expect(fmtPercent(0.914)).toBe("91%");
    expect(frameName("frames/lv_1.jpg")).toBe("lv_1.jpg");
  });
  it("каждый код ошибки имеет свой текст", () => {
    const codes = ["E_VIDEO_INVALID", "E_DECODE", "E_MODEL", "E_TIMEOUT"];
    const texts = codes.map((c) => errorText(c));
    expect(new Set(texts).size).toBe(4);
  });
  it("тип находки по-русски", () => {
    expect(typeRu("low_visibility")).toBe("Недостаточная видимость");
    expect(typeRu("Insulator")).toBe("Изолятор");
    expect(typeRu("bird_nest")).toBe("bird nest");
  });
});
