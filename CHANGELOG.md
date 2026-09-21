# Changelog

Phase-level history of VEye V2. **Every commit that changes behaviour adds a line under `[Unreleased]`**
(format and rules: `docs/00-git-and-tracking.md`). Per-area detail lives in `docs/`; slice-by-slice detail in `git log`.

> Phases 0–5 were pushed to GitHub as one squashed snapshot (`504f945` … `a8de53a`), so their entries below are the record;
> git history is per-slice from Phase 6 on.

## [Unreleased]
- **Memberships and the people directory (Phase 7, slice 7.2 — backend only)**: `Membership` (person × node, `is_lead`, `is_primary`, free-text `position_label`), several per person. Invariant kept by `memberships.py`: **a person with any membership has exactly one primary** (first one is primary automatically, making another primary demotes the old, the only primary cannot be unset, removing it promotes the earliest remaining); each person's writes are serialised by a row lock on the user. API: `/org/memberships/` (read: any signed-in user; write: `manage_membership`; a membership's person and node never change — remove and re-add), `GET /org/nodes/{id}/members/` (leads first), and `GET /org/people/` (`?q=`, `?node=`, `?unassigned=1`). People and members expose name, سمت and places only — never the national code or phone number that `/personnel/` returns. Deactivated people keep their memberships but are hidden unless `?include_inactive=1`; they cannot be added to a node. Nodes with members can't be deleted (`members` joins the 409 counts), and archived nodes can't receive members. **Deleting a person who still has memberships is now a 409 `user_has_memberships`** (before this it would have been misreported as «has documents»). Name search normalises Arabic/Persian letters, digits and Unicode whitespace *in SQL* (no stored copy, no data migration); a test pins the SQL against `normalize_search_term`.
- **Organisation tree (Phase 7, slice 7.1 — backend only)**: new `apps.organization` with `Company` (singleton, `pk=1`) and `OrgNode` — one self-referencing table for شرکت / حوزه / واحد / بخش with a materialised `path` and stored `depth`. A واحد may hang directly under the company (a company with no حوزه is valid). The parent-kind table, the single root and sibling-unique names (on the normalised key, so Arabic and Persian yeh collide) live in the database as constraints; `tree.py` owns everything a CHECK cannot see (path/depth, cycle check on move, delete pre-flight) and checks first so callers get Persian errors. API: `GET /org/tree/` (flat, depth-first, one query; capped by `ORG_TREE_MAX_NODES`, over it two levels + `truncated` and `?parent=` lazy loading), `/org/nodes/` CRUD + `archive/` + `unarchive/`, `/org/company/` and its logo. Reads: any signed-in user. Writes: `manage_organization`. Nothing can create the `Company` row yet — bootstrap arrives in slice 7.4.
- **Three new capabilities**: `manage_organization`, `manage_membership`, `create_project` (کارفرمایی gets all three, ستادی gets `create_project`, صفی nothing; the مدیر عامل gets them automatically). They gate only the coarse "may I use this surface" question and never touch the five document capabilities. **There is deliberately no "read any conversation" capability and there must never be one**: the مدیر عامل is built from `Capability.values`, so it would silently hand that position everyone's private messages. Chat access will be membership-based only (a test pins that no capability name mentions conversations).
- Dev: opening the app on `http://127.0.0.1:3000` now redirects to `http://localhost:3000` (`next.config.ts`). Next blocked its dev resources for `127.0.0.1` (no hydration, so the login form silently reloaded) and the API's host-only session cookies live on `localhost`.
- Designer: after a successful «ذخیره» the app returns to «ساخت مستند» with a «ذخیره شد» message (as V_1.0 did).
- **مدیر عامل** (کارفرمایی لول ۱) now holds every capability (was approve + personnel + PDF only); the one-person-per-step rule still applies to him.

## Phase 6 — history, bulk print, dashboard extras, importer ✅ (docs: `10-phase-6.md`)
- **History screen** (`/documents/history`): revisions tab (filter, family chains, signers, PDF link) + activity tab (audit feed, filters). New `GET /history/revisions/` and `/history/activity/`; register search helpers extracted to `queries.py`. Docs: `10-phase-6.md`.
- **Dashboard extras**: «منتظر اقدام شما» card (`GET /dashboard/awaiting/`, same verdict as the register's buttons) and a recent-activity card.
- **چاپ لیست (bulk print)**: ZIP of already-built official PDFs for ticked rows or the current filter, with a preflight (ready / missing + reason), capped at `BULK_PRINT_MAX_FILES`; never renders. `GET /documents/bulk-print/[preflight/]`.
- **V_1.0 importer** (`manage.py import_v1`): Mongo (env-supplied URI) or a mongoexport file + local `saves/` and `img/` → Postgres, as a Celery job with a stored report; dry-run by default, skip-and-report on collisions, all-or-nothing writes with per-document savepoints, no network downloads; new `IMPORTED` audit event; `pymongo` dependency and a read-only `/import_data` mount.

## Phase 5 — Workflow, signatures, status, public verify ✅ (docs: `09-workflow.md`)
- State machine DRAFT → AWAITING_CONFIRMATION → AWAITING_APPROVAL → UNDER_CONTROL with مرجوع back to DRAFT (reason required, sign-offs cleared),
  one different person per step, row-locked transitions, typed 409s.
- Signer identity from the session; canvas signature pad; server normalises to an opaque PNG and refuses a blank pad.
- Audit trail (`DocumentEvent`), `GET /documents/{id}/history/`; designer shows the return banner + timeline; the designer's «نمایش» was wired.
- Approving a revision obsoletes the previous one and (re)builds PDFs.
- Public `/verify/{code}` page + rate-limited `GET /api/v1/verify/{code}/` (pending documents disclose nothing).
- 50 backend tests (11 mutations each caught), 12 frontend tests; run through the real Celery worker and the browser.

## Phase 4 — PDF engine ✅ (docs: `08-pdf-engine.md`)
- `apps/pdfgen`: the user's ReportLab renderer ported near-verbatim (bytes in/out, fonts registered once, crash fixes only, quirks preserved);
  adapter (Postgres → `PdfInput`), `PdfBuild` model, idempotent Celery task, atomic storage, API, register buttons چاپ / بازسازی / نمایش.
- Fidelity oracle: golden PDFs made by V_1.0's own code, asserted **byte-for-byte**; concurrency and empty-media checks.
- Decisions: explicit «ساخت PDF»; one file per revision replaced on rebuild; watermarked on-demand preview; Long `extra_boxes` printed; blank empty signature cells.
- New capability `print_document`. 63 backend tests, 7 frontend tests.

## Phase 3 — Document designer ✅ (docs: `04-designer.md`)
- Five block types, rich text markers, responsibilities, all-revision change history, attachment references, file uploads, logo (normalised to PNG),
  optimistic concurrency (`base_version`), content lock outside DRAFT, revisions start as a copy.

## Phase 2 — Document registry ✅ (docs: `03-document-registry.md`)
- `Document` (one row per revision), gapless race-free numbering (`DocumentSequence`), create / revise / search, register list without N+1.

## Phase 1 — Identity & RBAC ✅ (docs: `02-auth-and-rbac.md`)
- National-code login with httpOnly JWT cookies + CSRF, Redis token blacklist, login rate limit, personnel management, roll × level matrix, capabilities.

## Phase 0 — Foundations ✅
- Docker Compose (postgres, redis, backend, celery, frontend), settings split, Persian RTL Next.js 16 shell, vendored Vazir fonts, pinned PDF dependencies.
