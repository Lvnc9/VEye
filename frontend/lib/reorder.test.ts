import { describe, expect, it } from "vitest";
import { dropIndex, insertAfter, moveElement } from "./reorder";

describe("reordering", () => {
  const list = ["a", "b", "c", "d"];

  it("moves an item to an index", () => {
    expect(moveElement(list, 0, 2)).toEqual(["b", "c", "a", "d"]);
    expect(moveElement(list, 3, 0)).toEqual(["d", "a", "b", "c"]);
    expect(moveElement(list, 1, 1)).toBe(list);
    expect(moveElement(list, 1, 99)).toEqual(["a", "c", "d", "b"]);
    expect(moveElement(list, 7, 0)).toBe(list);
  });

  it("turns a drop before/after a row into the right index", () => {
    const drop = (from: number, over: number, after: boolean) => moveElement(list, from, dropIndex(from, over, after));
    expect(drop(0, 2, false)).toEqual(["b", "a", "c", "d"]); // a before c
    expect(drop(0, 2, true)).toEqual(["b", "c", "a", "d"]); // a after c
    expect(drop(3, 0, false)).toEqual(["d", "a", "b", "c"]); // d before a
    expect(drop(3, 1, true)).toEqual(["a", "b", "d", "c"]); // d after b
    expect(drop(2, 2, false)).toEqual(list); // onto itself
    expect(drop(2, 2, true)).toEqual(list);
    expect(drop(1, 0, true)).toEqual(list); // b after a: where it already is
  });

  it("inserts after an index, at the start, or at the end", () => {
    expect(insertAfter(list, "x", 1)).toEqual(["a", "b", "x", "c", "d"]);
    expect(insertAfter(list, "x", -1)).toEqual(["x", "a", "b", "c", "d"]);
    expect(insertAfter(list, "x", 10)).toEqual(["a", "b", "c", "d", "x"]);
  });
});
