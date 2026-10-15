import { describe, expect, it } from "vitest";
import {
  REASON_MAX_LENGTH,
  STEP_LABELS,
  signatureFormData,
  validateReason,
  validateWithdrawNote,
  workflowControls,
} from "./workflow";
import type { WorkflowState } from "./types";

const flow = (over: Partial<WorkflowState>): WorkflowState => ({
  step: "confirm",
  can_act: true,
  can_return: true,
  can_withdraw: false,
  ...over,
});

describe("workflowControls", () => {
  it("offers the step's button, and مرجوع only when the server says so", () => {
    expect(workflowControls(flow({}))).toEqual({
      primary: { step: "confirm", label: "تایید", disabled: false },
      canReturn: true,
      canWithdraw: false,
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
      canWithdraw: false,
    });
    expect(workflowControls(flow({ can_act: false, can_return: false })).primary).toBeNull();
  });

  it("shows the same person their own step however many steps they already took (no «blocked» state)", () => {
    expect(workflowControls(flow({ step: "confirm", can_act: true, can_return: true })).primary).toEqual({
      step: "confirm",
      label: "تایید",
      disabled: false,
    });
  });
});

describe("withdrawing (Phase 20)", () => {
  it("offers «بازپس‌گیری» to the submitter even with no step of their own to take", () => {
    expect(workflowControls(flow({ can_act: false, can_return: false, can_withdraw: true }))).toEqual({
      primary: null,
      canReturn: false,
      canWithdraw: true,
    });
  });

  it("keeps it beside the step when the submitter may also confirm", () => {
    const controls = workflowControls(flow({ can_withdraw: true }));
    expect(controls.primary?.step).toBe("confirm");
    expect(controls.canWithdraw).toBe(true);
  });

  it("takes an empty note but caps a long one", () => {
    expect(validateWithdrawNote("")).toBeNull();
    expect(validateWithdrawNote("x".repeat(REASON_MAX_LENGTH))).toBeNull();
    expect(validateWithdrawNote("x".repeat(REASON_MAX_LENGTH + 1))).not.toBeNull();
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
