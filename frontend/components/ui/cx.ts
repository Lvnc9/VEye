/** Joins class names, dropping the falsy ones — `cx("a", busy && "b")`. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
