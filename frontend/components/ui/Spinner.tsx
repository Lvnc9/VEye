import { LoaderCircle } from "lucide-react";
import { cx } from "./cx";

/** A turning ring for work in progress. Decorative: the surrounding text says what is happening. */
export function Spinner({ className }: { className?: string }) {
  return <LoaderCircle aria-hidden className={cx("size-4 animate-spin", className)} />;
}
