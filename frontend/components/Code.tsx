/** A document code like "PO-01-01" is Latin text inside an RTL page; isolate it
 *  so the hyphens and digits aren't reordered by the bidi algorithm, and keep it
 *  on one line (a hyphen is otherwise a legal break point). */
export function Code({ children }: { children: string }) {
  return (
    <bdi
      dir="ltr"
      className="inline-block whitespace-nowrap rounded-md bg-muted px-1.5 py-px font-mono text-[12.5px] text-soft-foreground ring-1 ring-inset ring-border"
    >
      {children}
    </bdi>
  );
}
