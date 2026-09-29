/**
 * The link an attached file is shared by: a page of this app (`/documents/<id>/files/<fid>`), not the
 * API's download address — it asks for a login first and then downloads, so a pasted link keeps
 * working after the 15-minute access token has expired. Pure functions; relative imports only.
 */

export function documentFileLink(origin: string, documentId: number | string, fileId: number | string): string {
  return `${origin.replace(/\/+$/, "")}/documents/${documentId}/files/${fileId}`;
}

/** The file name a `Content-Disposition: attachment` header asks for (RFC 6266: `filename*` wins). */
export function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const encoded = /filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)/.exec(header);
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1].trim());
    } catch {
      // fall through to the plain form
    }
  }
  const plain = /filename\s*=\s*"?([^";]+)"?/.exec(header);
  return plain ? plain[1].trim() : fallback;
}
