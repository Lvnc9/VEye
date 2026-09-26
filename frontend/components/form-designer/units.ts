import { PT_IN_MM } from "@/lib/form-layout";

/** CSS length of `n` millimetres on the canvas page. The page sets `--mm` to one
 *  millimetre of its own rendered width, so the whole page scales with the column. */
export function mm(n: number): string {
  return `calc(var(--mm) * ${n})`;
}

/** CSS length of `n` typographic points on the canvas page. */
export function pt(n: number): string {
  return mm(n * PT_IN_MM);
}
