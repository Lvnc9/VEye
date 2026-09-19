/** A document code like "PO-01-01" is Latin text inside an RTL page; isolate it
 *  so the hyphens and digits aren't reordered by the bidi algorithm, and keep it
 *  on one line (a hyphen is otherwise a legal break point). */
export function Code({ children }: { children: string }) {
  return (
    <bdi dir="ltr" className="inline-block whitespace-nowrap font-mono text-[13px]">
      {children}
    </bdi>
  );
}
