# Known gaps, unverified items, pending decisions

## Fixed most recently
- `DELETE /personnel/{id}/` on someone who authored a document was an unhandled **500** (`ProtectedError`).
  Now **409 `user_has_documents`** with a Persian message; deactivate via `PATCH {is_active:false}`. 3 tests added (accounts: 21 total).

## Open issues
| # | Issue | Suggested handling |
|---|---|---|
| 1 | `prod.py` only rejects `SECRET_KEY` starting `insecure-dev-key`; the `.env` value `change-me` (9 bytes) passes it and triggers PyJWT's HS256 key-length warning | also reject short keys (<32 bytes) in prod; put a real key in `.env` |
| 2 | Stray `backend/p1.db` (SQLite file, likely left from an early test run) | confirm unused, then delete |
| 3 | Leftover files in the container media volume from deleted Phase-0 apps: `poster_attachments/test.png`, `qr/*.png` | harmless; delete when convenient |
| 4 | The **user still needs to rotate** V_1.0's committed Mongo/S3/login secrets | remind them; never copy the values |
| 5 | No Celery beat/periodic tasks defined yet (worker only); `celery` service has no hot reload | add beat only if a phase needs it |
| 6 | **PDF: long lines run off the page.** V_1.0's `add_body_text` wraps on character count: a line of ~90–170 chars is drawn unwrapped and is clipped at the left edge; >170 is cut mid-word every 70 chars | preserved on purpose (user: "preserve quirks"). Fix = wrap on `stringWidth` — the user's call |
| 7 | **PDF: `text_merge` drops the last word that forces a wrap, and duplicates a chunk when a short word repeats** (`is` identity test). Affects responsibilities descriptions | preserved; a small fix cures both — the user's call (details in 08) |
| 8 | ~~Issued PDFs go stale when superseded~~ | **Fixed in Phase 5**: approval rebuilds the superseded PDF. Residual: a build already *running* for the old revision at that moment is skipped (logged) — «بازسازی» fixes it |
| 9 | ~~QR codes 404~~ | **Fixed in Phase 5**: `/verify/{code}` is live |
| 11 | PDF: two-word names/posts wrap with lines in reverse order in the narrow control-table cells; a document without a logo prints a black square | V_1.0 behaviour, preserved (the archived PDFs do it too) — the user's call |
| 12 | The PDF's free «متن آزاد» under «وضعیت کنترل:» (V_1.0 `extra_header`) has no UI | not built (all V_1.0 samples have it empty); add a field on approval if wanted |
| 13 | The verify endpoint's rate limit keys on `REMOTE_ADDR` | behind a reverse proxy, configure the real client IP or all scanners share one bucket |
| 14 | No inbox/کارتابل and no way for an author to withdraw a submitted document | by design for now: reviewers filter the register on «در انتظار …»; only a reviewer can return |
| 10 | `package-lock.json` was out of sync with `package.json` (vitest missing from the container's `node_modules`); `npm install` in the container fixed it and changed the lockfile | review the lockfile diff when committing |

## Unverified by hand (covered by unit/backend tests or by reasoning only)
- **Phase 5:** the approver's *browser* session (approval was driven through the API), the pad on a touch device, the «پاک کردن» button; see [09](09-workflow.md).
- **Phase 4:** the PDF rendering *inside a browser tab* — the browser pane did not surface the popup opened by چاپ/نمایش, so I confirmed the
  requests (POST 202 → polled → `…/download/` 200, 56–61 KB) and rendered the same files with `pdftoppm`, but did not watch the tab. The
  failure banner (`ناموفق`) and the disabled-without-capability state are backend/unit-tested, not clicked. Not verified: real-world documents
  with Responsibilities/Long text against archived V_1.0 PDFs (the archived samples contain only Short blocks — the other blocks are covered
  by the byte-for-byte oracle against V_1.0's own code, not by archived output).
- Enter-key submit on the login form (button click works; likely a browser-automation artefact).
- Ctrl/⌘+B/I/U in the designer (toolbar buttons verified, same code path).
- Upload **cancel** button and progress bar mid-transfer (files used were tiny).
- Picture and video uploads from a browser (backend-tested only).

## Decisions still pending (ask the user; don't assume)
Phase 4 — **all decided** with the user (build trigger, storage, preview, extra boxes, empty signatures); see [08-pdf-engine.md](08-pdf-engine.md).
Phase 5 — **all decided** with the user (مرجوع rules, one person per step, auto-obsolete + auto-build, drawn signature); see [09-workflow.md](09-workflow.md). Still open: whether `print_document` should stop being granted to every roll.
Phase 6: dedup/collision policy for importing documents; whether Long-block `links` (Liara URLs) should be fetched or recorded as unmigrated.

## Things that look like bugs but are deliberate
Crossed group prefixes (پوستر→PO etc.); the `creater` misspelling; page-1 no watermark and final-page watermark/footnote drawn twice
(V_1.0 PDF quirks — preserved in Phase 4); `SignOff` model exists but is unused.
