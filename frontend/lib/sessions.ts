/**
 * «ورودهای اخیر» (Phase 20): `GET /auth/sessions/` and a short, readable name for the browser that
 * signed in. Pure — relative imports only, so vitest can load it.
 */

export interface LoginEvent {
  id: number;
  succeeded: boolean;
  ip: string | null;
  user_agent: string;
  created_at: string;
}

export interface SessionsResponse {
  events: LoginEvent[];
  history_days: number;
}

// Order matters: Edge and Opera say "Chrome" too, and Chrome says "Safari".
const BROWSERS: [RegExp, string][] = [
  [/Edg(e|A|iOS)?\//, "Edge"],
  [/OPR\/|Opera/, "Opera"],
  [/Firefox\/|FxiOS\//, "Firefox"],
  [/Chrome\/|CriOS\//, "Chrome"],
  [/Safari\//, "Safari"],
];

const SYSTEMS: [RegExp, string][] = [
  [/Android/, "Android"],
  [/iPhone|iPad|iPod/, "iOS"],
  [/Windows/, "Windows"],
  [/Mac OS X|Macintosh/, "macOS"],
  [/Linux/, "Linux"],
];

/** "Chrome روی Windows"; the parts it cannot tell are left out, and nothing at all reads «مرورگر ناشناخته». */
export function describeDevice(userAgent: string): string {
  const browser = BROWSERS.find(([pattern]) => pattern.test(userAgent))?.[1];
  const system = SYSTEMS.find(([pattern]) => pattern.test(userAgent))?.[1];
  if (browser && system) return `${browser} روی ${system}`;
  return browser ?? system ?? "مرورگر ناشناخته";
}
