"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronDown, X } from "lucide-react";
import { Popover } from "@/components/ui/Popover";
import { cx } from "@/components/ui/cx";
import { apiGet } from "@/lib/api-client";
import type { OrgNode, OrgTreeResponse } from "@/lib/organization";
import {
  MAX_RESPONSIBILITY_ROWS,
  clearChoice,
  companyHasDomains,
  domainOfUnit,
  domainOptions,
  emptyResponsibilityRow,
  pickDomain,
  pickUnit,
  rowStage,
  standaloneUnits,
  unitOptions,
} from "@/lib/responsibilities";
import type { ResponsibilitiesSection, ResponsibilityRow } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api-query";
import { textareaClass } from "../ui/Field";
import { AddButton, IconButton, type BlockProps } from "./ui";

const pickerButton =
  "inline-flex h-10 min-w-40 max-w-full items-center justify-between gap-2 rounded-xl border px-3 text-sm transition-colors " +
  "disabled:cursor-not-allowed disabled:opacity-50";

/** A button that opens a short list: «انتخاب حوزه» / «انتخاب واحد», then the chosen name. */
function Picker<T extends { id: number; name: string }>({
  label,
  chosen,
  options,
  extra,
  disabled,
  empty,
  onPick,
}: {
  label: string;
  /** The name to show once something is chosen (the row's stored snapshot, so it shows even while the chart loads). */
  chosen: string;
  options: T[];
  /** A last option that is not a node, e.g. «بدون حوزه». */
  extra?: { label: string; onPick: () => void };
  disabled: boolean;
  empty: string;
  onPick: (option: T) => void;
}) {
  return (
    <Popover
      label={label}
      disabled={disabled}
      triggerClassName={cx(
        pickerButton,
        chosen ? "border-brand-300 bg-brand-50 text-brand-900" : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50",
      )}
      panelClassName="max-h-64 w-64 overflow-y-auto"
      trigger={
        <>
          <span className="truncate">{chosen || label}</span>
          <ChevronDown className="size-4 shrink-0 text-slate-400" />
        </>
      }
    >
      {(close) => (
        <div className="space-y-0.5">
          {options.length === 0 && !extra && <p className="px-3 py-2 text-sm text-slate-500">{empty}</p>}
          {options.map((option) => (
            <button
              key={option.id}
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                onPick(option);
                close();
              }}
              className="flex w-full items-center rounded-lg px-3 py-2 text-start text-sm text-slate-700 hover:bg-slate-100"
            >
              {option.name}
            </button>
          ))}
          {extra && (
            <button
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                extra.onPick();
                close();
              }}
              className="flex w-full items-center rounded-lg border-t border-slate-100 px-3 py-2 text-start text-sm text-slate-500 hover:bg-slate-100"
            >
              {extra.label}
            </button>
          )}
        </div>
      )}
    </Popover>
  );
}

/** With a truncated chart (over `ORG_TREE_MAX_NODES`) the list holds only the top two levels; the units of the
 *  chosen حوزه are then fetched on their own (`GET /org/tree/?parent=<id>`). */
function useLoadedChildren(parent: number | null, needed: boolean): OrgNode[] {
  const [loaded, setLoaded] = useState<{ parent: number; nodes: OrgNode[] } | null>(null);
  useEffect(() => {
    if (!needed || parent === null) return;
    let cancelled = false;
    apiGet<OrgTreeResponse>("/org/tree/", { parent })
      .then((data) => !cancelled && setLoaded({ parent, nodes: data.nodes }))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [needed, parent]);
  return needed && loaded && loaded.parent === parent ? loaded.nodes : [];
}

/**
 * مسئولیت ها — one line per row (owner's redesign, 2026-09-30): the block starts with one row; each row is
 * «انتخاب حوزه» (only when the company has حوزه), then «انتخاب واحد», then a «توضیحات:» field, and prints as
 * «حوزه IT  واحد هوش مصنوعی  جهت <text>». Any number of rows.
 */
export function ResponsibilitiesBlock({ section, disabled, update }: BlockProps<ResponsibilitiesSection>) {
  const tree = useApiQuery<OrgTreeResponse>("/org/tree/");
  // Units fetched for a truncated chart, merged over every row's choice.
  const [fetched, setFetched] = useState<OrgNode[]>([]);
  const addFetched = useCallback(
    (nodes: OrgNode[]) =>
      setFetched((previous) => {
        const known = new Set(previous.map((node) => node.id));
        const fresh = nodes.filter((node) => !known.has(node.id));
        return fresh.length > 0 ? [...previous, ...fresh] : previous;
      }),
    [],
  );
  const chart = tree.data?.nodes ?? [];
  const hasDomains = companyHasDomains(chart);

  const setRow = (position: number, next: (row: ResponsibilityRow) => ResponsibilityRow) =>
    update((s) => ({ ...s, rows: s.rows.map((row, i) => (i === position ? next(row) : row)) }));

  return (
    <div className="space-y-3">
      {tree.error && <p className="text-sm text-rose-700">{tree.error}</p>}
      {section.rows.map((row, position) => (
        <Row
          key={position}
          index={position}
          row={row}
          chart={chart}
          extraUnits={fetched}
          onFetched={addFetched}
          truncated={tree.data?.truncated === true}
          hasDomains={hasDomains}
          disabled={disabled}
          loading={tree.loading}
          onChange={(next) => setRow(position, next)}
          onRemove={() =>
            update((s) => ({
              ...s,
              rows: s.rows.length > 1 ? s.rows.filter((_, i) => i !== position) : [emptyResponsibilityRow()],
            }))
          }
        />
      ))}
      {!disabled && section.rows.length < MAX_RESPONSIBILITY_ROWS && (
        <AddButton onClick={() => update((s) => ({ ...s, rows: [...s.rows, emptyResponsibilityRow()] }))}>افزودن مسئولیت</AddButton>
      )}
    </div>
  );
}

function Row({
  index,
  row,
  chart,
  extraUnits,
  onFetched,
  truncated,
  hasDomains,
  disabled,
  loading,
  onChange,
  onRemove,
}: {
  index: number;
  row: ResponsibilityRow;
  chart: OrgNode[];
  extraUnits: OrgNode[];
  onFetched: (nodes: OrgNode[]) => void;
  truncated: boolean;
  hasDomains: boolean;
  disabled: boolean;
  loading: boolean;
  onChange: (next: (row: ResponsibilityRow) => ResponsibilityRow) => void;
  onRemove: () => void;
}) {
  // A truncated chart lacks the units under a حوزه: fetch them for this row's choice.
  const children = useLoadedChildren(row.domain, truncated && row.domain !== null);
  useEffect(() => {
    if (children.length > 0) onFetched(children);
  }, [children, onFetched]);

  const nodes = truncated ? [...chart, ...extraUnits] : chart;
  const stage = rowStage(row, hasDomains);
  const units = unitOptions(nodes, row, hasDomains);
  const canStandAlone = hasDomains && standaloneUnits(nodes).length > 0;

  return (
    <div className="flex flex-wrap items-start gap-2 rounded-xl border border-slate-200 bg-white p-3">
      <span className="mt-2 w-6 shrink-0 text-center text-xs text-slate-400">{index + 1}</span>
      <div className="flex min-w-0 flex-1 flex-wrap items-start gap-2">
        {hasDomains && (
          <Picker
            label="انتخاب حوزه"
            chosen={row.domain_name || (row.standalone ? "بدون حوزه" : "")}
            options={domainOptions(chart, row.domain)}
            extra={canStandAlone ? { label: "بدون حوزه (واحدهای مستقل)", onPick: () => onChange((r) => pickDomain(r, null)) } : undefined}
            disabled={disabled || loading}
            empty="حوزه‌ای تعریف نشده است."
            onPick={(node) => onChange((r) => pickDomain(r, node))}
          />
        )}
        {(!hasDomains || stage !== "domain") && (
          <Picker
            label="انتخاب واحد"
            chosen={row.unit_name}
            options={units}
            disabled={disabled || loading}
            empty={
              !hasDomains
                ? "واحدی تعریف نشده است."
                : row.domain === null && !row.standalone
                  ? "ابتدا حوزه را انتخاب کنید."
                  : "این حوزه واحدی ندارد."
            }
            onPick={(node) => onChange((r) => pickUnit(r, node, domainOfUnit(nodes, node)))}
          />
        )}
        {stage === "text" && (
          <textarea
            value={row.text}
            disabled={disabled}
            maxLength={5000}
            rows={1}
            placeholder="توضیحات:"
            aria-label={`توضیحات مسئولیت ${index + 1}`}
            onChange={(event) => onChange((r) => ({ ...r, text: event.target.value }))}
            className={cx(textareaClass, "min-h-10 min-w-56 flex-1 resize-y")}
          />
        )}
        {stage === "text" && row.unit_name !== "" && !disabled && (
          <button
            type="button"
            onClick={() => onChange(clearChoice)}
            className="mt-2 inline-flex items-center gap-1 text-xs text-slate-500 underline-offset-2 hover:text-slate-800 hover:underline"
          >
            تغییر {hasDomains ? "حوزه و واحد" : "واحد"}
          </button>
        )}
      </div>
      {!disabled && (
        <IconButton label="حذف این ردیف" tone="danger" onClick={onRemove}>
          <X />
        </IconButton>
      )}
    </div>
  );
}
