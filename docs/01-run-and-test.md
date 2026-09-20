# Run, test, environment

All commands from `/Users/samlv/WorkFlow/VEye/V_2.0`.

## Run
```bash
docker compose up -d            # postgres:5432 redis:6379 backend:8000 celery frontend:3000
docker compose ps
docker compose logs -f backend
```
Docker Desktop must be running first (`open -a Docker`). The backend container runs
`migrate` then `runserver`; the frontend runs `npm run dev`.

| Situation | Fix |
|---|---|
| `requirements/*.txt` changed | `docker compose up -d --build backend celery` (the stale image crashes on `import celery`) |
| **Celery code changed** (anything `pdfgen` imports) | `docker compose restart celery` — the worker has **no hot reload** (`docker compose logs celery` should list `pdfgen.build_pdf`) |
| Frontend 404s every route / "both middleware.ts and proxy.ts" | `docker compose restart frontend` (dev server latches the error; disk is fine) |
| "No migrations to apply" but columns are wrong | stale tables from deleted Phase-0 apps; drop them + their `django_migrations` rows |
| Browser pane screenshots/clicks time out | pane hidden — reopen with `mcp__Claude_Browser__preview_start`; `read_page`/DOM still work |
| `.next` permission error | clear the directory's *contents* only (it is a volume mount) |
| `import_v1` can't see the data | put it in `V_2.0/import_data/` (git-ignored) — it is mounted read-only at `/import_data` in `backend` and `celery`; after changing `docker-compose.yml` volumes run `docker compose up -d` (recreate), after changing requirements `docker compose up -d --build backend celery` |
| `tsc`: "Cannot find module 'vitest'" (every `*.test.ts`) | the frontend container's `node_modules` volume predates vitest — `docker compose exec -T frontend npm install` (this also brought `package-lock.json` in line with `package.json`) |
| Moving/deleting files under `backend/media` kills requests for a few seconds | runserver's autoreloader watches `/app`; wait for it to come back |
| Browser-pane clicks land in the wrong place after `resize_window` to a custom size | the click frame is the pane's, not the emulated viewport's — `resize_window preset=desktop` first |

## Tests
```bash
docker compose exec -T backend python manage.py test --noinput        # all: 392
docker compose exec -T backend python manage.py test apps.documents   # one app
docker compose exec -T frontend npx vitest run                        # 68
docker compose exec -T frontend npx tsc --noEmit
docker compose exec -T frontend npm run lint
docker compose exec -T frontend npm run build
docker compose exec -T backend python manage.py check
docker compose exec -T backend python manage.py makemigrations --check --dry-run
```
Backend tests: accounts 21, `documents/tests.py` 58, `test_designer.py` 67, `test_workflow.py` 50, `test_history.py` 18, `dashboard` 9, `pdfgen` 85 (golden 4, renderer 14, adapter 19, API/task 26, bulk 22),
`importer` 84 (mapping 27, import/task/command 40, sources & files 17) — **392** total, incl. real-thread concurrency tests that are skipped on SQLite — run on Postgres).
Tests use a LocMem cache so they need no Redis. Frontend: designer 22, rich-text 16, pdf 8, workflow 7, verify 5, history 5, bulk-print 5 (**68**).
Golden-PDF oracle and how to regenerate it: [08-pdf-engine.md](08-pdf-engine.md). No backend linter is configured (`manage.py check` + `makemigrations --check` only).

## Configuration (`V_2.0/.env`, template `.env.example`)
Key settings live in `backend/config/settings/base.py`, all env-driven:
`DJANGO_SECRET_KEY`, `DATABASE_URL`/`POSTGRES_*`, `REDIS_URL`, `CELERY_BROKER_URL`,
`CELERY_RESULT_BACKEND`, `FRONTEND_BASE_URL` (used to build QR/verify links), JWT cookie
flags, `DOCUMENT_FILE_MAX_BYTES` (100 MB), `LOGO_MAX_BYTES` (5 MB),
`DATA_UPLOAD_MAX_MEMORY_SIZE` (10 MB), `PDF_FONT_REGULAR` / `PDF_FONT_BOLD` / `PDF_FONT_NAME`,
`CELERY_TASK_TIME_LIMIT` (300 s; also the stale-build threshold) / `CELERY_TASK_SOFT_TIME_LIMIT`.
`LANGUAGE_CODE=fa`, `TIME_ZONE=Asia/Tehran`.
`prod.py` refuses to boot if `SECRET_KEY` starts with `insecure-dev-key` (see gaps: `change-me` passes).

## Dev accounts (dev DB only)
| National code | Who | Can |
|---|---|---|
| `123456` | the user's own (sam) | — |
| `9000000001` | مدیر عامل (کارفرمایی L1) | approve, manage personnel — **cannot author** |
| `9000000002` | معاون/مشاور (ستادی L2) | create + confirm |
The two test accounts share a dev-only password that is deliberately **not written in this repo** (it is public on GitHub). The project owner knows it;
to set your own: `docker compose exec backend python manage.py changepassword 9000000002`. Agents must never type it into forms — ask the user to sign in.
Dev DB currently holds **0 documents**
(Phase 4's verification seeded five, then deleted them — a leftover PR-01-01 would collide with the numbering sequence).
To get PDF-able documents: `apps.pdfgen.tests.helpers.create_case(key, {}, author)` in `manage.py shell` builds the fixture documents
from `tests/cases.py` (finalized ones show چاپ) — **always pass `author`** (an old bug created a stray user 7000000001 in the dev DB; removed).
Real ones go through the workflow (Phase 5). To try it you need three different people: author (`create_document`), a **different** ستادی for تایید
(9000000002 fits), and کارفرمایی for تصویب (9000000001 fits); create an author with `/personnel/register` or `manage.py shell`.
For API-level checks use DRF `APIClient().force_authenticate(user)` in the shell rather than typing passwords.
Phase 5's verification seeded and then removed 4 documents, a test user and `DocumentSequence` rows (a leftover sequence would skip numbers).
Create an author via `/personnel/register` (needs the 9000000001 login) or `manage.py shell`.

## Python / tooling versions
Python 3.12 (image), Django 5.0, DRF 3.15, ReportLab **5.0.1**, Node 20, Next.js 16.3.5
(Turbopack, `proxy.ts`), React 19, Tailwind 4, vitest **3** (v5 conflicts with `@types/node@^20`).
Read `frontend/node_modules/next/dist/docs/` before writing Next code — this is not the Next you know
(`frontend/AGENTS.md`).
