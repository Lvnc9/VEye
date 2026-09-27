"use client";

import { useState } from "react";
import {
  ELEMENT_GROUP_LABELS,
  ELEMENT_KINDS,
  MAX_ELEMENTS,
  fromResponse,
  insertAfter,
  moveElement,
  newElement,
  snapshot,
  toPayload,
  validate,
  type ElementKind,
  type FormElement,
  type FormState,
} from "@/lib/form-designer";
import { formatJalali } from "@/lib/jalali";
import { useCurrentUser } from "@/lib/current-user";
import type { ContentResponse } from "@/lib/types";
import { DesignerShell } from "@/components/designer/DesignerShell";
import { FootnoteFields } from "@/components/designer/FootnoteFields";
import { LogoSection } from "@/components/designer/LogoSection";
import { useDesignerDocument, type DesignerAdapter } from "@/components/designer/useDesignerDocument";
import { FormCanvas } from "./FormCanvas";
import { ElementInspector, PageSettingsPanel } from "./Inspector";

const formAdapter: DesignerAdapter<FormState> = { fromResponse, toPayload, snapshot, validate };

type Tab = "element" | "page";

/** طراحی فرم (Phase 11, ADR-011): a palette, the A4 canvas, and an inspector. */
export function FormDesigner({ initial }: { initial: ContentResponse }) {
  const doc = useDesignerDocument(initial, formAdapter);
  const { user } = useCurrentUser();
  const { content, state, setState, canEdit, locked } = doc;
  const document = content.document;

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("page");
  const selected = state.elements.find((element) => element.key === selectedKey) ?? null;

  function edit(updater: (current: FormState) => FormState) {
    setState(updater);
    doc.setNotice(null);
  }

  function updateElement(key: string, updater: (element: FormElement) => FormElement) {
    edit((current) => ({ ...current, elements: current.elements.map((e) => (e.key === key ? updater(e) : e)) }));
  }

  function select(key: string | null) {
    setSelectedKey(key);
    if (key) setTab("element");
  }

  function add(kind: ElementKind) {
    const element = newElement(kind);
    edit((current) => {
      // New elements go after the selected one, or at the end.
      const at = current.elements.findIndex((e) => e.key === selectedKey);
      return { ...current, elements: insertAfter(current.elements, element, at === -1 ? current.elements.length : at) };
    });
    select(element.key);
  }

  function remove(key: string) {
    if (!window.confirm("این جزء حذف شود؟")) return;
    edit((current) => ({ ...current, elements: current.elements.filter((e) => e.key !== key) }));
    if (key === selectedKey) setSelectedKey(null);
  }

  const full = state.elements.length >= MAX_ELEMENTS;
  const groups = (Object.keys(ELEMENT_GROUP_LABELS) as (keyof typeof ELEMENT_GROUP_LABELS)[])
    .map((group) => ({ group, kinds: ELEMENT_KINDS.filter((entry) => entry.group === group) }))
    .filter(({ kinds }) => kinds.length > 0);

  return (
    <DesignerShell doc={doc} wide>
      {canEdit && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <span className="text-sm font-semibold text-slate-700">افزودن:</span>
          {groups.map(({ group, kinds }) => (
            <div key={group} className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-slate-500">{ELEMENT_GROUP_LABELS[group]}</span>
              {kinds.map(({ kind, label }) => (
                <button
                  key={kind}
                  type="button"
                  disabled={locked || full}
                  title={full ? `یک فرم حداکثر ${MAX_ELEMENTS.toLocaleString("fa-IR")} جزء دارد.` : undefined}
                  onClick={() => add(kind)}
                  className="rounded bg-indigo-600 px-2.5 py-1 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  + {label}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px] xl:items-start">
        <FormCanvas
          header={{
            title: document.title,
            fullCode: document.full_code,
            revision: document.revision_display,
            date: formatJalali(document.content_saved_at ?? new Date()),
            companyName: user?.company?.name ?? "",
            logoUrl: content.logo_url,
            footnote1: state.footnote1,
            footnote2: state.footnote2,
          }}
          settings={state.settings}
          elements={state.elements}
          selectedKey={selectedKey}
          locked={locked}
          onSelect={select}
          onMove={(index, direction) => edit((current) => ({ ...current, elements: moveElement(current.elements, index, index + direction) }))}
          onRemove={remove}
          onReorder={(from, to) => edit((current) => ({ ...current, elements: moveElement(current.elements, from, to) }))}
          onUpdate={updateElement}
        />

        <aside className="rounded-lg border border-slate-200 bg-white shadow-sm xl:sticky xl:top-4">
          <div role="tablist" className="flex border-b border-slate-200 text-sm">
            {(
              [
                ["element", "ویژگی‌های جزء"],
                ["page", "صفحه و سربرگ"],
              ] as [Tab, string][]
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={tab === id}
                onClick={() => setTab(id)}
                className={`flex-1 px-3 py-2.5 font-medium ${
                  tab === id ? "border-b-2 border-indigo-600 text-indigo-700" : "text-slate-500 hover:text-slate-800"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="p-4">
            {tab === "element" &&
              (selected ? (
                <ElementInspector
                  key={selected.key}
                  element={selected}
                  disabled={locked}
                  update={(updater) => updateElement(selected.key, updater)}
                />
              ) : (
                <p className="text-sm text-slate-500">برای دیدن ویژگی‌ها، روی یکی از اجزای فرم کلیک کنید.</p>
              ))}
            {tab === "page" && (
              <div className="space-y-6">
                <PageSettingsPanel
                  settings={state.settings}
                  disabled={locked}
                  onChange={(settings) => edit((current) => ({ ...current, settings }))}
                />
                <section className="space-y-2 border-t border-slate-200 pt-4">
                  <h3 className="text-sm font-semibold text-slate-800">لوگو</h3>
                  <LogoSection
                    endpoint={`/documents/${document.id}/logo/`}
                    logoUrl={content.logo_url}
                    canEdit={canEdit}
                    onChange={(logoUrl) => doc.setContent((current) => ({ ...current, logo_url: logoUrl }))}
                  />
                </section>
                <section className="space-y-2 border-t border-slate-200 pt-4">
                  <h3 className="text-sm font-semibold text-slate-800">پاورقی</h3>
                  <FootnoteFields
                    footnote1={state.footnote1}
                    footnote2={state.footnote2}
                    disabled={locked}
                    onChange={(next) => edit((current) => ({ ...current, ...next }))}
                  />
                </section>
              </div>
            )}
          </div>
        </aside>
      </div>
    </DesignerShell>
  );
}
