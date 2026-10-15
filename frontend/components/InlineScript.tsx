/**
 * A script that runs once, while the HTML is parsed, before the first paint (Next 16 docs,
 * preventing-flash-before-hydration.md). On the client it renders as `text/plain`, so React neither
 * warns about a script tag nor runs it a second time.
 */
export function InlineScript({ html }: { html: string }) {
  return (
    <script
      type={typeof window === "undefined" ? "text/javascript" : "text/plain"}
      suppressHydrationWarning
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
