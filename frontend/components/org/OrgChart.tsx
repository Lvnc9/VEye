"use client";

import { useCallback, useRef, useState, type PointerEvent, type ReactNode, type WheelEvent } from "react";
import {
  ORG_KIND_LABELS,
  chartLayout,
  fitView,
  zoomAround,
  type Company,
  type OrgNode,
  type OrgTreeNode,
} from "@/lib/organization";

interface Props {
  nodes: OrgNode[];
  company: Company | null;
  showArchived: boolean;
  selectedId: number | null;
  onSelect: (node: OrgNode) => void;
}

/**
 * The organisation as a building, hand-drawn in CSS: the company is the building (its name and
 * logo on the facade), each حوزه a floor, each واحد a room, each بخش a desk. Everything clickable is
 * a real `<button>` with a spoken label, so the chart works from the keyboard; the semantic `<ul>`
 * tree (the «نمای فشرده») is its fallback for screen readers and very large organisations.
 *
 * Pan by dragging the background, zoom with the buttons or Ctrl/⌘ + wheel. No library: a
 * `transform` on one wrapper.
 */
export function OrgChart({ nodes, company, showArchived, selectedId, onSelect }: Props) {
  const layout = chartLayout(nodes, showArchived);
  const [view, setView] = useState({ x: 0, y: 0, zoom: 1 });
  const viewport = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement | null>(null);
  const fitted = useRef(false);
  const drag = useRef<{ x: number; y: number; view: typeof view } | null>(null);

  const fit = useCallback(() => {
    const frame = viewport.current ?? content.current?.parentElement;
    const box = frame?.getBoundingClientRect();
    if (!box || !content.current) return;
    // offsetWidth/Height are the layout size: unaffected by the transform being fitted.
    setView(fitView({ width: box.width, height: box.height }, { width: content.current.offsetWidth, height: content.current.offsetHeight }));
  }, []);

  // A callback ref, not an effect: fit the whole building into view once, when it first appears.
  const attachContent = useCallback(
    (node: HTMLDivElement | null) => {
      content.current = node;
      if (node && !fitted.current) {
        fitted.current = true;
        fit();
      }
    },
    [fit],
  );

  if (!layout) return null;

  const center = () => {
    const box = viewport.current?.getBoundingClientRect();
    return { x: (box?.width ?? 0) / 2, y: (box?.height ?? 0) / 2 };
  };

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    // Only a drag that starts on the empty background pans; buttons keep their clicks.
    if ((event.target as HTMLElement).closest("button")) return;
    drag.current = { x: event.clientX, y: event.clientY, view };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    const start = drag.current;
    if (!start) return;
    setView({ ...start.view, x: start.view.x + event.clientX - start.x, y: start.view.y + event.clientY - start.y });
  }

  function onWheel(event: WheelEvent<HTMLDivElement>) {
    if (!event.ctrlKey && !event.metaKey) return; // a plain wheel keeps scrolling the page
    event.preventDefault();
    const box = event.currentTarget.getBoundingClientRect();
    setView((v) => zoomAround(v, event.deltaY < 0 ? 1.1 : 1 / 1.1, { x: event.clientX - box.left, y: event.clientY - box.top }));
  }

  const button = "flex h-8 w-8 items-center justify-center rounded border border-slate-300 bg-white text-slate-700 hover:bg-slate-50";

  return (
    <div className="relative">
      <div className="absolute end-3 top-3 z-10 flex gap-1" role="group" aria-label="بزرگ‌نمایی">
        <button type="button" className={button} aria-label="بزرگ‌تر" onClick={() => setView((v) => zoomAround(v, 1.2, center()))}>
          +
        </button>
        <button type="button" className={button} aria-label="کوچک‌تر" onClick={() => setView((v) => zoomAround(v, 1 / 1.2, center()))}>
          −
        </button>
        <button
          type="button"
          className={`${button} w-auto px-2 text-xs`}
          aria-label="بازنشانی نما"
          onClick={fit}
        >
          نمای کامل
        </button>
      </div>

      <div
        ref={viewport}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={() => (drag.current = null)}
        onPointerCancel={() => (drag.current = null)}
        onWheel={onWheel}
        className="relative h-[70vh] min-h-[28rem] cursor-grab touch-none overflow-hidden rounded-xl border border-slate-200 bg-[radial-gradient(circle_at_1px_1px,#cbd5e1_1px,transparent_0)] bg-[length:22px_22px] bg-slate-50 active:cursor-grabbing"
      >
        <div
          ref={attachContent}
          style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.zoom})`, transformOrigin: "0 0" }}
          className="absolute top-0 left-0 w-max max-w-none"
        >
          <Building name={layout.company.name} logo={company?.logo_url ?? null} archivedShown={showArchived}>
            {layout.floors.length === 0 && (
              <p className="px-6 py-8 text-center text-sm text-slate-500">هنوز حوزه یا واحدی ساخته نشده است.</p>
            )}
            {layout.floors.map((floor) => (
              <Floor
                key={floor.node?.id ?? "ground"}
                title={floor.node?.name ?? "واحدهای مستقل"}
                floorNode={floor.node}
                selectedId={selectedId}
                onSelect={onSelect}
              >
                {floor.rooms.length === 0 && <span className="text-xs text-slate-400">بدون واحد</span>}
                {floor.rooms.map((room) => (
                  <Room key={room.node.id} node={room.node} selected={room.node.id === selectedId} onSelect={onSelect}>
                    {room.desks.map((desk) => (
                      <Desk key={desk.id} node={desk} selected={desk.id === selectedId} onSelect={onSelect} />
                    ))}
                  </Room>
                ))}
              </Floor>
            ))}
            <RootSelect node={layout.company} selected={layout.company.id === selectedId} onSelect={onSelect} />
          </Building>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-500">برای جابه‌جایی نما بکشید؛ برای بزرگ‌نمایی از دکمه‌ها یا Ctrl + چرخ ماوس استفاده کنید.</p>
    </div>
  );
}

function Building({ name, logo, archivedShown, children }: { name: string; logo: string | null; archivedShown: boolean; children: ReactNode }) {
  return (
    <section
      aria-label={`ساختمان ${name}`}
      className="w-max min-w-[36rem] rounded-3xl border-2 border-slate-800 bg-white shadow-lg"
    >
      <header className="flex items-center justify-center gap-3 rounded-t-[1.4rem] bg-slate-800 px-8 py-4 text-white">
        {logo && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={logo} alt="" className="h-9 w-9 rounded bg-white object-contain p-0.5" />
        )}
        <h2 className="text-lg font-bold">{name}</h2>
        {archivedShown && <span className="rounded bg-amber-400 px-1.5 py-0.5 text-[10px] font-medium text-amber-950">با بایگانی‌شده‌ها</span>}
      </header>
      <div className="divide-y-2 divide-slate-200">{children}</div>
    </section>
  );
}

function Floor({
  title,
  floorNode,
  selectedId,
  onSelect,
  children,
}: {
  title: string;
  floorNode: OrgTreeNode | null;
  selectedId: number | null;
  onSelect: (node: OrgNode) => void;
  children: ReactNode;
}) {
  const selected = floorNode !== null && floorNode.id === selectedId;
  return (
    <div className={`flex items-stretch ${floorNode && !floorNode.is_active ? "opacity-60" : ""}`}>
      <div className="flex w-28 shrink-0 items-center justify-center border-e-2 border-slate-200 bg-slate-50 p-3 text-center">
        {floorNode ? (
          <button
            type="button"
            onClick={() => onSelect(floorNode)}
            aria-label={`${ORG_KIND_LABELS.DOMAIN} ${title}`}
            aria-pressed={selected}
            className={`rounded-lg px-2 py-1.5 text-sm font-semibold text-indigo-900 hover:bg-indigo-100 ${selected ? "bg-indigo-100 ring-2 ring-indigo-400" : ""}`}
          >
            {title}
          </button>
        ) : (
          <span className="text-sm font-semibold text-slate-500">{title}</span>
        )}
      </div>
      <div className="flex flex-1 flex-wrap items-start gap-4 p-4">{children}</div>
    </div>
  );
}

function Room({ node, selected, onSelect, children }: { node: OrgTreeNode; selected: boolean; onSelect: (node: OrgNode) => void; children: ReactNode }) {
  return (
    <div
      className={`min-w-44 rounded-xl border-2 bg-sky-50/60 p-3 ${selected ? "border-sky-500 ring-2 ring-sky-300" : "border-sky-200"} ${node.is_active ? "" : "opacity-60"}`}
    >
      <button
        type="button"
        onClick={() => onSelect(node)}
        aria-label={`${ORG_KIND_LABELS.UNIT} ${node.name}`}
        aria-pressed={selected}
        className="mb-2 block w-full rounded-lg px-2 py-1 text-start text-sm font-semibold text-sky-900 hover:bg-sky-100"
      >
        {node.name}
        {!node.is_active && <span className="ms-1 text-[10px] font-normal">(بایگانی‌شده)</span>}
      </button>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

function Desk({ node, selected, onSelect }: { node: OrgTreeNode; selected: boolean; onSelect: (node: OrgNode) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(node)}
      aria-label={`${ORG_KIND_LABELS.SECTION} ${node.name}`}
      aria-pressed={selected}
      className={`rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors ${
        selected ? "border-emerald-500 bg-emerald-100 text-emerald-900 ring-2 ring-emerald-300" : "border-emerald-200 bg-white text-emerald-900 hover:bg-emerald-50"
      } ${node.is_active ? "" : "opacity-60"}`}
    >
      {node.name}
    </button>
  );
}

/** The company row, so the building itself can be selected (its people, its top-level structure). */
function RootSelect({ node, selected, onSelect }: { node: OrgTreeNode; selected: boolean; onSelect: (node: OrgNode) => void }) {
  return (
    <div className="flex justify-center bg-slate-50 p-3 rounded-b-[1.4rem]">
      <button
        type="button"
        onClick={() => onSelect(node)}
        aria-label={`${ORG_KIND_LABELS.COMPANY} ${node.name}`}
        aria-pressed={selected}
        className={`rounded-lg px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-200 ${selected ? "bg-slate-200 ring-2 ring-slate-400" : ""}`}
      >
        افراد و ساختار سطح شرکت
      </button>
    </div>
  );
}
