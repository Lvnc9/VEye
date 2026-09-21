import type { ReactNode } from "react";
import { buildTree, ORG_KIND_LABELS, ORG_KIND_TONE, type OrgNode, type OrgTreeNode } from "@/lib/organization";

interface Props {
  nodes: OrgNode[];
  /** "dark" for the public setup pages, "light" inside the app shell. */
  tone?: "dark" | "light";
  selectedId?: number | null;
  onSelect?: (node: OrgNode) => void;
  /** Extra content on a node's row (a delete button, a member count…). */
  renderExtra?: (node: OrgNode) => ReactNode;
}

/**
 * The chart as a real nested `<ul>`: what screen readers and keyboards get, the wizard's live
 * preview, and the «نمای فشرده» fallback for a very large organisation.
 */
export function OrgTreeList({ nodes, tone = "light", selectedId = null, onSelect, renderExtra }: Props) {
  const root = buildTree(nodes);
  if (!root) return null;
  return (
    <ul role="tree" aria-label="ساختار سازمان" className="space-y-1 text-sm">
      <Row node={root} tone={tone} selectedId={selectedId} onSelect={onSelect} renderExtra={renderExtra} />
    </ul>
  );
}

function Row({ node, tone, selectedId, onSelect, renderExtra }: { node: OrgTreeNode } & Omit<Props, "nodes">) {
  const dark = tone === "dark";
  const selected = node.id === selectedId;
  const label = (
    <>
      <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${ORG_KIND_TONE[node.kind]}`}>
        {ORG_KIND_LABELS[node.kind]}
      </span>
      <span className={node.is_active ? "" : "line-through opacity-60"}>{node.name}</span>
      {!node.is_active && <span className="text-[10px] opacity-70">(بایگانی‌شده)</span>}
    </>
  );
  const rowClass = `flex items-center gap-2 rounded px-2 py-1 ${
    selected
      ? dark
        ? "bg-accent/15 ring-1 ring-accent/40"
        : "bg-sky-50 ring-1 ring-sky-300"
      : dark
        ? "hover:bg-white/5"
        : "hover:bg-slate-100"
  }`;

  return (
    <li role="treeitem" aria-selected={selected} aria-expanded={node.children.length > 0 ? true : undefined}>
      <div className={rowClass}>
        {onSelect ? (
          <button type="button" onClick={() => onSelect(node)} className="flex flex-1 items-center gap-2 text-start">
            {label}
          </button>
        ) : (
          <span className="flex flex-1 items-center gap-2">{label}</span>
        )}
        {renderExtra?.(node)}
      </div>
      {node.children.length > 0 && (
        <ul
          role="group"
          className={`mt-1 ms-3 space-y-1 border-s ps-3 ${dark ? "border-line" : "border-slate-200"}`}
        >
          {node.children.map((child) => (
            <Row key={child.id} node={child} tone={tone} selectedId={selectedId} onSelect={onSelect} renderExtra={renderExtra} />
          ))}
        </ul>
      )}
    </li>
  );
}
