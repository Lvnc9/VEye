# Phase 6 — history, dashboard extras, bulk print, importer (in progress)

Decisions (asked of the user, all confirmed): **History** = two tabs (revisions + activity). **Bulk print** = a ZIP of already-built official PDFs for selected rows or
the current filter, with a preflight, never rendering. **Dashboard** = an «awaiting you» card + the last 10 workflow events. **Importer** = live Mongo via `MONGO_URI`
(env, at run time) *or* a mongoexport file, plus local `saves/` and `img/`; **skip-and-report on collisions, dry-run by default**; **local files only — never download** from the
Liara URLs; runs as a **management command that queues a Celery job** (`--sync` inline).
Commit-by-commit record: `git log --oneline` and `CHANGELOG.md`.

## History screen — سوابق مستندات (`/documents/history`) ✅
V_1.0's «Document History» button was dead (`main.py:909` called a handler with no arguments → TypeError), so this is a new feature. Read-only, open to any signed-in user
(like the register), and it never opens or renders a PDF.

| Route | Notes |
|---|---|
| `GET /history/revisions/` | every revision of every document; filters `search` (**the register's search**: title, printed code incl. revision, group/category label, Persian/Arabic letters), `group`, `category`, `status` (unknown → empty), `family` (e.g. `PR-01` = one document's whole chain; malformed → empty). Ordered by the **printed code prefix** (FR, PO, PR, WI), then number, newest revision first. Row: code, revision, title, group/category/status labels, the three sign-offs (name, post, date), `pdf_status`/`pdf_built_at` of the *issued* PDF (subquery; a preview doesn't count), created/saved times. 3 queries per page |
| `GET /history/activity/` | the audit trail across all documents (`DocumentEvent`), newest first; filters `kind`, `document` (id), `q` (document title/code, register search), `actor` (name contains), `days` (last N; ≤0 / non-numeric → empty). Row: document `{id, full_code, title}`, kind, from/to status (+labels), actor name/post, reason, time. 2 queries per page; never exposes user ids |

Code: `apps/documents/history.py`, shared helpers in `apps/documents/queries.py` (extracted from `views.py` in a separate refactor commit: `search()`, `full_code_expression()`, `prefix_expression()`, `with_official_pdf()`).
Frontend: `app/(app)/documents/history/page.tsx` (filters live in the page so switching tabs keeps them), `components/history/{RevisionsTab,ActivityTab,DebouncedInput}.tsx`, `components/Pager.tsx`,
`lib/history.ts` (query building, vocabularies), `lib/use-paged-query.ts` (paged fetch with *derived* loading — a lint rule forbids sync setState in effects), `formatJalaliDateTime` in `lib/jalali.ts`, `pdfDownloadUrl` in `lib/pdf.ts`.
Interactions: clicking a code (either tab) narrows the revisions tab to that family; the activity feed links each document to its designer page. The sidebar now highlights only the most specific matching item (so `/documents/history` doesn't also light up «ساخت مستند»).

Verified: 18 backend tests (filters, ordering, N+1 guards, pagination, a real workflow feeding the feed; **7 mutations each caught**), 6 frontend unit tests; in the browser with data made by the real workflow — revisions tab, family filter,
activity feed, kind filter. **Not verified:** the «باز کردن» PDF link from the revisions tab (same route as the register's چاپ, which was verified in Phase 4), the actor/`q`/days filters and pagination in the browser (API-tested), a very narrow (phone) layout.
Known limits: `actor` search normalises the term but event names are stored as typed, so a name entered with Arabic letters may not match a Persian-letter search; the activity feed has no Jalali date-range picker (a «last N days» select instead).

## Dashboard extras ✅
The counts table and system info already existed (Phase 2/3). Added two cards on `/dashboard`:
- **«منتظر اقدام شما»** — `GET /dashboard/awaiting/`: documents waiting for the *signed-in user's* step (the closest thing to V_1.0's dead کارتابل button).
  Uses **the workflow's own verdict** (`workflow.next_step_for(...).can_act`), so it can never disagree with the register's buttons: a step the user's roll can't take, or that they are barred
  from as an earlier signer, is not listed. **Drafts count only when the user created them** (otherwise every author would see everyone's unsent drafts) and only once a body is saved.
  Returns `{count, by_step: {submit, confirm, approve}, items[≤20, longest-waiting first]}`; `count` covers everything, the list is capped; scans at most 500 candidates. Not cached (per user; 2 queries).
  Each item links to the document (its header has the sign-off buttons); `waiting_since` is the document's `updated_at`, i.e. when its status last changed hands.
- **«فعالیت‌های اخیر»** — the last 10 events, read from `GET /history/activity/?page_size=10` (no new endpoint), with a link to the History screen.
Frontend: `components/dashboard/{AwaitingCard,RecentActivityCard}.tsx`, `lib/use-api-query.ts`; each card fetches on its own so one failing card doesn't blank the dashboard.
Verified: 9 backend tests (`apps/dashboard/tests.py`; the card agrees with the register's `workflow.can_act`; 2-query guard; **6 mutations: 5 caught, 1 equivalent** — the capability `Q` only narrows the scan, `next_step_for` re-checks capabilities anyway);
browser: as the approver the card listed the one document awaiting approval and the activity card showed the newest events; API-checked for the confirmer (0) and author (their 2 drafts).
Not verified: the empty state in the browser, the «N مورد دیگر» overflow line (test-covered via the cap), phone layout.

## چاپ لیست — bulk print ✅
V_1.0 had no such feature. **A ZIP of already-built official PDFs** for the ticked rows, or — with nothing ticked — the register's current filter (no filter = every document). It **never renders or builds**;
what isn't ready is listed with the reason, so it can be built first (then come back).

| Route | Notes |
|---|---|
| `GET /documents/bulk-print/preflight/` | selection = `?ids=1,2,3` (≤1000, de-duplicated; bad → 400) **or** the register filters `search`/`group`/`category`/`status` (same code as the register, `queries.apply_filters`; an unknown value selects nothing rather than everything). Returns `{total, cap, truncated, ready, missing:[{id, full_code, title, reason, reason_label}]}`. Reasons: `not_finalized` (هنوز نهایی نشده), `not_built`, `building`, `failed`, `file_missing` (row says READY but the file is gone). 3 queries whatever the size |
| `GET /documents/bulk-print/` | the ZIP (`documents-YYYY-MM-DD.zip`, `attachment`, `Cache-Control: private, no-store`, headers `X-Bulk-Print-Count/-Missing`). Entries `<title>-<code>.pdf` (V_1.0's naming; unsafe characters replaced, collisions numbered), ordered by printed code, **stored not deflated** (PDFs are compressed). **409 `nothing_to_print`** if the selection has no built PDF |

- **Cap:** `BULK_PRINT_MAX_FILES` (default 200, env-overridable): the first N by printed code are packed and `truncated: true` says so — the dialog tells the user to narrow the selection.
- A document counts as ready whenever its **official** build row has a file that exists — including while a *re*build runs or after a failed one (the previous file is still the issued one, as in Phase 4). A **preview is never a candidate.**
- Authenticated only (like PDF downloads); a GET so the browser just navigates with its cookie. The route is registered *before* the documents router (`config/urls.py`) or `documents/<pk>/` would swallow it.
- Code: `apps/pdfgen/bulk.py` (selection, plan, archive names, ZIP), two views in `pdfgen/views.py`. Frontend: checkbox column + «چاپ لیست (…)» button on the register (selection is tied to the filters it was made under and reads as empty when they change; it persists across pages),
  `components/BulkPrintDialog.tsx` (preflight summary, missing list, download), `lib/bulk-print.ts` (+ tests).
- Verified: 22 backend tests (ZIP contents byte-identical to the stored PDFs, reasons, filters, cap, never-renders guard via patched renderer/adapter/build service, 3-query guard, name sanitising; **9 mutations: 8 caught, 1 equivalent** (swapping the builds query for another single query)),
  5 frontend tests; in the browser: dialog on «all documents» (2 ready / 3 not final, correct reasons), download request 200 (115 KB), selection label + «لغو انتخاب»; the ZIP built from the seeded data opens and holds valid PDFs with Persian names.
- **Not verified:** the saved file in the browser's Downloads folder (I confirmed the request and inspected the same response via the API), the truncated-list message in the UI (API-tested), phone layout. No merged single PDF (not chosen; would need a PDF-merge dependency + a job).
