import { describe, expect, it } from "vitest";
import { COALESCE_MS, LIMIT, emptyHistory, record, redo, undo } from "./undo-history";

describe("history", () => {
  it("undoes and redoes one step at a time", () => {
    let h = emptyHistory<string>();
    h = record(h, "a", 1000); // a → b
    h = record(h, "b", 5000); // b → c
    const first = undo(h, "c")!;
    expect(first.state).toBe("b");
    const second = undo(first.history, first.state)!;
    expect(second.state).toBe("a");
    expect(undo(second.history, second.state)).toBeNull();
    const again = redo(second.history, second.state)!;
    expect(again.state).toBe("b");
    expect(redo(again.history, again.state)!.state).toBe("c");
  });

  it("coalesces a burst of changes into one step", () => {
    let h = emptyHistory<string>();
    h = record(h, "a", 1000);
    h = record(h, "ab", 1000 + COALESCE_MS - 1);
    h = record(h, "abc", 1000 + 2 * (COALESCE_MS - 1));
    expect(h.past).toEqual(["a"]);
    expect(undo(h, "abcd")!.state).toBe("a");
  });

  it("a pause starts a new step", () => {
    let h = emptyHistory<string>();
    h = record(h, "a", 1000);
    h = record(h, "ab", 1000 + COALESCE_MS + 1);
    expect(h.past).toEqual(["a", "ab"]);
  });

  it("a new change after an undo drops the redo branch and starts its own step", () => {
    let h = emptyHistory<string>();
    h = record(h, "a", 1000);
    const back = undo(h, "b")!; // current is a again, b can be redone
    expect(back.history.future).toEqual(["b"]);
    const branched = record(back.history, "a", 1100); // within the window, but right after an undo
    expect(branched.future).toEqual([]);
    expect(branched.past).toEqual(["a"]);
  });

  it("keeps at most LIMIT steps", () => {
    let h = emptyHistory<number>();
    for (let i = 0; i < LIMIT + 10; i += 1) h = record(h, i, 1000 * (i + 1));
    expect(h.past).toHaveLength(LIMIT);
    expect(h.past[0]).toBe(10);
  });
});
