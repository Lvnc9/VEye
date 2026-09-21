/**
 * Login page helpers: where to go after signing in, and how a national code is typed.
 * Pure functions, no fetching — relative imports only (vitest has no `@/` alias).
 */

export const DEFAULT_AFTER_LOGIN = "/dashboard";

/** Pages that must never be the destination of a login (they would just bounce back). */
const NEVER_RETURN_TO = new Set(["/login"]);

// Backslashes are treated as slashes by browsers ("/\evil.example" == "//evil.example"), and
// control characters are stripped by URL parsers — either can turn a "path" into a host.
const UNSAFE_CHARACTERS = /[\\\x00-\x1f\x7f]/;

/**
 * The `?next=` that proxy.ts adds when it bounces an anonymous visitor to /login — but only if it
 * is a plain path *inside this app*. Anything else (`//evil.example`, `https://…`, `/\evil`, a
 * `javascript:` URL, control characters) falls back to the dashboard: an open redirect on a login
 * page is a phishing gift.
 */
export function safeNextPath(raw: string | null | undefined): string {
  if (!raw || typeof raw !== "string") return DEFAULT_AFTER_LOGIN;
  if (!raw.startsWith("/") || raw.startsWith("//")) return DEFAULT_AFTER_LOGIN;
  if (UNSAFE_CHARACTERS.test(raw)) return DEFAULT_AFTER_LOGIN;

  let parsed: URL;
  try {
    parsed = new URL(raw, "http://veye.invalid");
  } catch {
    return DEFAULT_AFTER_LOGIN;
  }
  if (parsed.origin !== "http://veye.invalid") return DEFAULT_AFTER_LOGIN;
  if (NEVER_RETURN_TO.has(parsed.pathname)) return DEFAULT_AFTER_LOGIN;
  return parsed.pathname + parsed.search + parsed.hash;
}

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩";

/** Persian (۰-۹) and Arabic-Indic (٠-٩) digits → ASCII, everything else untouched. */
export function normalizeDigits(text: string): string {
  return text.replace(/[۰-۹٠-٩]/g, (ch) => {
    const persian = PERSIAN_DIGITS.indexOf(ch);
    return String(persian >= 0 ? persian : ARABIC_INDIC_DIGITS.indexOf(ch));
  });
}

/**
 * A national code as the server stores it: ASCII digits, no whitespace. The setup wizard creates
 * the first account this way (backend `to_latin_digits`), so someone typing on a Persian keyboard
 * must be able to sign in with it.
 */
export function normalizeNationalCode(text: string): string {
  return normalizeDigits(text).replace(/\s+/g, "");
}
