/**
 * Copy text to the clipboard. `navigator.clipboard` exists only in a secure context (https or
 * localhost); an intranet served over plain http falls back to a hidden textarea and `execCommand`.
 * Resolves to whether the text was copied — never throws.
 */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Denied (permissions policy, unfocused document): try the fallback.
  }
  return legacyCopy(text);
}

function legacyCopy(text: string): boolean {
  if (typeof document === "undefined") return false;
  const field = document.createElement("textarea");
  field.value = text;
  field.setAttribute("readonly", "");
  field.style.position = "fixed";
  field.style.top = "0";
  field.style.opacity = "0";
  document.body.appendChild(field);
  const previous = document.activeElement as HTMLElement | null;
  try {
    field.select();
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    field.remove();
    previous?.focus?.();
  }
}
