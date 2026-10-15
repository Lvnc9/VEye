import { describe, expect, it } from "vitest";
import { DEFAULT_THEME, THEME_INIT_SCRIPT, parseThemeChoice, resolveTheme } from "./theme";

describe("theme choice", () => {
  it("defaults to light for anything unknown", () => {
    expect(DEFAULT_THEME).toBe("light");
    expect(parseThemeChoice(null)).toBe("light");
    expect(parseThemeChoice("blue")).toBe("light");
    expect(parseThemeChoice("dark")).toBe("dark");
    expect(parseThemeChoice("system")).toBe("system");
  });

  it("follows the system only when asked to", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });
});

/** Runs the inline script against a fake <html>, storage and media query. */
function runInitScript(stored: Record<string, string>, systemDark: boolean) {
  const classes = new Set<string>();
  const attrs: Record<string, string> = {};
  const root = {
    classList: { toggle: (name: string, on: boolean) => (on ? classes.add(name) : classes.delete(name)) },
    style: { colorScheme: "" },
    setAttribute: (name: string, value: string) => (attrs[name] = value),
  };
  const fn = new Function("document", "localStorage", "window", THEME_INIT_SCRIPT);
  fn(
    { documentElement: root },
    { getItem: (key: string) => stored[key] ?? null },
    { matchMedia: () => ({ matches: systemDark }) },
  );
  return { dark: classes.has("dark"), scheme: root.style.colorScheme, attrs };
}

describe("the inline script agrees with resolveTheme", () => {
  for (const stored of [undefined, "light", "dark", "system", "nonsense"]) {
    for (const systemDark of [false, true]) {
      it(`stored=${stored} systemDark=${systemDark}`, () => {
        const result = runInitScript(stored ? { "veye.theme": stored } : {}, systemDark);
        const expected = resolveTheme(parseThemeChoice(stored), systemDark);
        expect(result.dark).toBe(expected === "dark");
        expect(result.scheme).toBe(expected);
      });
    }
  }

  it("restores the collapsed sidebar", () => {
    expect(runInitScript({ "veye.sidebar": "collapsed" }, false).attrs["data-sidebar"]).toBe("collapsed");
    expect(runInitScript({}, false).attrs["data-sidebar"]).toBeUndefined();
  });

  it("survives blocked storage", () => {
    const fn = new Function("document", "localStorage", "window", THEME_INIT_SCRIPT);
    expect(() => fn({ documentElement: {} }, { getItem: () => { throw new Error("blocked"); } }, {})).not.toThrow();
  });
});
