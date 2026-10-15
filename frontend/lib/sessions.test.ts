import { describe, expect, it } from "vitest";
import { describeDevice } from "./sessions";

describe("describeDevice", () => {
  it("names common browsers on their systems", () => {
    expect(
      describeDevice(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
      ),
    ).toBe("Chrome روی Windows");
    expect(
      describeDevice(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
      ),
    ).toBe("Safari روی macOS");
    expect(describeDevice("Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0")).toBe(
      "Firefox روی Linux",
    );
    expect(
      describeDevice(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/129.0 Mobile/15E148 Safari/604.1",
      ),
    ).toBe("Chrome روی iOS");
  });

  it("does not mistake Edge or Opera for Chrome", () => {
    const chromium = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36";
    expect(describeDevice(`${chromium} Edg/129.0`)).toBe("Edge روی Windows");
    expect(describeDevice(`${chromium} OPR/114.0`)).toBe("Opera روی Windows");
  });

  it("says so when it cannot tell", () => {
    expect(describeDevice("")).toBe("مرورگر ناشناخته");
    expect(describeDevice("curl/8.4.0")).toBe("مرورگر ناشناخته");
    expect(describeDevice("Something (Android 14)")).toBe("Android");
  });
});
