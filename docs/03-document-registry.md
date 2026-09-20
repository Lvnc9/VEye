# Document registry — ساخت مستند (Phase 2) — ✅ done

Code: `backend/apps/documents/` — `models.py`, `services.py`, `serializers.py`, `views.py`, `admin.py`,
tests in `tests.py`. Vocabulary in `apps/core/constants.py`. Frontend: `app/(app)/documents/page.tsx`.

## Data model (one row **per revision**)
`Document`: `category`, `title`, `group`, `number`, `revision` (1–99), `status`, `previous_revision`
(OneToOne self-FK — replaces V_1.0's `check/` HTTP fetch), `content_saved_at`, `content_version`, `logo`,
footnotes, `created_by` (**PROTECT**). Unique on `(group, number, revision)`.
Derived properties: `prefix`, `code` (`PR-01`), `revision_display` (`01`), `full_code` (`PR-01-01`),
`is_finalized`, `is_editable`, `action` (the row's next action), `responsibility_summary()`,
`previous_change_rows()`.
`DocumentSequence(group PK, last_number)` — the per-group counter. `SignOff(document, role, name,
position, signature ImageField, signed_date, signed_by)` — written by the workflow from the session; a return deletes the rows. `DocumentEvent` is the audit trail.
PDF state is **not** on `Document`: it lives in `pdfgen.PdfBuild` (one row per document × kind) — see [08-pdf-engine.md](08-pdf-engine.md).

### Vocabulary (`core/constants.py`)
- Groups → prefixes (**deliberately crossed**, ported literally): پوستر→`PO`, روش اجرایی→`PR`, دستورالعمل→`WI`, فرم→`FR`.
- Categories: داخل سازمانی / برون سازمانی. **The Persian labels are my translation**; V_1.0 stores the English
  strings `'Inside Organization'`/`'Outside Organization'`. `LEGACY_CATEGORY_VALUES` maps them for the importer.
- Statuses: `DRAFT`, `AWAITING_CONFIRMATION`, `AWAITING_APPROVAL`, `UNDER_CONTROL`, `OBSOLETE`
  (from the Dashboard's five columns). `FINALIZED_STATUSES` = everything except DRAFT.
  Transitions happen only through `apps/documents/workflow.py` (Phase 5): DRAFT → AWAITING_CONFIRMATION → AWAITING_APPROVAL → UNDER_CONTROL, مرجوع back to DRAFT,
  and approving a revision makes the previous UNDER_CONTROL one OBSOLETE.
- `SignOffRole` values `creater`/`confirmer`/`approver` — "creater" misspelling kept on purpose (V_1.0 field name).
- `SectionType`, `ResponsibilityRole`, `RESPONSIBILITY_ROW_LABELS` ["الف","ب","ج","د"], `REGISTER_COLUMN_ROLE`, `FileKind`.

## Numbering
Code `<PREFIX>-<NN>-<RR>`. Numbers come from a locked `DocumentSequence` row (`select_for_update` +
`get_or_create`) — **gapless and race-free**; a rejected create rolls its number back. Proven with real-thread tests.
V_1.0 derived the number from the *last row in the group*, which was racy and wrong (`simple_code` stuck at "1").
Draft shows revision `01`, not `00` (V_1.0's sentinel). Revision >99 is refused (V_1.0 wrapped silently).

## API (`/api/v1/`, all need auth; writes need `create_document`)
| Route | Notes |
|---|---|
| `GET /documents/` | 25/page. Filters `group`, `category`, `status` (unknown value → empty). `search` matches title, full code, category/group label; Persian/Arabic yeh-kaf and Persian digits normalised. 3 queries/page, N+1-free |
| `POST /documents/` | `{category,title,group}`. Existing title → **409 `title_exists`** (payload carries `existing_id`; message says finish the draft or create a revision) |
| `GET /documents/{id}/` | |
| `POST /documents/{id}/submit/ · confirm/ · approve/ · return/`, `GET .../history/`, `GET /verify/{code}/` | Phase 5 — see [09-workflow.md](09-workflow.md) |
| `GET /documents/bulk-print/preflight/`, `GET /documents/bulk-print/` | Phase 6 — چاپ لیست: ZIP of already-built PDFs for selected ids or the current filter — see [10-phase-6.md](10-phase-6.md) |
| `POST /documents/{id}/revise/` | previous revision must be finished (409 `previous_not_finished`); latest only; ≤99 (409 `revision_limit`). **The new revision is a copy** (see designer doc) |
| `GET/PUT /documents/{id}/content/` | designer body — see [04-designer.md](04-designer.md) |
| `POST /documents/{id}/files/`, `GET .../files/{fid}/download/`, `POST/DELETE .../logo/` | see designer doc |
| `GET/POST /documents/{id}/pdf/{official\|preview}/`, `.../download/` | Phase 4 — see [08-pdf-engine.md](08-pdf-engine.md). List rows gain `pdf_status`, `pdf_built_at` (subquery; still 4 queries/page) |
No edit/delete of a document via the API (V_1.0 offered neither).
Errors: `ConflictError` (409) carries a typed JSON payload (`code`, ids as ints) — reuse it for new conflicts.
Personnel routes: see [02-auth-and-rbac.md](02-auth-and-rbac.md). Dashboard: `/dashboard/metrics/`, `/dashboard/system-info/`.

## Register page
13 columns: ردیف, دسته بندی, عنوان, گروه, بازنگری, کد, حسابکش, پاسخ‌خواه, پاسخگو, تدوین, تائید, تصویب, وضعیت.
- حسابکش/پاسخ‌خواه/پاسخگو are derived from the Responsibilities block and **follow the row labels**
  (Cash Account / Receiver / Responder) — V_1.0's positional mapping was a swap.
- تدوین/تائید/تصویب show the signer's **name + Jalali date** (سمت in a tooltip), filled by the sign-off workflow (Phase 5).
- Row actions: تکمیل / ویرایش / مشاهده are live. **چاپ** (finalized rows: «ساخت PDF» → «در حال ساخت…» → «چاپ» + «بازسازی») and
  **نمایش** (watermarked preview, rows with a saved body) are live (Phase 4). The sign-off buttons (ارسال برای تایید / تایید / تصویب / مرجوع) come from
  each row's `workflow` field and replaced the old disabled «اتمام» (Phase 5, [09-workflow.md](09-workflow.md)).
- `Document.action` decides which button a row shows (`documents_01.py:886-902` semantics).

## Deliberate differences from V_1.0
- Typing an existing title is an error, not a silent new revision (two explicit operations).
- Revision search matches the displayed `01`, not the stored `"0-1"`.
- Documents can't be edited/deleted through the API.

## For the Phase 6 importer
- `number` from the stored `code` ("PO-01" → 1); **never trust `simple_code`**.
- `review "0-0"` → revision 1 + DRAFT; otherwise `revision = 10·one + two`.
- After import set `DocumentSequence.last_number` to max per group.
- Map category via `LEGACY_CATEGORY_VALUES`; normalise titles with `normalize_title` (V_1.0 mixes Arabic/Persian yeh).

## Gotchas
- SQL `LPad` truncates (`lpad('100',2,'0')`→`'10'`); search uses an explicit CASE.
- DRF `APIException` stringifies dict values → use `ConflictError` for typed payloads.
- Stale-migration collision on the dev DB (see `01-run-and-test.md`).
