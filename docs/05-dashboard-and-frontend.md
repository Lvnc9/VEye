# Dashboard & frontend conventions

## Dashboard (backend `apps/dashboard/`, frontend `app/(app)/dashboard`)
- `GET /dashboard/metrics/` — real group × status counts. All four groups always present (zero-filled);
  **every revision counts**; cached 60 s in Redis; `signals.py` invalidates on Document/User save/delete.
  (V_1.0's dashboard was hard-coded mock data, incl. `کاربر: مدیر عامل`.)
- `GET /dashboard/system-info/` — small info payload.
- `GET /dashboard/awaiting/` — Phase 6: documents awaiting the signed-in user's step (same verdict as the register's buttons); the dashboard also shows the last 10 events from `/history/activity/`. See [10-phase-6.md](10-phase-6.md).
- Phase 6 may add more widgets; keep them query-based.

## Frontend stack
Next.js 16.3.5 (App Router, Turbopack, **`proxy.ts` not `middleware.ts`**), React 19, Tailwind 4, vitest 3.
`lang="fa" dir="rtl"`, Vazir via `next/font/local`. **Read `node_modules/next/dist/docs/` before writing Next code.**

## Layout
`app/(app)/layout.tsx`: window-height shell, dark sidebar, `CurrentUserProvider`. Nav items carry an optional
`capability` (hidden if the user lacks it) and `ready:false` (rendered disabled «به‌زودی»). To add a screen, flip
`ready` and add the route; the history entry `/documents/history` is `ready:false` until Phase 6.

## lib/
| File | Role |
|---|---|
| `api-client.ts` | `apiGet/Post/Put/Patch/Delete`, `apiUploadWithProgress`; cookies + CSRF header; refresh-on-401 (excludes session endpoints); flattens DRF field errors into one Persian message |
| `types.ts` | shared API types incl. `Capability` |
| `current-user.tsx` | `CurrentUserProvider`, `useCurrentUser()` → `{user, can(cap)}` |
| `jalali.ts` | Jalali formatting via `Intl fa-IR-u-ca-persian`; local-date parsing |
| `rich-text.ts` | marker parse/serialise for B/I/U (+ tests) |
| `designer.ts` | designer state ⇄ API mapping (+ tests) |
| `workflow.ts` | Phase 5: `workflowControls(row.workflow)` (buttons from the server's verdict), `signStep` (multipart, **only the image is sent** — identity comes from the session), `returnDocument`, `validateReason`, Persian step labels/prompts (+ tests) |
| `verify.ts` | Phase 5: `fetchVerification(code)` for the public page — plain `fetch`, `credentials:"omit"`, `cache:"no-store"`, discriminated result (ok / not_found / error; 403/429 are *not* "not found") (+ tests) |
| `pdf.ts` | Phase 4: `buildPdf` (POST → poll `waitForPdf`, joins a build already running on a 409 `build_in_progress`), `followPdf`, `officialPdfAction` (status → button), `openPdfInTab` (opens the tab **synchronously in the click** — popups after an `await` are blocked — then points it at the file; the state read also refreshes an expired session). Relative imports only: vitest has no `@/` alias (+ tests) |

## Components
`Code` (renders a full code LTR inside RTL), `StatusBadge`, `StatusBanner`, `PdfActions` (the register row's چاپ/بازسازی/نمایش buttons), `WorkflowActions` + `SignatureDialog` (canvas signature pad) + `ReturnDialog` + `WorkflowTimeline` (Phase 5), `designer/*` (block editors, toolbar, picker modal).
The register page keeps a per-row `pdfStatus` override (a build started here is newer than the list) and follows rows that *load* as `building`; polling lives in async handlers, not effects (`set-state-in-effect` is a lint error).

## Conventions
- Persian for every user-visible string; dates render Jalali via `lib/jalali.ts`.
- Errors: surface the API `detail`/field message; never show raw English status text.
- Deliberate hard redirects use `window.location.href` with an eslint-disable comment explaining why.
- Verify UI in the browser pane (`preview_start`), not only via tests; check RTL and that the sticky/scroll layout still works.
