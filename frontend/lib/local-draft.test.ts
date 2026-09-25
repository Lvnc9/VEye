import { describe, expect, it } from "vitest";
import { draftKey } from "./local-draft";

describe("draftKey", () => {
  it("builds veye:draft:<userId>:<projectId>:<purpose> without an objective", () => {
    expect(draftKey(7, 42, "note")).toBe("veye:draft:7:42:note");
  });

  it("appends the objective id when given", () => {
    expect(draftKey(7, 42, "objective-update", 9)).toBe("veye:draft:7:42:objective-update:9");
  });

  it("distinguishes purposes and objectives from each other", () => {
    expect(draftKey(7, 42, "note")).not.toBe(draftKey(7, 42, "meeting"));
    expect(draftKey(7, 42, "objective-update", 1)).not.toBe(draftKey(7, 42, "objective-update", 2));
  });

  it("distinguishes users and projects from each other, so one browser sharing several accounts never leaks a draft", () => {
    expect(draftKey(7, 42, "note")).not.toBe(draftKey(8, 42, "note"));
    expect(draftKey(7, 42, "note")).not.toBe(draftKey(7, 43, "note"));
  });
});
