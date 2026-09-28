/**
 * The designer's live paper (Phase 12): `POST /documents/{id}/live-preview/`
 * answers with page hashes, and an image only for pages the client did not
 * already have. This keeps the images seen so far and turns an answer into
 * the pages to show. React-free, so it is tested directly.
 */

export interface PreviewPage {
  hash: string;
  /** A PNG data URL; absent when the client said it already had this hash. */
  image?: string;
}

export interface PreviewResponse {
  pages: PreviewPage[];
  page_count: number;
  truncated: boolean;
}

export interface ShownPage {
  hash: string;
  src: string;
}

/** Page images kept between answers. Oldest first; bounded. */
export class PageCache {
  private images = new Map<string, string>();

  constructor(private readonly limit = 60) {}

  get hashes(): string[] {
    return [...this.images.keys()];
  }

  get size(): number {
    return this.images.size;
  }

  /**
   * The pages to show for an answer, remembering its new images — or `null`
   * when a page came without an image and is no longer cached (the caller then
   * asks again with no known hashes).
   */
  resolve(pages: PreviewPage[]): ShownPage[] | null {
    const shown: ShownPage[] = [];
    for (const page of pages) {
      const src = page.image ?? this.images.get(page.hash);
      if (!src) return null;
      // Re-inserting moves the entry to the newest end, so pages in use are the last evicted.
      this.images.delete(page.hash);
      this.images.set(page.hash, src);
      shown.push({ hash: page.hash, src });
    }
    while (this.images.size > this.limit) {
      const oldest = this.images.keys().next().value as string;
      this.images.delete(oldest);
    }
    return shown;
  }
}
