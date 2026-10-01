import { describe, expect, it } from "vitest";
import { notificationHref, type Notification } from "./notifications";

function make(overrides: Partial<Notification> = {}): Notification {
  return {
    id: 1,
    kind: "document_approved",
    kind_label: "مستند تصویب و ابلاغ شد",
    title: "«PO-01-01» تصویب و ابلاغ شد",
    body: "",
    url: "",
    created_at: "2026-10-01T06:00:00Z",
    read_at: null,
    is_read: false,
    ...overrides,
  };
}

describe("notificationHref", () => {
  it("goes to the server's url when there is one", () => {
    expect(notificationHref(make({ url: "/documents/42/edit" }))).toBe("/documents/42/edit");
  });

  it("falls back to the dashboard when there is nowhere to go", () => {
    expect(notificationHref(make({ url: "" }))).toBe("/dashboard");
  });
});
