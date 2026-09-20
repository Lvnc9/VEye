import { describe, expect, it } from "vitest";
import {
  REASON_MAX_LENGTH,
  STEP_LABELS,
  signatureFormData,
  validateReason,
  workflowControls,
} from "./workflow";
import type { WorkflowState } from "./types";

const flow = (over: Partial<WorkflowState>): WorkflowState => ({
  step: "confirm",
  can_act: true,
  can_return: true,
  blocked: null,
  ...over,
});

describe("workflowControls", () => {
  it("offers the step's button, and مرجوع only when the server says so", () => {
    expect(workflowControls(flow({}))).toEqual({
      primary: { step: "confirm", label: "تایید", disabled: false },
      canReturn: true,
    });
    expect(workflowControls(flow({ step: "submit", can_return: false })).canReturn).toBe(false);
  });

  it("labels the three steps", () => {
    expect(STEP_LABELS).toEqual({ submit: "ارسال برای تایید", confirm: "تایید", approve: "تصویب" });
  });

  it("shows nothing when there is no step, or the user is not involved", () => {
    expect(workflowControls(flow({ step: null, can_act: false, can_return: false }))).toEqual({
      primary: null,
      canReturn: false,
    });
    expect(workflowControls(flow({ can_act: false, can_return: false })).primary).toBeNull();
  });

  it("shows a disabled button carrying the reason to a barred earlier signer, and no مرجوع", () => {
    const reason = "شما تدوین‌کننده این مستند هستید و نمی‌توانید آن را تایید کنید.";
    expect(workflowControls(flow({ can_act: false, can_return: false, blocked: reason }))).toEqual({
      primary: { step: "confirm", label: "تایید", disabled: true, title: reason },
      canReturn: false,
    });
  });
});

describe("validateReason", () => {
  it("requires a reason", () => {
    expect(validateReason("")).toMatch(/دلیل/);
    expect(validateReason("   \n ")).toMatch(/دلیل/);
    expect(validateReason("بند ۲ اصلاح شود")).toBeNull();
  });

  it("caps its length at the server's limit", () => {
    expect(validateReason("x".repeat(REASON_MAX_LENGTH))).toBeNull();
    expect(validateReason("x".repeat(REASON_MAX_LENGTH + 1))).toMatch(/بیش از/);
  });
});

describe("signatureFormData", () => {
  it("sends only the image — identity comes from the session", () => {
    const form = signatureFormData(new Blob(["x"], { type: "image/png" }));
    expect([...form.keys()]).toEqual(["signature"]);
    expect((form.get("signature") as File).name).toBe("signature.png");
  });
});
