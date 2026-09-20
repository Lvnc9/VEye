# VEye V2 — status report for agents (start here)

**Purpose:** let you resume work without re-reading the codebase. Read this file,
then only the doc for the area you touch. [`skeleton.md`](skeleton.md) is the long-form
architecture + tracker (~37 KB) — open it only for depth, not orientation.

*Last updated: 2026-09-20, after Phase 5. Backend 259 tests, frontend 57 tests, all green.*

## What this project is
VEye is an ISO-style **controlled-document system** in Persian (RTL). Staff register a
document slot (`PR-01-01`), compose its body from ordered blocks, route it through
تدوین → تایید → تصویب with signatures, and publish a Persian PDF with a QR code and a
validity mark. **V_1.0** (`/V_1.0`) is the original CustomTkinter desktop app (Mongo + S3);
**V_2.0** (`/V_2.0`) is the rewrite: Django + DRF + PostgreSQL + Redis + Celery backend,
Next.js 16 frontend, **all storage local** (no Mongo, no S3).

## How much of the plan is deployed

| Phase | Scope | Status |
|---|---|---|
| 0 | Foundations, cleanup, Persian RTL shell, deps, fonts, Celery service | ✅ Done |
| 1 | Identity & RBAC (national-code login, personnel, capabilities) | ✅ Done |
| 2 | Document registry — ساخت مستند list, create, revise, search | ✅ Done |
| 3 | Document designer — 5 block types, files, logo, revision copy | ✅ Done |
| 4 | PDF engine — port `to_make_pdf.py`, build via Celery | ✅ Done |
| 5 | Workflow: sign-off, signatures, 5-state machine, مرجوع, `/verify/` page | ✅ Done |
| 6 | Dashboard extras, History screen, چاپ لیست, Mongo→Postgres importer | ❌ Not started |

Roughly **6 of 7 phases (~85 % of the work)** — the whole document lifecycle now works end to end: register → design → sign
(تدوین/تایید/تصویب, مرجوع) → PDF → public verify. What does not exist yet: the Document History screen, چاپ لیست
(bulk print), the dashboard extras, and the Mongo → Postgres importer. **Next: Phase 6.**

**Live user-facing screens:** `/login`, `/dashboard` (real counts), `/documents` (register),
`/documents/[id]/edit` (designer, read-only when not draft), `/personnel/register`, `/account`,
`/settings` (stub), and the **public** `/verify/[code]` (no login — what a QR code opens). Register row buttons: **ارسال برای تایید / تایید / تصویب / مرجوع**
(server-decided per user, signature pad dialog), **چاپ** and **نمایش** (PDF). Still disabled with a tooltip: سوابق مستندات (Phase 6).
Documents now leave DRAFT through the workflow — see [09](09-workflow.md); you need three different people (صفی/ستادی → ستادی → کارفرمایی).

## Docs index
| File | Read when you… |
|---|---|
| [01-run-and-test.md](01-run-and-test.md) | run the stack, run tests, hit an environment problem |
| [02-auth-and-rbac.md](02-auth-and-rbac.md) | touch login, cookies, permissions, personnel |
| [03-document-registry.md](03-document-registry.md) | touch `Document`, numbering, the register list, API routes |
| [04-designer.md](04-designer.md) | touch content blocks, files, logo, revisions-as-copies |
| [05-dashboard-and-frontend.md](05-dashboard-and-frontend.md) | touch any Next.js page, the API client, or the dashboard |
| [06-v1-reference.md](06-v1-reference.md) | need to consult V_1.0 (live vs dead files, quirks, secrets) |
| [07-known-gaps.md](07-known-gaps.md) | want open bugs, unverified items, decisions still pending |
| [08-pdf-engine.md](08-pdf-engine.md) | touch PDFs: the renderer port, build task/API, quirks, golden-file oracle |
| [09-workflow.md](09-workflow.md) | touch sign-off, status transitions, مرجوع, the audit trail, signatures, the public verify page |
| [00-git-and-tracking.md](00-git-and-tracking.md) | commit, branch, changelog and docs conventions — **read before your first commit** |
| [new-chat-prompt.md](new-chat-prompt.md) | the ready-to-paste prompt for opening a fresh chat on this project |
| [archive/](archive/) | finished phase briefs and old kickoff prompts (historical; they still say `.claude/`, which is now `docs/`) |

## Ground rules that apply everywhere
1. **Persian RTL UI**, Jalali dates, Persian error messages. Never ship English user-facing text.
2. **Postgres is the only source of truth.** The register list never opens or renders a PDF.
3. **PDFs are built only on an explicit action**, as a Celery task; چاپ لیست only downloads built files.
4. **The PDF algorithm is the user's** (`V_1.0/other_folder/to_make_pdf.py`) — port it, don't redesign it.
5. **No secrets in code.** V_1.0 has hard-coded Mongo/S3/login credentials; none may be copied. Config comes from `V_2.0/.env`.
6. Work in **vertical slices**; verify in the browser as well as with tests; update this folder and
   `skeleton.md` §7 when a phase completes — **and commit each slice as you go** ([00-git-and-tracking.md](00-git-and-tracking.md)).
7. Be suspicious of tests that pass first time — prior phases mutation-tested critical logic.

## Repo map (V_2.0)
```
V_2.0/
  docker-compose.yml   postgres · redis · backend · celery · frontend
  .env / .env.example  all configuration
  backend/
    config/            settings (base/dev/prod), celery.py, urls.py
    apps/core/         constants (Persian vocabulary), text normalisation, ConflictError, HasCapability, pagination
    apps/accounts/     User (national code), roll×level matrix, capabilities, JWT cookie auth, personnel API
    apps/documents/    models, services, content (designer), files, serializers, views  ← the domain
    apps/pdfgen/       PDF engine: ported renderer, adapter, PdfBuild model, Celery task, API, golden tests
                       (workflow.py + verify.py live in apps/documents/: the state machine and the public verify endpoint)
    apps/dashboard/    real aggregate counts, cached in Redis, signal invalidation
    assets/fonts/      Vazir.ttf + Vazir-Bold.ttf (the repo-root pair)
    requirements/      pinned deps incl. reportlab/bidi/reshaper/qrcode/jdatetime
    media/             uploaded files (docker volume)
  frontend/
    proxy.ts           route guard (Next 16 replacement for middleware.ts)
    app/(auth)/login   app/(app)/{dashboard,documents,personnel,account,settings}
    components/        Code, StatusBadge, StatusBanner, PdfActions, WorkflowActions, SignatureDialog, ReturnDialog, WorkflowTimeline, designer/*
    app/verify/[code]  public QR landing page (no auth)
    lib/               api-client, types, current-user, jalali, rich-text, designer, pdf, workflow, verify
```
Media on disk: `media/pdfs/<doc-id>/<code>.pdf`, `media/pdf_previews/<doc-id>.pdf` (plus designer files/logos).
