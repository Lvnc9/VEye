# VEye V2 — read this first

Persian RTL controlled-document system (Django + DRF + PostgreSQL + Redis + Celery + Next.js 16, all storage local).
It is a rewrite of the V_1.0 desktop app (a sibling directory `../V_1.0`, its own repo — **never copy its secrets**).

## Orientation (do not re-read the whole project)
1. **`docs/README.md`** — current status table, ground rules, docs index. Start here.
2. Then only the doc for the area you touch (`docs/01`…`docs/09`); `docs/07-known-gaps.md` for open decisions; `docs/skeleton.md` for long-form architecture.
3. **`docs/00-git-and-tracking.md`** — commit format, one-slice-per-commit, pre-commit checklist. `CHANGELOG.md` for the phase-level history.
4. `git log --oneline` is the slice-by-slice story from Phase 6 on.

## Non-negotiables
- Persian RTL UI, Jalali dates, Persian error messages. Never ship English user-facing text.
- Postgres is the source of truth. The register list never renders a PDF; PDFs are built only on an explicit action (Celery).
- The PDF algorithm (`backend/apps/pdfgen/renderer.py`) is the user's — port, don't redesign; preserve its quirks. `python-bidi==0.6.11`.
- No secrets in code or git. Config comes from `.env` (git-ignored; template `.env.example`).
- Ask the user before deciding product behaviour (state machines, policies, what to print). Recommend an option for each.
- **Commit every slice** with the conventions in `docs/00-git-and-tracking.md`; update docs + `CHANGELOG.md` in the same commit. Push only when asked.

## Run / test (details: `docs/01-run-and-test.md`)
```bash
docker compose up -d
docker compose exec -T backend python manage.py test --noinput
docker compose exec -T frontend npx tsc --noEmit && docker compose exec -T frontend npm run lint && docker compose exec -T frontend npx vitest run
docker compose restart celery      # after any Celery-task change (no hot reload)
```
Next.js 16 differs from older versions: read `frontend/node_modules/next/dist/docs/` before writing Next code (`frontend/AGENTS.md`).
