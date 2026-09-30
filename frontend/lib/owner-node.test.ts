import { describe, expect, it } from "vitest";
import { defaultOwnerNode, ownerNodeText, type OwnerNodeChoice } from "./owner-node";

const choice = (id: number, kind_label: string, label: string, depth = 1): OwnerNodeChoice => ({
  id, name: label.split(" › ").pop() ?? label, kind: "UNIT", kind_label, depth, label,
});

const choices = [choice(1, "واحد", "IT › هوش مصنوعی"), choice(2, "بخش", "IT › هوش مصنوعی › RAG"), choice(3, "بخش", "IT › هوش مصنوعی › LLM")];

describe("defaultOwnerNode", () => {
  it("starts on a node the person leads, the first in chart order", () => {
    expect(defaultOwnerNode(choices, [{ node: 3, is_lead: true }, { node: 2, is_lead: true }])).toBe(2);
  });

  it("ignores a membership that is not a lead", () => {
    expect(defaultOwnerNode(choices, [{ node: 2, is_lead: false }])).toBeNull();
  });

  it("ignores a led node the person may not pick (archived, say)", () => {
    expect(defaultOwnerNode(choices, [{ node: 99, is_lead: true }])).toBeNull();
  });

  it("takes the only choice when there is just one", () => {
    expect(defaultOwnerNode([choices[0]], [])).toBe(1);
    expect(defaultOwnerNode([choices[0]], undefined)).toBe(1);
  });

  it("leaves the choice to the person when there are several and none is theirs, or none at all", () => {
    expect(defaultOwnerNode(choices, undefined)).toBeNull();
    expect(defaultOwnerNode([], [{ node: 1, is_lead: true }])).toBeNull();
  });
});

describe("ownerNodeText", () => {
  it("says the kind, then the path", () => {
    expect(ownerNodeText(choices[1])).toBe("بخش · IT › هوش مصنوعی › RAG");
  });
});
