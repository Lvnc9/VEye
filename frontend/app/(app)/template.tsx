/**
 * Every signed-in screen rises in when you arrive at it. A template (unlike the layout) remounts when its
 * segment changes, so the entrance plays on each move between sections — but not on a search-param change
 * such as opening a conversation in /inbox?c=…, which keeps its state (Next 16 docs, template.md).
 */
export default function AppTemplate({ children }: { children: React.ReactNode }) {
  return <div className="veye-page">{children}</div>;
}
