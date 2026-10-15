import { describe, expect, it } from "vitest";
import { cn } from "./utils";

describe("cn", () => {
  it("drops falsy parts", () => {
    expect(cn("a", false, null, undefined, "", "b")).toBe("a b");
  });

  it("lets a later class of the same kind win", () => {
    expect(cn("h-10 px-4", "h-8")).toBe("px-4 h-8");
    expect(cn("text-sm text-slate-700", "text-base")).toBe("text-slate-700 text-base");
  });

  it("knows our custom shadows, easings and animations", () => {
    expect(cn("shadow-card", "shadow-raised")).toBe("shadow-raised");
    expect(cn("shadow-xs", "shadow-overlay")).toBe("shadow-overlay");
    expect(cn("ease-out-quint", "ease-in-quart")).toBe("ease-in-quart");
    expect(cn("animate-fade-up", "animate-pop")).toBe("animate-pop");
  });

  it("knows our semantic colours", () => {
    expect(cn("bg-card", "bg-primary")).toBe("bg-primary");
    expect(cn("text-muted-foreground", "text-foreground")).toBe("text-foreground");
    expect(cn("border-border", "border-input")).toBe("border-input");
    expect(cn("bg-navy", "bg-navy-raised")).toBe("bg-navy-raised");
  });

  it("keeps a size and a colour side by side", () => {
    expect(cn("text-sm", "text-muted-foreground")).toBe("text-sm text-muted-foreground");
    expect(cn("shadow-card", "shadow-primary/20")).toBe("shadow-card shadow-primary/20");
  });
});
