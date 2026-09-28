"use client";

import {
  canAddSection,
  fromResponse,
  moveSection,
  rekey,
  newSection,
  snapshot,
  toPayload,
  validate,
  type DesignerState,
} from "@/lib/designer";
import { SECTION_TYPES, SECTION_TYPE_LABELS, type ContentResponse, type DesignerSection, type SectionType } from "@/lib/types";
import { BlockFrame } from "./BlockFrame";
import { ShortBlock } from "./ShortBlock";
import { LongBlock } from "./LongBlock";
import { ResponsibilitiesBlock } from "./ResponsibilitiesBlock";
import { ChangesBlock } from "./ChangesBlock";
import { AttachmentBlock } from "./AttachmentBlock";
import { DesignerShell } from "./DesignerShell";
import { LivePaper } from "./LivePaper";
import { PaperLayout } from "./PaperLayout";
import { FootnoteFields } from "./FootnoteFields";
import { LogoSection } from "./LogoSection";
import { useDesignerDocument, type DesignerAdapter } from "./useDesignerDocument";
import { useDragReorder } from "./useDragReorder";
import { moveElement } from "@/lib/reorder";

const classicAdapter: DesignerAdapter<DesignerState> = {
  fromResponse: (response, previous) => fromResponse(response, previous?.sections),
  toPayload,
  snapshot,
  validate,
  rekey,
};

/** طراحی مستند — V_1.0's Poster screen (poster_01.py): the five block types. */
export function ClassicDesigner({ initial }: { initial: ContentResponse }) {
  const doc = useDesignerDocument(initial, classicAdapter);
  const { content, state, setState, canEdit, locked } = doc;
  const document = content.document;

  function updateSection<T extends DesignerSection>(key: string, updater: (section: T) => T) {
    setState((current) => ({
      ...current,
      sections: current.sections.map((s) => (s.key === key ? updater(s as T) : s)),
    }));
    doc.setNotice(null);
  }

  const drag = useDragReorder((from, to) => {
    setState((current) => ({ ...current, sections: moveElement(current.sections, from, to) }));
    doc.setNotice(null);
  });

  function addSection(type: SectionType) {
    setState((current) => ({ ...current, sections: [...current.sections, newSection(type)] }));
    doc.setNotice(null);
  }

  // The paper shows the unsaved edits while there are any, otherwise what is stored.
  const paperBody = canEdit && doc.dirty ? toPayload(state) : null;

  return (
    <DesignerShell doc={doc} wide>
      <PaperLayout
        paper={<LivePaper documentId={document.id} body={paperBody} refreshKey={content.logo_url ?? ""} />}
        editor={
          <>
            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-3 text-lg font-semibold text-slate-900">سربرگ</h2>
              <LogoSection
                endpoint={`/documents/${document.id}/logo/`}
                logoUrl={content.logo_url}
                canEdit={canEdit}
                onChange={(logoUrl) => doc.setContent((current) => ({ ...current, logo_url: logoUrl }))}
              />
            </section>

            {canEdit && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-slate-600">افزودن بخش:</span>
                {SECTION_TYPES.map((type) => (
                  <button
                    key={type}
                    type="button"
                    disabled={locked || !canAddSection(state.sections, type)}
                    onClick={() => addSection(type)}
                    title={canAddSection(state.sections, type) ? undefined : "در هر مستند فقط یک بخش از این نوع مجاز است."}
                    className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    + {SECTION_TYPE_LABELS[type]}
                  </button>
                ))}
              </div>
            )}

            <div className="space-y-4">
              {state.sections.length === 0 && (
                <div className="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-10 text-center text-sm text-slate-500">
                  {canEdit ? "هنوز بخشی اضافه نشده است. از دکمه‌های بالا استفاده کنید." : "این مستند هنوز محتوایی ندارد."}
                </div>
              )}

              {state.sections.map((section, position) => {
                const index = position + 1;
                const common = { index, disabled: locked };
                return (
                  <BlockFrame
                    key={section.key}
                    type={section.type}
                    index={index}
                    total={state.sections.length}
                    disabled={locked}
                    drag={drag}
                    dragKey={section.key}
                    onMove={(direction) =>
                      setState((current) => ({ ...current, sections: moveSection(current.sections, position, direction) }))
                    }
                    onRemove={() => {
                      if (!window.confirm("این بخش حذف شود؟")) return;
                      setState((current) => ({ ...current, sections: current.sections.filter((s) => s.key !== section.key) }));
                    }}
                  >
                    {section.type === "Short Explanation" && (
                      <ShortBlock section={section} {...common} update={(u) => updateSection(section.key, u)} />
                    )}
                    {section.type === "Long Explanation" && (
                      <LongBlock
                        section={section}
                        {...common}
                        documentId={document.id}
                        trackUpload={doc.trackUpload}
                        update={(u) => updateSection(section.key, u)}
                      />
                    )}
                    {section.type === "Responsibilities" && (
                      <ResponsibilitiesBlock section={section} {...common} update={(u) => updateSection(section.key, u)} />
                    )}
                    {section.type === "Changes Table" && (
                      <ChangesBlock
                        section={section}
                        {...common}
                        previous={content.previous_changes}
                        revisionDisplay={document.revision_display}
                        update={(u) => updateSection(section.key, u)}
                      />
                    )}
                    {section.type === "Attachment" && (
                      <AttachmentBlock
                        section={section}
                        {...common}
                        documentId={document.id}
                        update={(u) => updateSection(section.key, u)}
                      />
                    )}
                  </BlockFrame>
                );
              })}
            </div>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-3 text-lg font-semibold text-slate-900">پاورقی</h2>
              <FootnoteFields
                footnote1={state.footnote1}
                footnote2={state.footnote2}
                disabled={locked}
                onChange={(next) => setState((current) => ({ ...current, ...next }))}
              />
            </section>
          </>
        }
      />
    </DesignerShell>
  );
}
