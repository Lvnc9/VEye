# Document designer (Phase 3) — ✅ done

Code: backend `apps/documents/content.py` (save/copy/files/logo), `content_serializers.py`, `files.py`;
frontend `app/(app)/documents/[id]/edit/page.tsx`, `components/designer/*`, `lib/designer.ts`, `lib/rich-text.ts`.

## Content API
`GET /documents/{id}/content/` → the body; `PUT` replaces the **whole body in one transaction** keyed on the PK
(V_1.0 patched whichever row had an empty path).
- **Optimistic concurrency:** `PUT` carries `base_version`; stale → **409 `version_conflict`**
  (6-thread test: exactly one winner). `content_version` increments per save.
- **Locked** once status ≠ DRAFT → **409 `content_locked`** (reads stay open). Editing only happens in DRAFT.
- The document `date` is the last-saved date (from `content_saved_at`), as in V_1.0.

## Block types (`SectionType`, ordered by `position` — order is page order)
| Type | Content |
|---|---|
| Short Explanation (تشریحی کوتاه) | `lines[]` |
| Long Explanation (تشریحی بلند) | `heading`, `body`, `extra_boxes[]`, files |
| Responsibilities (مسئولیت ها) | 4 `ResponsibilityRow`s (role, post, supervisor, text) + notes; **one per document** |
| Changes Table (جدول تغییرات) | `ChangeTableRow`s (`text`, `date`); **one per document** |
| Attachment (ضمائم) | `AttachmentReference` items: `caption` + `target` (FK→Document, PROTECT) |
Section payload lives in `Section.content` (JSON) for Short/Long; the other three use child tables.

- **Rich text:** inline markers `**bold**`, `~~italic~~`, `--underline--` stored **verbatim**; the PDF
  renderer parses them. Nesting styles is refused (renderer can't). Helper: `lib/rich-text.ts`.
- **Responsibilities:** سمت/ناظر are **free text with the 9 titles as suggestions**. Roles map to the four rows
  الف/ب/ج/د. Both dropdown values in V_1.0 data are the placeholders `'Organiztion Post'`/`'SuperVisor'` → treat as empty.
- **Changes Table:** the *edition* printed = the owning document's `revision_display`; dates server-assigned;
  earlier revisions' rows are **frozen** and derived through `Document.previous_change_rows()` across the whole
  revision chain (not copied) — V_1.0 fetched only the immediately previous revision, so rev 3 lost rev 1's rows.
  No demo rows (V_1.0 pre-filled two hard-coded ones).
- **Attachments** reference other documents; can't self-attach; a linked row can be removed; unlinked rows are
  reported, not silently dropped.

## Revisions start as a copy (confirmed)
`services.create_revision` → `content.copy_content()`: blocks, footnotes, logo, attachments and **files
(physically copied)**; change rows are **not** copied (they derive from history).

## Files & logo
- Disk: `media/document_files/<doc-id>/<uuid>.<ext>`, `media/logos/<doc-id>/<uuid>.png`. Nothing user-controlled reaches a path.
- Upload `POST /documents/{id}/files/` — kind (picture/file/video) decided by extension (`FILE_EXTENSIONS`; `.xlsx` allowed);
  per-document dedup by SHA-256 (unique constraint + IntegrityError fallback); 100 MB cap. Download is
  **authenticated** (V_1.0's bucket was public).
- A file dropped from its block is deleted **on save** (via `transaction.on_commit`); an upload attached to nothing is
  swept by the next save. The UI holds Save while an upload is in flight.
- Logo: normalised to **PNG**, EXIF-rotated, ≤1024 px, ≤5 MB, ≤25 MP. **The PDF renderer only draws `.png` logos**
  (black box otherwise, `to_make_pdf.py:159-160`), which is why.

## Phase 4/5 additions to the designer page
The header now carries the workflow buttons (held while edits are unsaved), a red **return banner** when a reviewer sent the draft back (مرجوع), and the
«سوابق گردش کار» timeline; the save-bar **نمایش** builds a watermarked preview of the last *saved* version. Editing is only possible while DRAFT, so a
submitted document is read-only until a reviewer returns it. See [09-workflow.md](09-workflow.md).

## Frontend behaviours worth knowing
- `apiUploadWithProgress` uses XHR (fetch can't report upload progress).
- `fromResponse` keeps block keys across a save (else blocks remount mid-upload); blocks update via functional `update(s => …)`.
- Date-only strings are parsed as **local** dates (`new Date("2026-09-19")` is UTC midnight → previous day west of UTC).
- App shell is `h-screen overflow-hidden`; only `<main>` scrolls; the save bar is sticky inside `<main>`.
- ESLint `react-hooks/set-state-in-effect` is an **error**: derive loading state; only call setState in async callbacks.

## Not verified by hand
Ctrl/⌘+B/I/U shortcuts (toolbar buttons are verified); upload cancel button and progress bar mid-transfer;
picture/video uploads in a browser (backend-tested only).
