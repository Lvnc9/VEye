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
