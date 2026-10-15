"use client";

import { LazyMotion, MotionConfig, domMax } from "motion/react";
import { Direction, Tooltip } from "radix-ui";
import { ThemeProvider } from "@/components/theme/ThemeProvider";

/**
 * Everything the whole app needs once, around every page (public ones too):
 * - the theme (light / dark / system, lib/theme.ts);
 * - right-to-left for Radix — its menus, tooltips and sheets read the direction from here, not from CSS;
 * - one tooltip timing;
 * - motion: `m.*` components load their features once here (domMax, for layout animations), and every
 *   animation stands still for people who ask for reduced motion.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <Direction.Provider dir="rtl">
        <Tooltip.Provider delayDuration={300} skipDelayDuration={150}>
          <LazyMotion features={domMax}>
            <MotionConfig reducedMotion="user">{children}</MotionConfig>
          </LazyMotion>
        </Tooltip.Provider>
      </Direction.Provider>
    </ThemeProvider>
  );
}
