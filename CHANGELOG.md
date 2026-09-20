# Changelog

Phase-level history of VEye V2. **Every commit that changes behaviour adds a line under `[Unreleased]`**
(format and rules: `docs/00-git-and-tracking.md`). Per-area detail lives in `docs/`; slice-by-slice detail in `git log`.

> Phases 0–5 were pushed to GitHub as one squashed snapshot (`504f945` … `a8de53a`), so their entries below are the record;
> git history is per-slice from Phase 6 on.

## [Unreleased] — Phase 6: history, bulk print, dashboard extras, importer
- **History screen** (`/documents/history`): revisions tab (filter, family chains, signers, PDF link) + activity tab (audit feed, filters). New `GET /history/revisions/` and `/history/activity/`; register search helpers extracted to `queries.py`. Docs: `10-phase-6.md`.
- _(further entries are added per commit below)_

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
