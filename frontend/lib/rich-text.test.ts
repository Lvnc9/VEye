import { describe, expect, it } from "vitest";
import { MARKERS, applyStyle, parseMarkers, type Style } from "./rich-text";

/** Apply `style` to the substring `sel` of `text` (first occurrence). */
function run(text: string, sel: string, style: Style) {
  const start = text.indexOf(sel);
  if (start < 0) throw new Error(`"${sel}" not in "${text}"`);
  return applyStyle(text, start, start + sel.length, style);
}

describe("markers", () => {
  it("are the ones V_1.0's editor and the PDF renderer both use", () => {
    // to_make_pdf.py:458-541 parses exactly these three.
    expect(MARKERS).toEqual({ bold: "**", italic: "~~", underline: "--" });
  });
});

describe("applyStyle — wrapping", () => {
  it("wraps the selection and keeps it on the inner text", () => {
    const result = run("سلام دنیا", "دنیا", "bold");
    expect(result.error).toBeUndefined();
    expect(result.text).toBe("سلام **دنیا**");
    expect(result.text.slice(result.selStart, result.selEnd)).toBe("دنیا");
  });

  it("supports all three styles", () => {
    expect(run("a b", "b", "italic").text).toBe("a ~~b~~");
    expect(run("a b", "b", "underline").text).toBe("a --b--");
  });

  it("does nothing without a selection (as in V_1.0)", () => {
    const result = applyStyle("abc", 1, 1, "bold");
    expect(result.text).toBe("abc");
    expect(result.error).toBeUndefined();
  });

  it("preserves surrounding whitespace and newlines exactly", () => {
    const result = run("  خط اول\n\nخط دوم  ", "خط دوم", "bold");
    expect(result.text).toBe("  خط اول\n\n**خط دوم**  ");
  });
});

describe("applyStyle — toggling off", () => {
  it("unwraps when the markers sit just outside the selection", () => {
    // The state right after wrapping: selection is on the inner text.
    const wrapped = run("سلام دنیا", "دنیا", "bold");
    const undone = applyStyle(wrapped.text, wrapped.selStart, wrapped.selEnd, "bold");
    expect(undone.text).toBe("سلام دنیا");
    expect(undone.text.slice(undone.selStart, undone.selEnd)).toBe("دنیا");
  });

  it("unwraps when the selection includes the markers", () => {
    const result = run("سلام **دنیا**", "**دنیا**", "bold");
    expect(result.text).toBe("سلام دنیا");
    expect(result.text.slice(result.selStart, result.selEnd)).toBe("دنیا");
  });

  it("is a round trip", () => {
    const text = "قبل بعد";
    const wrapped = run(text, "قبل", "underline");
    const undone = applyStyle(wrapped.text, wrapped.selStart, wrapped.selEnd, "underline");
    expect(undone.text).toBe(text);
  });
});

describe("applyStyle — one style at a time", () => {
  it("replaces a different style on an exactly-wrapped selection", () => {
    const result = run("a **b** c", "**b**", "italic");
    expect(result.error).toBeUndefined();
    expect(result.text).toBe("a ~~b~~ c");
  });

  it("strips stray markers inside the selection before wrapping", () => {
    const result = run("x **a** y ~~b~~ z", "**a** y ~~b~~", "underline");
    expect(result.text).toBe("x --a y b-- z");
  });

  it("refuses to nest a style inside another, because the PDF parser cannot", () => {
    // parseMarkers (and the renderer's regex) match non-greedily per marker,
    // so "**hello ~~world~~**" would print the tildes literally.
    const text = "**hello world**";
    const result = run(text, "world", "italic");
    expect(result.text).toBe(text);
    expect(result.error).toBe("inside-style");
  });

  it("also refuses to re-apply the same style to part of an existing region", () => {
    const text = "**hello world**";
    const result = run(text, "world", "bold");
    expect(result.text).toBe(text);
    expect(result.error).toBe("inside-style");
  });

  it("allows styling text after a closed region", () => {
    const result = run("**a** b", "b", "italic");
    expect(result.error).toBeUndefined();
    expect(result.text).toBe("**a** ~~b~~");
  });
});

describe("parseMarkers", () => {
  it("splits text into styled runs the way the PDF renderer does", () => {
    expect(parseMarkers("a **b** c ~~d~~ e --f-- g")).toEqual([
      { text: "a " },
      { text: "b", style: "bold" },
      { text: " c " },
      { text: "d", style: "italic" },
      { text: " e " },
      { text: "f", style: "underline" },
      { text: " g" },
    ]);
  });

  it("leaves unmatched markers as literal text", () => {
    expect(parseMarkers("half **open")).toEqual([{ text: "half **open" }]);
  });

  it("returns a single plain run when there is nothing to parse", () => {
    expect(parseMarkers("plain")).toEqual([{ text: "plain" }]);
    expect(parseMarkers("")).toEqual([]);
  });
});
