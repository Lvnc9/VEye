import { cx } from "./cx";

/**
 * The living navy backdrop of the public pages (sign-in, the landing page, setup): slow aurora light that
 * drifts, a dot grid fading out towards the bottom, and a few beams of light running along faint lines
 * (after 21st.dev's «Background Beams» and «Background snippets»). Purely decorative and `aria-hidden`;
 * it animates transform/opacity/stroke only and stands still for reduced motion (globals.css). It sits
 * behind its parent's content: give the parent `relative isolate`.
 */
export function AnimatedBackground({ className, beams = true }: { className?: string; beams?: boolean }) {
  return (
    <div aria-hidden className={cx("pointer-events-none absolute inset-0 -z-10 overflow-hidden bg-navy", className)}>
      {/* Aurora: three soft lights drifting on long, out-of-step loops. */}
      <div className="veye-aurora absolute -top-1/4 right-[-10%] size-[42rem] rounded-full bg-sky-500/20 blur-[120px]" />
      <div className="veye-aurora veye-aurora-2 absolute top-1/3 left-[-15%] size-[36rem] rounded-full bg-indigo-500/15 blur-[120px]" />
      <div className="veye-aurora veye-aurora-3 absolute bottom-[-20%] right-1/4 size-[30rem] rounded-full bg-emerald-400/10 blur-[110px]" />

      {/* A dot grid, strongest at the top. */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgb(148_163_184/0.14)_1px,transparent_0)] bg-[length:26px_26px] [mask-image:radial-gradient(ellipse_80%_60%_at_50%_0%,black,transparent)]" />

      {beams && (
        <svg className="absolute inset-0 size-full" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice" fill="none">
          <defs>
            <linearGradient id="veye-beam" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="#38bdf8" stopOpacity="0" />
              <stop offset="0.5" stopColor="#38bdf8" stopOpacity="0.9" />
              <stop offset="1" stopColor="#818cf8" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[
            "M-50 620 C 250 520, 450 700, 700 560 S 1100 420, 1260 470",
            "M-50 300 C 200 380, 420 220, 650 300 S 1000 420, 1260 330",
            "M-50 120 C 300 60, 520 200, 800 130 S 1080 40, 1260 90",
          ].map((d, i) => (
            <g key={d}>
              <path d={d} stroke="rgb(148 163 184 / 0.07)" strokeWidth="1" />
              <path d={d} stroke="url(#veye-beam)" strokeWidth="1.5" strokeLinecap="round" className="veye-beam" style={{ animationDelay: `${i * 2.4}s` }} />
            </g>
          ))}
        </svg>
      )}

      {/* A top light and a vignette at the foot, so text above stays calm. */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-l from-transparent via-glow/40 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-navy to-transparent" />
    </div>
  );
}
