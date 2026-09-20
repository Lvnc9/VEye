# PDF engine (Phase 4) — ✅ done

Code: `backend/apps/pdfgen/`. Frontend: `lib/pdf.ts`, `components/PdfActions.tsx`, the register page
(`app/(app)/documents/page.tsx`). The renderer is **the user's algorithm**, ported from
`V_1.0/other_folder/to_make_pdf.py` (+ the `Provider` in `deliver_convert.py`). Read the *Quirks* section before
"fixing" anything that looks wrong in a PDF.

## Decisions (asked of the user, all confirmed)
| Question | Decision |
|---|---|
| Build trigger | Explicit **«ساخت PDF»** action → Celery task. States: ساخته نشده / در حال ساخت / آماده / ناموفق. Phase 5's finalize step can call the same service. |
| Storage | One current file per revision, **replaced on rebuild**: `media/pdfs/<doc-id>/<full_code>.pdf`, written atomically (temp file + `os.replace`). |
| نمایش | **Watermarked «پیش‌نمایش» on demand**, any revision incl. drafts, via the same task → `media/pdf_previews/<doc-id>.pdf` (replaced each time). Never the issued copy. |
| Long-block `extra_boxes` | **Printed** as paragraphs after the body (V_1.0 silently dropped them). Attached files are *not* printed (downloads are authenticated). |
| Empty signature cells | **Blank** (name, سمت, امضا empty), as V_1.0 does for an unsigned role. |

## Layout of `apps/pdfgen/`
| File | Role |
|---|---|
| `renderer.py` | `HeaderFooterCanvas` + `PDFMaker` — **near-verbatim** V_1.0 (see *Surgery*) |
| `provider.py` | V_1.0's `Provider.deliver_to_pdf` as a pure function `deliver_to_pdf(PdfInput, preview, invariant) -> bytes`. `PdfInput` is a frozen dataclass; blocks are tagged tuples (`text` / `responsibilities` / `table` / `attachments`) instead of V_1.0's `type(el) is list/dict` |
| `adapter.py` | `load(document_id) -> PdfInput` — Postgres → the data V_1.0's JSON carried. Reads images from media, degrades to placeholders |
| `qr.py` | `verify_url(document)` = `{FRONTEND_BASE_URL}/verify/{full_code}`; `qr_png(data)` (V_1.0 `generate_qr` params, in memory) |
| `fonts.py`, `apps.py` | fonts registered **once** in `AppConfig.ready()` (`settings.PDF_FONT_*`); names `"Vazir"`/`"Vazir-Bold"` |
| `models.py` | `PdfBuild` — one row per (document, kind); status, token, path, size, sha256, built_at, error |
| `services.py` | `request_build()` — locked, transactional, queues the task `on_commit` |
| `tasks.py` | `@shared_task pdfgen.build_pdf(build_id, token)` |
| `storage.py` | paths under `MEDIA_ROOT` (never user-controlled), `write_atomic` |
| `views.py`, `urls.py` | the API below |
| `tests/` | 63 tests + `cases.py`, `helpers.py`, `fixtures/` (logo, 3 signatures, **golden PDFs**), `tools/make_golden_from_v1.py` |

## API (`/api/v1/`, authenticated)
| Route | Notes |
|---|---|
| `GET /documents/{id}/pdf/{kind}/` | state: `{kind, status, status_label, requested_at, built_at, size, error, stale, download_url}`. `kind` = `official` \| `preview`; `status` = `none`/`building`/`ready`/`failed`. `download_url` follows the *file*, so it is present during a rebuild and after a failed one |
| `POST /documents/{id}/pdf/{kind}/` | queue a build → **202** with the state. Needs `Capability.PRINT_DOCUMENT` |
| `GET /documents/{id}/pdf/{kind}/download/` | the file, `inline` (`?download=1` → attachment), filename `<title>-<code>.pdf`, `Cache-Control: private, no-cache`. Authenticated — never a public media URL |
| `GET /documents/` rows | gain `pdf_status` (official) and `pdf_built_at` via subquery annotations — **no PDF is opened; still 4 queries/page** |

Typed 409s (`ConflictError`): `not_finalized` (official PDF of a non-finalized revision — use نمایش),
`build_in_progress` (a build is genuinely running; carries `build_id`). A `BUILDING` row older than
`CELERY_TASK_TIME_LIMIT + 60 s` is `stale` and may be rebuilt. Unknown `kind`/document → 404.

**Permission:** new capability `print_document` ("ساخت و نمایش PDF مستند"), granted to **every roll** (so today it
restricts nothing, but it is the switch to flip if that changes). Reads/downloads need authentication only.
Adding it meant updating the four capability assertions in `accounts/tests.py`.

## Build lifecycle
`POST` → `request_build` (row lock `select_for_update`; unique `(document, kind)`; new token) → `on_commit` → `build_pdf.delay`.
The task acts only on a row still `BUILDING` **with its own token** (a redelivered or superseded task is a no-op),
renders in memory, writes atomically, then records the result with a compare-and-set on the token.
`OperationalError`/`OSError` retry twice; anything else → `FAILED` with a Persian message (cause goes to the log, never
to the user). If the broker is unreachable the row is failed immediately. A failed *re*build keeps the previous file
downloadable. Nothing in the task touches module state; several run at once in the prefork pool (concurrency = CPUs).

## Surgery on `renderer.py` (everything else is verbatim)
- images (logo/QR/signatures) are PNG **bytes**, decoded once by `_image()`; a `None` draws V_1.0's black placeholder box.
  The `.png`-only-logo rule (V_1.0: `".png" in path`) now lives in the adapter.
- `PDFMaker` writes to `BytesIO`; `generate_pdf()` returns bytes; `invariant=` (tests only) makes output reproducible.
- `_register_fonts` removed (→ `AppConfig.ready()`); `image_checker`, `_draw_attachment_item` (dead), the demo `__main__`, and all `print()`s removed.
- **Crash fixes (only these):** unguarded bold `setFont` in the small header; `whole_code.split('-')[2]` moved inside its guard;
  mutable `creater=[]` defaults; `image_checker` writing a `Response` (moot — no network).
- `from bidi.algorithm import get_display`, `python-bidi==0.6.11`, `reportlab==5.0.1` (all pinned; a test asserts the bidi module/version).

## Quirks preserved on purpose (the golden files pin them)
Page 1 has no watermark; the last page's watermark/footnote is drawn twice; furniture is drawn *under* body content on pages ≥2;
`add_body_text` wraps on **character count** (≤170 chars: not wrapped at all; >170: cut into 70-char chunks, mid-word);
control-table body starts on page 2; the responsibilities notes print «توضیحات:» twice; a Changes-Table header cell overflows;
`text_merge` (below). Transparent signatures were the one thing changed *outside* the renderer — see next section.

### ⚠ Things a user will notice — decide whether to fix (not fixed: "preserve quirks")
1. **Long lines run off the page.** A body line of ~90–170 characters is drawn as one line and is **clipped at the left edge**
   (visible in the `full` golden, page 2/3). Wrapping is by character count, not width.
2. **`text_merge` loses and duplicates text.** Used for responsibilities descriptions (limit 100) and `extra_header`:
   `text_merge("aaa bbb ccc ddd", 12)` → `[' aaa bbb ccc']` — **the last word is dropped when it is the one that forces a wrap**;
   and `i is group[-1]` is an *identity* test, so repeated short words duplicate a chunk (`"x y x y"` → `[' x y', ' x y x y']`).
   Real user text can vanish from an issued PDF. A small fix (compare by index instead of `is`, and flush the final chunk) would cure both.
3. Mid-word cuts for lines >170 chars (see above).
Adapter-side differences from a stock V_1.0 run (not renderer changes): no stray leading space on the first Short block
(V_1.0's module-level `SHORT = " "`); change-table rows are numbered continuously across revisions; **transparent signature PNGs are
flattened onto white** (the renderer draws signatures without `mask="auto"`, so V_1.0 would print a black box; its archived signatures
were opaque). **Phase 5 should still normalize signatures on upload.**

## Data mapping (`adapter.load`)
- header: `title`, `full_code`, `revision_display`, date = **Jalali** (`YYYY/MM/DD`) of the local (Asia/Tehran) date of `content_saved_at` (today if never saved);
  footnote1/2 → upper/lower; QR = `verify_url(document)` — **the `/verify/` page is Phase 5, so scanned codes 404 until then**.
- validity cell: `UNDER_CONTROL`→معتبر, `OBSOLETE`→منسوخ, anything else → **empty** (a document not yet under control claims no validity).
  ⇒ an issued PDF goes stale when its revision is superseded: **Phase 5 must call `request_build` when a revision becomes OBSOLETE.**
- blocks in `position` order: Short (non-empty lines, each + `\n`); Long = `heading\nbody` (+ `\n\n`-joined non-empty `extra_boxes`);
  Responsibilities = «الف:  سمت: … ناظر: …» rows + «توضیحات: » notes; Changes Table = all earlier revisions' frozen rows
  (`previous_change_rows()`, oldest first) then this revision's, numbered 1..n continuously; Attachment = caption, `target.full_code`, the target's QR.
  An **empty Attachment block still prints the «ضمائم:» heading** (V_1.0 does; `عنوان-PO-01-01.pdf` shows it).
- `\r\n` normalised to `\n` at the boundary. Sign-offs → three control-table rows; missing/corrupt image → blank/placeholder + a log warning.

## Verification performed
- **Oracle:** `tests/fixtures/golden/*.pdf` are produced by **V_1.0's own `Provider` + `to_make_pdf.py`, unmodified** (`tools/make_golden_from_v1.py`, JSON in →
  ReportLab `invariant`), for 4 cases (sample with 3 signatures; bare/empty-attachment/placeholders; every block type over 4 pages incl.
  a 2-revision history, markers, Latin/digits, overflow, OBSOLETE; a watermarked draft preview). `test_golden.py` loads each case into Postgres, renders through
  the adapter + port, and asserts **byte equality**. Mutation-checked: 170→160 wrap, dropping the double footnote, 70→71 chunk, and swapping in the Rust `bidi` each fail it.
  Two normalisations are applied to the oracle only (leading-space global; signature XObject naming) — documented in the tool.
- Visual: rendered pages compared against `نمونه-PR-01-01.pdf` (layout matches; both embed `Vazir` + `Vazir-Bold` as TrueType subsets, 2 pages) and the multi-page/preview goldens looked at by hand.
- **Concurrency:** (a) 8 threads × 3 rounds of different inputs == sequential bytes (mutation: a class-level shared logo fails it); (b) 5 simultaneous real Celery builds
  (official ×3 docs + preview ×2, separate prefork workers) — all 12 pages **pixel-identical** to sequential renders, each PDF contains only its own code;
  (c) two simultaneous POSTs → exactly one build starts (real threads; without `select_for_update` the *rebuild* variant fails 4/4).
- **Fresh empty media:** unit test with an empty `MEDIA_ROOT`, and live: media contents moved aside, builds succeeded, `pdfs/` created on demand, placeholders + warnings, no crash.
- Browser (live stack): register shows «ساخت PDF» → «در حال ساخت…» → «چاپ» (+ «بازسازی»), «نمایش» on every saved row incl. the draft; چاپ/نمایش hit
  `…/download/` with 200 (56–61 KB). **Not verified by eye:** the pane did not surface the popup tab, so I did not see the PDF render *inside the browser tab* (PDFs were rasterised with `pdftoppm` instead).

## Regenerating the golden files
Only needed if `cases.py` changes or ReportLab is bumped (the files are byte-exact for `reportlab==5.0.1`):
```bash
cd V_2.0
docker compose cp <V_1.0>/other_folder backend:/tmp/v1/other_folder
docker compose cp <V_1.0>/Vazir.ttf backend:/tmp/v1/Vazir.ttf && docker compose cp <V_1.0>/Vazir-Bold.ttf backend:/tmp/v1/Vazir-Bold.ttf
docker compose exec -T backend python -m apps.pdfgen.tests.tools.make_golden_from_v1 --v1 /tmp/v1
docker compose exec -T backend python manage.py test apps.pdfgen --noinput
```
V_1.0's tree here is `V_1.0/VEye-GUI-customtkinter/` (the docs elsewhere abbreviate it to `V_1.0/`).

## Phase 5 wiring (done — see [09-workflow.md](09-workflow.md))
- `workflow.approve` calls `services.request_build(kind=OFFICIAL)` on commit for the approved revision and for the superseded one **if it ever had an official build**, so it reprints «منسوخ».
- `/verify/{code}` is live (public). Signatures are normalised to opaque PNG on upload (`files.normalize_signature`); the adapter's flatten stays as a guard.
- Signature names now show up in the control table and expose two more preserved quirks: two-word names/posts **wrap with the lines in reverse order** in the narrow cells
  (the archived `تایید کننده` does it too), and a document **with no logo prints the black placeholder square**.

## For Phase 6
- Phase 6 «چاپ لیست» is built (`pdfgen/bulk.py`): it only zips `pdfs/<id>/<code>.pdf` files that exist and never renders — see [10-phase-6.md](10-phase-6.md).
- Nothing prunes `media/pdf_previews/` (one file per document, replaced in place, so it is bounded).
