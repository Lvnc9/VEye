"use client";

import { useEffect, useRef } from "react";
import { animate, useInView, useReducedMotion } from "motion/react";
import { cx } from "./cx";

const FORMAT = new Intl.NumberFormat("fa-IR");

/**
 * A number that counts up to its value when it first scrolls into view, in Persian digits (after
 * 21st.dev's «Number Ticker» by Magic UI). Screen readers get the final number at once; reduced motion
 * shows it without counting. The digits are tabular, so the width doesn't jitter while counting.
 */
export function NumberTicker({
  value,
  className,
  duration = 1.1,
}: {
  value: number;
  className?: string;
  /** Seconds. */
  duration?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "0px 0px -10% 0px" });
  const reduce = useReducedMotion();
  const shown = useRef(0);

  useEffect(() => {
    const node = ref.current;
    if (!node || !inView) return;
    if (reduce) {
      node.textContent = FORMAT.format(value);
      shown.current = value;
      return;
    }
    const controls = animate(shown.current, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (latest) => {
        shown.current = latest;
        node.textContent = FORMAT.format(Math.round(latest));
      },
    });
    return () => controls.stop();
  }, [inView, value, reduce, duration]);

  return (
    <span className={cx("tabular-nums", className)}>
      <span ref={ref} aria-hidden>
        {FORMAT.format(0)}
      </span>
      <span className="sr-only">{FORMAT.format(value)}</span>
    </span>
  );
}
