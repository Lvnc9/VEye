/**
 * Turns an API error body into readable Persian text. Pure — relative imports only.
 *
 * The backend sends `{ detail: "..." }` (permission errors, conflicts, bad credentials) or DRF
 * field errors, which nest: `{ title: ["..."] }`, but also `{ manager: { password: ["..."] } }`
 * for a nested serializer. Everything reachable is flattened, in order.
 */
export function flattenErrorMessages(data: unknown): string[] {
  if (typeof data === "string") return data ? [data] : [];
  if (Array.isArray(data)) return data.flatMap(flattenErrorMessages);
  if (typeof data === "object" && data !== null) {
    return Object.entries(data as Record<string, unknown>)
      .filter(([key]) => key !== "code") // a machine code, not something to show
      .flatMap(([, value]) => flattenErrorMessages(value));
  }
  return [];
}

export function extractErrorMessage(data: unknown, status: number): string {
  if (typeof data === "object" && data !== null) {
    const detail = (data as Record<string, unknown>).detail;
    if (typeof detail === "string" && detail) return detail;
    const messages = flattenErrorMessages(data);
    if (messages.length > 0) return messages.join(" ");
  }
  return `درخواست ناموفق بود (کد ${status}).`;
}
