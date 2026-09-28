import { initials } from "@/lib/organization";
import { cx } from "./cx";

const TONES = [
  "bg-sky-100 text-sky-800",
  "bg-indigo-100 text-indigo-800",
  "bg-emerald-100 text-emerald-800",
  "bg-amber-100 text-amber-900",
  "bg-rose-100 text-rose-800",
  "bg-violet-100 text-violet-800",
  "bg-teal-100 text-teal-800",
  "bg-orange-100 text-orange-900",
];

/** The same person always gets the same colour. */
function toneFor(name: string): string {
  let hash = 0;
  for (const char of name) hash = (hash * 31 + char.codePointAt(0)!) | 0;
  return TONES[Math.abs(hash) % TONES.length];
}

const SIZES = {
  xs: "size-6 text-[10px]",
  sm: "size-7 text-[11px]",
  md: "size-9 text-xs",
  lg: "size-11 text-sm",
} as const;

/** A person's initials in a coloured circle. */
export function Avatar({
  name,
  size = "md",
  className,
  title,
}: {
  name: string;
  size?: keyof typeof SIZES;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title ?? name}
      aria-hidden
      className={cx(
        "inline-flex shrink-0 select-none items-center justify-center rounded-full font-bold",
        SIZES[size],
        toneFor(name),
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}

/** Overlapping avatars with a «+n» for the rest. */
export function AvatarStack({
  names,
  total,
  max = 4,
  size = "sm",
  label,
}: {
  names: string[];
  total?: number;
  max?: number;
  size?: keyof typeof SIZES;
  label?: string;
}) {
  const extra = (total ?? names.length) - Math.min(max, names.length);
  return (
    <div className="flex -space-x-2 space-x-reverse" aria-label={label} role={label ? "img" : undefined}>
      {names.slice(0, max).map((name, i) => (
        <Avatar key={`${name}-${i}`} name={name} size={size} className="ring-2 ring-white" />
      ))}
      {extra > 0 && (
        <span
          className={cx(
            "inline-flex shrink-0 items-center justify-center rounded-full bg-slate-200 font-bold text-slate-700 ring-2 ring-white",
            SIZES[size],
          )}
        >
          +{extra}
        </span>
      )}
    </div>
  );
}
