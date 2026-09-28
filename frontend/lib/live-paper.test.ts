import { describe, expect, it } from "vitest";
import { PageCache } from "./live-paper";

describe("PageCache", () => {
  it("shows new images and remembers them", () => {
    const cache = new PageCache();
    expect(cache.resolve([{ hash: "a", image: "data:a" }, { hash: "b", image: "data:b" }])).toEqual([
      { hash: "a", src: "data:a" },
      { hash: "b", src: "data:b" },
    ]);
    expect(cache.hashes).toEqual(["a", "b"]);
  });

  it("fills pages sent without an image from the cache", () => {
    const cache = new PageCache();
    cache.resolve([{ hash: "a", image: "data:a" }, { hash: "b", image: "data:b" }]);
    expect(cache.resolve([{ hash: "a" }, { hash: "c", image: "data:c" }])).toEqual([
      { hash: "a", src: "data:a" },
      { hash: "c", src: "data:c" },
    ]);
  });

  it("answers null when an image is missing everywhere, so the caller asks afresh", () => {
    expect(new PageCache().resolve([{ hash: "gone" }])).toBeNull();
  });

  it("stays bounded, evicting the images not shown recently", () => {
    const cache = new PageCache(3);
    cache.resolve([{ hash: "a", image: "1" }, { hash: "b", image: "2" }, { hash: "c", image: "3" }]);
    cache.resolve([{ hash: "a" }, { hash: "d", image: "4" }]); // a is used again, so b goes first
    expect(cache.size).toBe(3);
    expect(cache.hashes).toEqual(["c", "a", "d"]);
  });
});
