"use client";

import { MousePointerClick, Plus } from "lucide-react";
import { cardClass } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Tabs } from "@/components/ui/Tabs";
import { useState } from "react";
import {
  ELEMENT_GROUP_LABELS,
  ELEMENT_KINDS,
  MAX_ELEMENTS,
  fromResponse,
  insertAfter,
  moveElement,
  newElement,
  rekey,
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

const formAdapter: DesignerAdapter<FormState> = { fromResponse, toPayload, snapshot, validate, rekey };

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
        <div className={`${cardClass} flex flex-wrap items-center gap-x-5 gap-y-2.5 px-4 py-3`}>
          <span className="flex items-center gap-1.5 text-sm font-bold text-slate-700">
            <Plus className="size-4 text-brand-600" />
            افزودن:
          </span>
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
                  className="inline-flex h-8 items-center rounded-lg bg-brand-50 px-2.5 text-sm text-brand-800 ring-1 ring-inset ring-brand-600/15 transition-[background-color,transform] duration-150 hover:bg-brand-100 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-brand-50"
                >
                  {label}
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

        <aside className={`${cardClass} overflow-hidden xl:sticky xl:top-4`}>
          <Tabs
            label="ویژگی‌ها"
            className="px-2"
            items={[
              { id: "element" as Tab, label: "ویژگی‌های جزء" },
              { id: "page" as Tab, label: "صفحه و سربرگ" },
            ]}
            value={tab}
            onChange={setTab}
          />
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
                <EmptyState compact icon={<MousePointerClick />} message="برای دیدن ویژگی‌ها، روی یکی از اجزای فرم کلیک کنید." />
              ))}
            {tab === "page" && (
              <div className="space-y-6">
                <PageSettingsPanel
                  settings={state.settings}
                  disabled={locked}
                  onChange={(settings) => edit((current) => ({ ...current, settings }))}
                />
                <section className="space-y-2 border-t border-slate-100 pt-4">
                  <h3 className="text-sm font-bold text-slate-800">لوگو</h3>
                  <LogoSection
                    endpoint={`/documents/${document.id}/logo/`}
                    logoUrl={content.logo_url}
                    canEdit={canEdit}
                    onChange={(logoUrl) => doc.setContent((current) => ({ ...current, logo_url: logoUrl }))}
                  />
                </section>
                <section className="space-y-2 border-t border-slate-100 pt-4">
                  <h3 className="text-sm font-bold text-slate-800">پاورقی</h3>
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
