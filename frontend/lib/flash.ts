/**
 * A one-shot message that survives a client-side navigation: the designer saves a
 * document and returns to the register, which then says so («مستند … ذخیره شد»).
 *
 * sessionStorage (not a query string) keeps the URL clean and the message from
 * being replayed on refresh or a shared link; every access is guarded because
 * storage can be blocked, and the message is a nicety — never let it break a page.
 */
const KEY = "veye:flash";

export function setFlash(message: string): void {
  try {
    window.sessionStorage.setItem(KEY, message);
  } catch {
    /* storage unavailable: the navigation still happens, just without the message */
  }
}

/** The pending message, removed as it is read (so it shows exactly once). */
export function takeFlash(): string | null {
  try {
    const message = window.sessionStorage.getItem(KEY);
    if (message !== null) window.sessionStorage.removeItem(KEY);
    return message;
  } catch {
    return null;
  }
}
