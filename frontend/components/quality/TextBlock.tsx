import { cx } from "@/components/ui/cx";

/** One labelled paragraph of a quality record — shown only when there is something to say. */
export function TextBlock({ title, text, tone = "plain" }: { title: string; text: string; tone?: "plain" | "danger" | "success" }) {
  if (!text) return null;
  const surface =
    tone === "danger" ? "bg-rose-50/70 dark:bg-rose-400/10 ring-rose-200" : tone === "success" ? "bg-emerald-50/70 dark:bg-emerald-400/10 ring-emerald-200" : "bg-muted/50 ring-border";
  return (
    <section className={cx("rounded-xl px-4 py-3 ring-1 ring-inset", surface)}>
      <h3 className="mb-1 text-xs font-bold text-soft-foreground">{title}</h3>
      <p className="whitespace-pre-line text-sm leading-7 text-foreground">{text}</p>
    </section>
  );
}
