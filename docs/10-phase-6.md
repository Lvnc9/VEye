# Phase 6 — history, dashboard extras, bulk print, importer ✅ done

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

## V_1.0 importer — `manage.py import_v1` ✅
Brings V_1.0's documents (MongoDB index rows + `saves/*.json` contents + `img/` signatures and logos) into Postgres. **Decided with the user:** rows from a live Mongo (connection string in an *environment variable, at run time*) **or** a
`mongoexport` file; **skip-and-report on collisions, dry-run by default**; **local files only — nothing is downloaded from the Liara URLs**; runs as a **Celery job started by a management command** (`--sync` runs inline).
V_1.0's committed credentials are never used, read or copied; nothing in the repo contains a connection string.

### How to run it
```bash
# 1. Stage the data (git-ignored; it contains real names and signatures — never commit it):
mkdir -p import_data && cp -R <V_1.0>/saves import_data/saves && cp -R <V_1.0>/img import_data/img
#    and either: mongoexport --db my_database --collection my_collection --jsonArray --out import_data/rows.json
#    or:         put the Mongo connection string in an env var the *worker* sees (e.g. MONGO_URI in V_2.0/.env, then `docker compose up -d celery`)
# 2. Dry run (the default — parses and checks everything, writes NOTHING, prints what would happen):
docker compose exec backend python manage.py import_v1 --index-file /import_data/rows.json          # or: --mongo-uri-env MONGO_URI
# 3. Read the report (skipped / errors / warnings), fix the data or accept it, then really import:
docker compose exec backend python manage.py import_v1 --index-file /import_data/rows.json --commit
# Later:  --status RUN_ID  (re-print a report)   --report-file out.json   --sync (inline, no Celery)   --v1-dir DIR (default /import_data)
#         --mongo-db my_database --mongo-collection my_collection  (V_1.0's defaults, utils.py MongoDBClient)
```
`/import_data` inside the containers is `./import_data` on the host (`V1_IMPORT_DIR` overrides), mounted read-only on `backend` and `celery`. Only one import may run at a time (a run older than 2 h no longer blocks).
Imported documents are **not** given PDFs: finalized ones show «ساخت PDF» in the register, as usual.

### What is read and how it maps (`apps/importer/mapping.py`, pure functions)
| V_1.0 | V_2 |
|---|---|
| index row `code` "PO-01" | `group` + `number` (**never `simple_code`** — V_1.0 stored it wrongly after any revision). The prefix must match the group's (the deliberately crossed prefixes), else the row is an error |
| `review` "tens-units" | `revision` = 10·tens + units (1–99); **"0-0" = never saved → revision 1 + DRAFT** |
| `valid` | `vali` (V_1.0's typo) → UNDER_CONTROL, `outdated` → OBSOLETE, anything else → DRAFT (V_1.0 never wrote `status`). `vali` on a "0-0" row is downgraded to DRAFT with a warning |
| `group` (Persian, Arabic-yeh variants) | `DocumentGroup`; `category` "Inside/Outside Organization" → `DocumentCategory` (unknown → داخل سازمانی + warning); `title` normalised (Arabic→Persian letters) |
| content JSON | header (date → `content_saved_at` at 12:00 Tehran; logo; footnotes), sections in order: Short → lines; Long → heading/body/`extra_boxes`; Responsibilities → the 4 role rows (post = option *i*, supervisor = *i+4*, **the placeholders "Organiztion Post"/"SuperVisor" become empty**) + notes; Changes Table → this revision's own rows only (V_1.0's frozen `label` rows are skipped: V_2 derives them from the revision chain); Attachment → `[caption, "CODE-REV", qr]` resolved to documents (QR path dropped) |
| signers `[name, post, signature URL]` | `SignOff` (finalized documents only): name/post as stored, signature = `img/<last segment of the URL>` normalised to an opaque PNG, date = the document date, `signed_by` empty (V_1.0 has no accounts). Drafts' signers are ignored (noted). The index row's overwritten `[name, date]` shape is used when the JSON has none |
| `json_path` | only its **last path segment** is used, to find `saves/<name>`; fallback `saves/<title>-<CODE-REV>.json`. A file whose `document_number` belongs to another document is **not** used (`content_mismatch`; "…-00" on a revision-1 file is accepted) |
| — | `created_by` = an inactive, password-less account «واردسازی از نسخهٔ ۱» (`national_code` `v1-import`); one `IMPORTED` audit event per document (points at the run); `created_at` = the saved date; `previous_revision` = the nearest lower revision (if it has no successor yet); `DocumentSequence` raised to the highest imported number per group, **never lowered** |

Behaviour decisions inside the importer (mine, consistent with the approved rules — tell me if you disagree): **V_1.0 never marked a superseded revision**, so an UNDER_CONTROL revision that has a *later UNDER_CONTROL revision in the same batch* is imported as **OBSOLETE** (as V_2's approval would have made it; reported `superseded_on_import`);
signer *names* are kept exactly as stored (Arabic yeh/kaf included — they print on the PDFs as V_1.0 printed them), unlike titles which are normalised.

### Collisions, atomicity, idempotency
- A row whose (group, number, revision) already exists is **skipped** (`exists`) and never touched; a revision-1 title already used in the group is skipped (`title_conflict`); a repeated row in the source is an error (`duplicate_in_source`). Re-running is therefore safe, and a partial source can be completed by a second run.
- A real run writes inside **one outer transaction with a savepoint per document**: a document that fails is rolled back alone and reported (`import_failed`, cause in the server log only) while the rest continue; a failure of the run itself (attachment linking, the sequence bump, the database) rolls **everything** back and deletes the logo/signature files it wrote. *(This structure exists because the first real run found a bug: the sequence bump ran outside a transaction after the documents had already committed, leaving a half-finished import.)*
- Attachments are linked in a second pass once every document of the run exists; a label that names no known document is dropped and reported (`attachment_unresolved`).

### The report
`ImportRun` (Postgres, read-only in the admin): status queued/running/succeeded/failed, dry-run flag, progress (`processed`/`total`), `counts` `{total, created | would_create, skipped, errors, warnings, superseded}` and `report` = one entry per row `{position, code, title, action, notes[{level, code, message (Persian)}]}`.
Note codes: `exists`, `title_conflict`, `duplicate_in_source`, `bad_review`, `bad_code`, `code_group_mismatch`, `unknown_group`, `missing_title`, `unknown_category`, `unknown_valid`, `valid_but_never_saved`, `no_content`, `content_missing`, `content_mismatch`, `logo_missing`/`logo_unreadable`, `signature_missing`/`signature_unreadable`,
`no_signers`, `signers_ignored_on_draft`, `links_not_migrated` (Long-block file links are *counted*, not migrated), `frozen_change_rows`, `bad_change_date`, `attachment_unresolved`, `attachment_self`, `superseded_on_import`, `import_failed`. The command prints only the notable lines plus a Persian summary.
**Secrets:** `options` stores only the *name* of the environment variable; the URI is read in the process that runs the job, never stored, logged or sent through the broker; a driver error is reported as its class name only (tested with a URI containing a marker password).

### Verified
- **84 backend tests** (mapping 27, importer against Postgres/task/command 40, sources & file safety 17). **26 deliberate breakages, all caught** — including 0-0→revision 0, status mapping, `simple_code`, placeholders, frozen rows, supersede, collisions, dry-run writing, the outer transaction, file cleanup, the sequence bump, path traversal, symlink escape, Arabic/Persian file names, secret echoing and task redelivery.
- **Against the real V_1.0 files** (staged locally, then removed): rows synthesised from the `saves/*.json` (I don't have your Mongo export) → dry run, then a real run *through Celery*: 9 documents, real signatures and logos imported, sequences raised, supersede applied. **The imported «نمونه» (PR-01-01) renders as V_1.0's own archived `نمونه-PR-01-01.pdf`**: same layout, names, posts, three signatures, logo, footnotes and Jalali date (only the QR differs, by design); the History screen lists the imported documents in printed-code order with their signers.
- **Not verified:** a run against a **live MongoDB** (`--mongo-uri-env`) — only against a fake driver (I have no database and must not use V_1.0's credentials): the first real use should be a dry run; large volumes/timing (the task limit is 1 h; ~10 documents take well under a second); Long-block file links and any document whose content lives only in the Liara bucket (reported, not migrated — you chose local files only); `img/` names that differ from the URLs' last segment.
