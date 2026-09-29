import { describe, expect, it } from "vitest";
import { documentFileLink, filenameFromDisposition } from "./file-link";

describe("documentFileLink", () => {
  it("is a page of this app, without a doubled slash", () => {
    expect(documentFileLink("http://localhost:3000", 12, 34)).toBe("http://localhost:3000/documents/12/files/34");
    expect(documentFileLink("https://veye.example/", "12", "34")).toBe("https://veye.example/documents/12/files/34");
  });
});

describe("filenameFromDisposition", () => {
  it("prefers the encoded Persian name", () => {
    const header = `attachment; filename="file.pdf"; filename*=utf-8''%D9%81%D8%B1%D9%85.pdf`;
    expect(filenameFromDisposition(header, "x")).toBe("فرم.pdf");
  });
  it("reads the plain form, quoted or not", () => {
    expect(filenameFromDisposition('attachment; filename="a b.pdf"', "x")).toBe("a b.pdf");
    expect(filenameFromDisposition("attachment; filename=a.pdf", "x")).toBe("a.pdf");
  });
  it("falls back when there is no header or no name", () => {
    expect(filenameFromDisposition(null, "پرونده")).toBe("پرونده");
    expect(filenameFromDisposition("inline", "پرونده")).toBe("پرونده");
  });
});
