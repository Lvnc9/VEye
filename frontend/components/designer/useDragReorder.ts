"use client";

import { useRef, useState, type DragEvent } from "react";
import { dropIndex } from "@/lib/reorder";

/**
 * Native drag-and-drop reordering of a vertical list, shared by the block
 * designer and the form canvas. Drag starts on a grip (`gripProps`) so text in
 * the rows stays selectable; each row (`rowProps`) is a drop target, split into
 * a top half (drop before) and a bottom half (drop after). ↑/↓ buttons stay the
 * keyboard and touch path.
 */
export function useDragReorder(onReorder: (from: number, to: number) => void) {
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [dropAt, setDropAt] = useState<{ index: number; after: boolean } | null>(null);
  const rows = useRef<(HTMLElement | null)[]>([]);

  function end() {
    setDragFrom(null);
    setDropAt(null);
  }

  return {
    /** Spread onto the row element. */
    rowProps(index: number) {
      return {
        ref: (node: HTMLElement | null) => {
          rows.current[index] = node;
        },
        onDragOver(event: DragEvent) {
          if (dragFrom === null) return;
          event.preventDefault();
          const box = event.currentTarget.getBoundingClientRect();
          const after = event.clientY > box.top + box.height / 2;
          if (dropAt?.index !== index || dropAt.after !== after) setDropAt({ index, after });
        },
        onDrop(event: DragEvent) {
          event.preventDefault();
          if (dragFrom !== null && dropAt) onReorder(dragFrom, dropIndex(dragFrom, dropAt.index, dropAt.after));
          end();
        },
      };
    },
    /** Spread onto the grip that starts a drag of row `index`. */
    gripProps(index: number, key: string) {
      return {
        draggable: true,
        onDragStart(event: DragEvent) {
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", key); // Firefox needs data to start a drag
          const row = rows.current[index];
          if (row) event.dataTransfer.setDragImage(row, 16, 16);
          setDragFrom(index);
        },
        onDragEnd: end,
        title: "برای جابه‌جایی بکشید",
      };
    },
    /** Where the drop line shows for row `index`, if anywhere. */
    marker(index: number): "before" | "after" | null {
      return dropAt?.index === index ? (dropAt.after ? "after" : "before") : null;
    },
    isDragging(index: number): boolean {
      return dragFrom === index;
    },
  };
}
