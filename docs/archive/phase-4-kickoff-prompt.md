> **Historical.** Written before the docs moved into the repo: `.claude/docs/…` is now `docs/…` and `.claude/skeleton.md` is `docs/skeleton.md`.

# Prompt used for Phase 4 — ✅ completed (kept for reference; Phase 5 needs a new one)

```
You are continuing VEye V2, a Persian RTL controlled-document system being rewritten from a desktop app
(/Users/samlv/WorkFlow/VEye/V_1.0) into Django + DRF + PostgreSQL + Redis + Celery + Next.js 16
(/Users/samlv/WorkFlow/VEye/V_2.0). All storage is local; no Mongo, no S3.

START HERE — do not re-read the whole project:
1. Read /Users/samlv/WorkFlow/VEye/.claude/docs/README.md. It has the plan-deployed table, ground rules and a docs index.
   Phases 0–3 (foundations, auth/RBAC, document registry, document designer) are DONE and verified — roughly 4 of 7 phases.
   Phases 4 (PDF engine), 5 (workflow/signatures/verify page/status machine) and 6 (history, چاپ لیست, Mongo importer) are NOT started.
2. Read .claude/docs/phase-4-brief.md (your task), 07-known-gaps.md (open decisions), and 01-run-and-test.md (how to run/test).
3. Open 03-document-registry.md and 04-designer.md before touching the data model; 06-v1-reference.md before reading V_1.0.
   .claude/skeleton.md is the long-form architecture and tracker — consult a section only when the docs point you there.

YOUR TASK: Phase 4 — port the user's PDF generator (V_1.0/other_folder/to_make_pdf.py + the Provider in deliver_convert.py) into
V_2.0/backend/apps/pdfgen/, sourcing data from Postgres, and build PDFs as a Celery task on an explicit user action. The register
list must never render PDFs. QR codes point at {FRONTEND_BASE_URL}/verify/{code}-{revision}.

NON-NEGOTIABLE:
- The PDF algorithm is the user's. Port it as written; fix only crash-level bugs listed in the brief; preserve its quirks.
- Pin python-bidi==0.6.11 and import get_display from bidi.algorithm. Use the vendored Vazir fonts via settings.PDF_FONT_*.
- No module-global state (concurrent Celery tasks must not corrupt each other). Register fonts once in AppConfig.ready().
- Never copy or print V_1.0's hard-coded credentials (Mongo, S3, login dict). Config comes from V_2.0/.env only.
- Persian for all user-facing text. Use ConflictError for typed 409s and HasCapability for permissions.

ASK THE USER BEFORE DECIDING (batch into one AskUserQuestion; give a recommendation for each):
build trigger/states; where built PDFs are stored and whether rebuilds replace them; whether نمایش renders a watermarked preview
on demand; whether to print Long-block extra_boxes/file links (V_1.0 silently drops them); how to render empty signature cells
before Phase 5.

DEFINITION OF DONE (details in the brief): fidelity check against archived V_1.0 PDFs (look at the rendered pages yourself),
two-simultaneous-builds concurrency test, fresh-empty-media test, backend + frontend tests / lint / tsc / build green,
`docker compose restart celery` after task changes, browser verification of the enabled چاپ/نمایش actions.
Then UPDATE the docs: README status table, add .claude/docs/08-pdf-engine.md, and .claude/skeleton.md §7. Report honestly what
was and wasn't verified. Stop after Phase 4 — do not start Phase 5.

Environment notes: Docker Desktop must be running (`open -a Docker`, then `docker compose up -d` in V_2.0). Dev logins are in
01-run-and-test.md. The Celery worker has no hot reload. Next.js 16 differs from your training data — read
frontend/node_modules/next/dist/docs/ before writing Next code.
```
