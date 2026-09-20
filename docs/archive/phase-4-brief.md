> **Historical.** Written before the docs moved into the repo: `.claude/docs/…` is now `docs/…` and `.claude/skeleton.md` is `docs/skeleton.md`.

# Phase 4 brief — PDF engine

> **✅ DONE (2026-09-20).** What was built, the user's decisions and the verification are in [08-pdf-engine.md](08-pdf-engine.md). This brief is kept as the original spec.

**Goal:** click ساخت/build on a finished-authoring document → a Celery task renders the Persian RTL PDF with the
user's algorithm → it is stored locally and downloadable. The register list never renders PDFs.
**Runnable outcome:** build a document, download the PDF, compare it against an archived V_1.0 PDF.

## Spec = the user's file
`V_1.0/other_folder/to_make_pdf.py` (renderer, no GUI imports) + `deliver_convert.py` (`Provider`, the data adapter).
**Port the algorithm as written.** Only fix crash-level bugs. Quirks are preserved on purpose.

### Renderer structure
- ReportLab **5.0.1** low-level `pdfgen.canvas` (no Platypus). `HeaderFooterCanvas(canvas.Canvas)` (`:20-263`) overrides
  `showPage()`/`save()` to inject furniture: footnote each page, small header from page 2, optional «پیش نمایش» watermark.
- `PDFMaker` (`:274+`) imperative call sequence: `draw_header` → `draw_control_table` → per-section
  `add_body_text` / `add_table` / `attachments` / `responsibilities` → `generate_pdf()`.
- Lift verbatim: `HeaderFooterCanvas`, `prepare_rtl`, `add_body_text`, `add_table`, `attachments`, `responsibilities`,
  `draw_control_table`, `draw_header`, `draw_wrapped_centred_text`, `draw_header_cell`, `draw_data_cell`, `text_merge`.
- Surgery: `PDFMaker.__init__` takes absolute font/logo/QR paths and accepts `BytesIO` (Canvas takes file-likes);
  register fonts once (`AppConfig.ready()`), names must stay `"Vazir"` / `"Vazir-Bold"` (string-concatenated in 9 places);
  `generate_pdf` returns bytes.
- Rewrite: `image_checker` (`:1112-1140`) → read from Django storage; `Provider` → instance-scoped, sourcing from Postgres;
  drop the viewer launch (`deliver_convert.py:260-278`, `os.startfile`/`xdg-open`/`sys.exit`).

### Hard constraints
1. **`python-bidi==0.6.11` and `from bidi.algorithm import get_display`** (legacy pure-Python). 0.7.x removes `bidi.algorithm`; the Rust
   `bidi.get_display` differs on edge cases → PDFs would silently differ. Already pinned in `requirements/base.txt`. Also
   `arabic-reshaper==3.0.1`, `qrcode[pil]==8.2`, `jdatetime==6.1.0`.
2. **Fonts:** the repo-root Vazir pair, vendored at `backend/assets/fonts/`; use `settings.PDF_FONT_REGULAR/BOLD/NAME`.
3. **Python ≥ 3.12** (nested f-strings in `image_checker`).
4. **No module-global state.** `deliver_convert.py:14` `all_documents` is mutated and read by a `@staticmethod`; two concurrent
   Celery tasks would corrupt each other. Pass it as a parameter/instance field.
5. Persian shaping/RTL must match V_1.0 — verify visually against archived PDFs.

### Crash bugs to fix while porting
`image_checker` writes `Response` instead of `.content` for approver/confirmer; `whole_code.split('-')[2]` before its guard
(`:416`); mutable defaults `creater=[]` then indexed `[0]` (`:942`); unguarded bold `setFont` (`:241`); unvalidated `json.load` of an HTTP body
(`deliver_convert.py:186`); `requests.get` with no timeout (moot once reading local storage).

### Quirks to PRESERVE (user asked for fidelity)
Page 1 has no watermark; the last page's watermark and footnote are drawn **twice** (`save()` re-enters the overridden `showPage`);
furniture draws *under* body content on pages ≥2; `add_body_text` wraps on **character count**, not `stringWidth`; only `.png` logos are drawn.

## Data available from V_2.0 (no HTTP, no JSON files)
- `Document`: `group`/`prefix`, `number`, `revision_display`, `full_code`, `title`, `logo` (already PNG), footnotes,
  date = local date of `content_saved_at`, `status`, `created_by`.
- Sections in `position` order: Short (`lines`), Long (`heading`, `body`, `extra_boxes`, files), Responsibilities
  (`ResponsibilityRow`: role, post, supervisor, text + notes), Changes Table (`ChangeTableRow` text/date), Attachment (`caption`, `target`).
- Change history: current rows + **`Document.previous_change_rows()`** (frozen rows across all earlier revisions; numbering continues).
  Edition printed = owning doc's `revision_display`.
- Attachment items: print caption + `target.full_code` + the target's QR.
- `SignOff` rows (name/position/signature/date) exist but are empty until Phase 5 — render the control table cleanly with blanks.
- Rich text markers `**` `~~` `--` are stored verbatim — parse them in the renderer as V_1.0 does; nesting is not allowed by the designer.
- **QR content** = `{FRONTEND_BASE_URL}/verify/{code}-{revision}` (e.g. `/verify/PR-01-01`); the page itself is Phase 5, so the QR
  will 404 until then — acceptable, note it.
- Validity mark (معتبر / منسوخ) comes from `status`.

## Suggested shape
```
backend/apps/pdfgen/
  apps.py          register fonts in ready()
  renderer.py      ported HeaderFooterCanvas + PDFMaker (near-verbatim)
  adapter.py       Document -> the dict/objects the renderer expects (instance-scoped, DB-sourced)
  qr.py            generate_qr (from utils.py:193) -> /verify/ URL
  tasks.py         @shared_task build_pdf(document_id) — idempotent, retries, writes to media/pdfs/
  tests/           renderer, adapter, task, concurrency, fresh-media
```
Plus: a place on `Document` for the built file (+ built-at/failed state), an API to trigger a build and to download, and
enabling the disabled چاپ / نمایش row actions in `frontend/app/(app)/documents/page.tsx`.

## Verification gate (do all)
1. Regenerate a document equivalent to an archived PDF (`V_1.0/نمونه-PR-01-01.pdf`, `روش اجرايي کنترل مستندات-PO-01-01.pdf`) from
   `saves/*.json` content loaded into Postgres; compare page count, embedded fonts (`Vazir`/`Vazir-Bold` as `/FontFile2`), control-table text,
   and a visual diff of page 1 (render pages to PNG and look at them yourself).
2. **Concurrency:** two builds simultaneously through Celery → no cross-contamination.
3. **Fresh container:** empty `media/` so the old cache-miss crash path is exercised.
4. Persian shaping/bidi correct (mixed digits/Latin codes inside RTL text).
5. `docker compose restart celery` after task changes (no hot reload). Tests + lint + build green. Browser check of the buttons.
6. **Update** `.claude/docs/` (README status table, this brief → "done", add `08-pdf-engine.md`) and `../skeleton.md` §7.
