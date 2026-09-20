# Workflow, signatures, status, verify page (Phase 5) — ✅ done

Code: backend `apps/documents/workflow.py` (services), `verify.py` (public endpoint), `files.normalize_signature`,
`DocumentEvent` + `SignOff.signed_by` in `models.py`; frontend `lib/workflow.ts`, `lib/verify.ts`,
`components/{SignatureDialog,ReturnDialog,WorkflowActions,WorkflowTimeline}.tsx`, `app/verify/[code]/page.tsx`,
plus changes to the register and designer pages. V_1.0 had **no** real workflow: one person filled all four panels,
typing any name/post into a dialog; `status` was never written; مرجوع was wired to the ویرایش handler and did nothing.

## Decisions (asked of the user, all confirmed)
| Question | Decision |
|---|---|
| مرجوع | The **confirmer** (while AWAITING_CONFIRMATION) or the **approver** (while AWAITING_APPROVAL) returns to **DRAFT**, **reason required**, **all sign-offs cleared** (the author edits and the whole chain restarts). Every return is audited. |
| Same person | **Each step needs a different person**, enforced server-side (409 `same_person`). Capabilities still apply on top. |
| New revision approved | The previous revision becomes **OBSOLETE automatically**; the approved revision's PDF is **auto-built**, and the superseded revision's PDF is **auto-rebuilt** (if it ever had one) so it prints «منسوخ». |
| Signature | **Drawn on a canvas at every sign-off.** Name, سمت and date come from the session, never typed. |

Defaults I chose (say if you disagree): a `DRAFT` is submittable only once a body has been saved (`content_saved_at`);
the author must hold `create_document` but need not be the row's `created_by` (same as editing); the register's
تدوین/تائید/تصویب columns show **name + Jalali date** (title in a tooltip); the PDF's free «متن آزاد» control-status text
(V_1.0's `extra_header`) is **not built** — it stays empty.

## State machine
```
DRAFT --submit--> AWAITING_CONFIRMATION --confirm--> AWAITING_APPROVAL --approve--> UNDER_CONTROL
  ^                        |                                  |                        (previous rev → OBSOLETE)
  +------- return ---------+----------------------------------+   (reason required, sign-offs cleared)
```
| Step | Needs | Writes |
|---|---|---|
| `submit` | `create_document`; status DRAFT; body saved | SignOff `creater`; event SUBMITTED; body locked |
| `confirm` | `confirm_document`; not the creater signer | SignOff `confirmer`; event CONFIRMED |
| `approve` | `approve_document`; not creater/confirmer | SignOff `approver`; event APPROVED; supersede previous (event SUPERSEDED, actor = approver); queue PDF builds on commit |
| `return` | `confirm_document` in AWAITING_CONFIRMATION, `approve_document` in AWAITING_APPROVAL; not the creater signer; reason 1–1000 chars | deletes sign-offs (files removed on commit); event RETURNED (with reason) |

Each transition is one `@transaction.atomic` under a `select_for_update` row lock, so two simultaneous confirms have exactly one winner
(the loser gets 409 `wrong_status`). Status changes use `save(update_fields=…)`, not `.update()`, so the dashboard cache invalidates.
The approval never fails because of a PDF: builds are queued on commit; a build already running for the old revision is logged and skipped.
Typed 409s: `wrong_status` (carries current `status`), `same_person`, `content_missing`. Bad/blank signature → 400 with a Persian `signature` message.
Roll capabilities (Phase 1) mean: صفی may author; ستادی may author and confirm; کارفرمایی may approve. A ستادی user may therefore author *and*
be a confirmer candidate — the same-person rule is what stops them doing both on one document.

## API (`/api/v1/`)
| Route | Notes |
|---|---|
| `POST /documents/{id}/submit/` · `/confirm/` · `/approve/` | **multipart**, one field `signature` (PNG from the pad). Each has its own `capability_required(...)` permission (`core/permissions.py`). Returns the fresh document row (200) |
| `POST /documents/{id}/return/` | JSON `{reason}`. Capability depends on the state, checked in the service (403 `PermissionDenied` otherwise) |
| `GET /documents/{id}/history/` | the audit trail `[{kind, kind_label, from/to_status(+_label), actor_name, actor_title, reason, created_at}]`, oldest first; never exposes user ids |
| register rows / detail | gain `workflow: {step, can_act, can_return, blocked}` — computed from the prefetched sign-offs, **no extra query** (list is still 4 queries/page). `step` is `submit`/`confirm`/`approve`/`null` (null for a draft with no saved body, and for finished documents). `blocked` is a Persian reason when the user holds the capability but is barred as an earlier signer |
| detail / `content` payload | gain `return_note: {reason, by, by_title, at}` while a DRAFT's latest event is a return (one query; not on list rows) |
| `GET /verify/{code}/` | **public** (see below) |

Signature handling (`files.normalize_signature`): ≤2 MB, ≤4 MP, PNG/JPEG/WEBP only, re-encoded to an **opaque RGB PNG** (transparency flattened onto white —
the PDF renderer draws signatures unmasked), thumbnailed to 1000 px, and **a blank pad is refused** (<30 ink pixels). Stored at `media/signatures/<doc-id>/<uuid>.png`.
`SignOff.signed_by` (new FK, SET_NULL) is what the same-person rule compares; the printed name/post are text snapshots.

## Audit trail (`DocumentEvent`)
`kind` (submitted / confirmed / approved / returned / superseded), `from_status`, `to_status`, `actor` (SET_NULL) + **`actor_name`/`actor_title` snapshots**,
`reason`. Needed because a return deletes the sign-offs; the trail is what still says who had signed. Read-only in the admin (no add/change/delete).

## Public verify (`/verify/{code}` page, `GET /api/v1/verify/{code}/`)
What a printed QR code opens. V_1.0's QR was a *predicted static PDF URL*, so an obsolete revision kept "proving" validity forever.
- No login, **no cookies read** (`authentication_classes = []`: a stale token can't 401 a scanner), `Cache-Control: no-store`, rate-limited **per IP**
  (`VERIFY_RATELIMIT_RATE`, default `60/m`, read per request so tests can override; over the limit → 403).
- Code = `PR-01-01` (case-insensitive, trimmed); malformed/unknown → 404 `{found:false}`.
- `state`: `valid` (UNDER_CONTROL → معتبر) · `obsolete` (→ منسوخ, plus `current_revision` = newest UNDER_CONTROL revision of the family, or null) · `pending`
  (draft/awaiting → «در دست بررسی»; **discloses only code, revision and that it isn't valid — no title, no signers**). valid/obsolete add title, group, and the three signers (name, سمت, date) — what the PDF already prints.
- Never returns ids, `created_by`, national codes, or signature images.
- The frontend page fetches with plain `fetch` (`credentials: "omit"`), `proxy.ts` lets `/verify/*` through unauthenticated.

## Frontend
- **Register row** (`WorkflowActions`): the server decides which buttons exist. `can_act` → the step's button (ارسال برای تایید / تایید / تصویب) opens
  `SignatureDialog`; `can_return` → «مرجوع» opens `ReturnDialog`; `blocked` → the step button **disabled with the reason as its tooltip**.
  After success the list reloads and a Persian notice shows; approving shows that a PDF build started (the row then follows it, Phase 4 behaviour).
- **`SignatureDialog`**: pointer-events canvas (mouse/touch, `touch-action:none`, DPR-scaled, white background), read-only name/سمت/Jalali date from `useCurrentUser`,
  «پاک کردن», submit disabled until there is ink; exports `toBlob("image/png")`; server errors appear inside the dialog.
- **Designer page**: header shows the same workflow buttons (held while there are unsaved edits — the server signs what was last *saved*), a red **return banner**
  (who/when/reason), the **timeline** («سوابق گردش کار»), and the save-bar **«نمایش» is now live** (it was left disabled in Phase 4 — fixed here; previews the last saved version).
- Removed the register's disabled «اتمام» button and the `ACTION_AVAILABLE_IN` table (nothing is "coming later" any more except history/bulk print).

## Verification performed
- 50 workflow/verify backend tests (real Postgres, real threads). **Mutation-checked: 11 mutations each fail ≥1 test** — dropping the same-person check, the row lock,
  the `save()` (dashboard cache), the sign-off clearing, the reason requirement, the supersede, the PDF queueing, the saved-body requirement, taking the signer name from the request,
  the verify page's pending-document redaction, and the return's capability check. Two race tests: simultaneous confirms → one winner; confirm-vs-return → one of exactly two coherent end states.
- Live stack with the **real Celery worker** (users via force-authenticated API clients; no passwords typed): approve → PDF built automatically (`requested_by` = approver);
  revision 2 through submit/confirm/approve → revision 1 became OBSOLETE and its PDF was rebuilt — I looked at both PDFs: **معتبر** with three signatures before, **منسوخ** after.
- **Browser** (signed in as a ستادی user): submitted a draft by drawing a signature (register + notice + name/date in the تدوین column); saw the same person's «تایید» disabled with the
  reason; returned a document (empty reason refused, then with a reason) → back to DRAFT, sign-offs gone; the designer showed the return banner + timeline and its «نمایش» worked;
  confirmed a document with a drawn signature; the public `/verify/…` page rendered valid, obsolete (with pointer to the current revision), pending and not-found, and loads with no session.
- Frontend: 12 new unit tests (`workflow`, `verify`); tsc, lint, `next build` clean.

## Not verified / caveats
- **Not clicked:** the *approver's* browser session (approval was exercised through the API with a force-authenticated approver; its capability gate is backend-tested); the signature pad on a real touch device (pointer events are used, but I only drove it with a mouse); the pad's «پاک کردن» button; rate-limit behaviour behind a proxy (`key="ip"` uses `REMOTE_ADDR`; behind a reverse proxy configure the real client IP or every scanner shares one bucket).
- A build of the *old* revision already running at approval time is skipped (logged), so that one PDF can finish printing «معتبر»; the register shows it and «بازسازی» fixes it.
- Visible V_1.0 PDF quirks that sign-offs now surface (all preserved on purpose): **two-word names/posts wrap with the lines in reverse order** in the narrow cells (the archived PDFs do the same to «تایید کننده»); a document **without a logo prints V_1.0's black placeholder square**.
- No inbox/کارتابل screen (V_1.0's button was dead): a reviewer finds work by filtering the register on «در انتظار تایید/تصویب». Withdrawing a submitted document is not a feature (only a reviewer can return it).
