# VEye V2 — Architecture & Progress

> Rewritten from scratch on 2026-09-19 against the **real** V_1.0 application.
> The previous version of this file described an early mock-data prototype and
> was wrong in almost every particular. The Progress Tracker at the bottom is
> the answer to "how much of this is actually built".
>
> **Agents: start with [`docs/README.md`](docs/README.md)** — a compact, current status report
> (per-area docs, known gaps, the PDF-engine doc). Use this file only for depth.

---

## 1. What VEye is

An **ISO-style controlled-document system**, entirely in Persian. Staff register
a document slot (category / title / group → an auto-generated code like
`PO-01`), compose its body from ordered content blocks, route it through
**تدوین → تایید → تصویب** with hand-drawn signatures, and publish a Persian
RTL PDF stamped with a QR code and a validity mark (معتبر / منسوخ).

**V_1.0** is a CustomTkinter desktop app (~25k lines) storing data in MongoDB
hosted on Liara cloud, with files in Liara S3-compatible object storage.

**V_2.0** is the same system as Django + PostgreSQL + Next.js, **all storage
local** (no Mongo, no S3), with Celery for background work.

### Locked decisions
| Decision | Choice |
|---|---|
| UI language | Persian RTL throughout — `dir="rtl"`, Vazir webfont, Jalali dates |
| Existing data | Migrated into Postgres (Phase 6) |
| PDF rendering | The V_1.0 algorithm is **ported, not rewritten** |
| List performance | ساخت مستند loads from Postgres queries only — never by touching PDFs. PDFs build on explicit ساخت action; چاپ لیست just downloads what exists. |
| Sequencing | Phased vertical slices, each independently runnable |

---

## 2. ⚠ V_1.0 source map — live vs dead

Verified three ways: import graph, `__pycache__` timestamps from the last run,
and `git status`.

**LIVE — 9 files.** `main.py`, plus in `other_folder/`: `Dashboard.py`,
`documents_01.py`, `create_confirm_approval_statusControl.py`, `register.py`,
`poster_01.py`, `utils.py`, `deliver_convert.py`, `to_make_pdf.py`.

**DEAD — never port from these.** `other_folder/{documents,poster,utils_01,test01-04}.py`,
`clearing_the_database.py`, `qr/gen.py`, and critically **`documents_01 (1).py`
at the repo root** — a stale re-download that cannot even import (`from utils
import …` absolute, with no root `utils.py`) and whose group names are
**English**. The live file uses **Persian** group names.

```python
# LIVE — other_folder/documents_01.py:699-706
if   group == "پوستر":       code = "PO-01"
elif group == "روش اجرایی":  code = "PR-01"
elif group == "دستورالعمل":  code = "WI-01"
elif group == "فرم":         code = "FR-01"
```
The Persian labels deliberately do not transliterate to their Latin prefixes
(روش اجرایی→PR, دستورالعمل→WI). Reproduced literally in
`backend/apps/core/constants.py`.

### ⚠ Credentials to rotate
Committed in V_1.0 **and in git history** (single commit `7922293`):
MongoDB URI with password (`other_folder/utils.py:90` — a *default argument*,
so baked into every call site; also `clearing_the_database.py:21`,
`test02.py:4`, `test03.py:9`); Liara S3 access key + secret
(`other_folder/utils.py:26-27`, `:1629-1630`,
`create_confirm_approval_statusControl.py:18-19`, `utils_01.py:1444-1445`);
and the app login dict (`main.py:19-21`). **None are carried into V_2.0** —
config reads `.env` only.

---

## 3. Repository layout

```
VEye/
├── V_1.0/VEye-GUI-customtkinter/   # reference only, untouched
└── V_2.0/
    ├── docker-compose.yml          # postgres · redis · backend · celery · frontend
    ├── .env.example
    ├── backend/
    │   ├── config/                 # settings/{base,dev,prod}, urls, celery, asgi/wsgi
    │   ├── apps/
    │   │   ├── core/               # shared constants, base models, permissions, redis utils
    │   │   ├── accounts/           # national-code User + RBAC + JWT cookie auth
    │   │   ├── dashboard/          # read-only aggregation (no models)
    │   │   ├── documents/          # registry + designer + workflow      [Phase 2-3, 5]
    │   │   └── pdfgen/             # ported ReportLab renderer + Celery build [Phase 4 ✅]
    │   ├── assets/fonts/           # Vazir.ttf, Vazir-Bold.ttf (repo-root pair)
    │   └── requirements/
    └── frontend/                   # Next.js 16 · React 19 · Tailwind 4
        ├── app/                    # App Router, lang="fa" dir="rtl"
        ├── app/fonts/              # Vazir TTFs for next/font/local
        ├── components/
        ├── lib/                    # api-client, types, jalali
        └── proxy.ts                # route guard (Next 16 renamed middleware → proxy)
```

---

## 4. Data model

MongoDB (`my_database.my_collection`, one flat collection) holds a thin
**index row**; the `saves/*.json` file holds the **actual content**. Postgres
normalizes both into one schema.

**Index row** (`other_folder/documents_01.py:714-733`): `category`, `title`,
`group`, `review` (`"one-two"`), `code`, `simple_code`,
`accountant`/`questioner`/`responder` (each `[post, supervisor]`),
`creater`/`confirmer`/`approver`, `valid`, `json_path`, `link`.

**Content JSON** (`other_folder/utils.py:507-525`): `title`, `logo_path`,
`document_number`, `date` (Jalali), `qr_path`, three role triples
`[name, role, signature_url]`, `validation`, `extra_header`,
`footnotes.{footnote1,footnote2}`, `dynamic_items[]`.

### `dynamic_items` — five ordered section types (order *is* page order)
| type | payload |
|---|---|
| `Short Explanation` | flat list of strings (heading + body) |
| `Long Explanation` | `main_entry`, `main_textbox`, `additional_textboxes[]`, `links[]` |
| `Changes Table` | `rows[]` of `{column_number, edition, date, content:{text, type: entry\|label, previous_change}}` |
| `Responsibilities` | `options[8]` = 4 rows × (post 0-3, supervisor 4-7) + `entries[]` |
| `Attachment` | payload in sibling key `all_labels[]` = `[caption, code_review, qr_path]` → a **cross-document reference** |

### Planned Django models (`apps/documents`)
- **`Document`** ✅ *built (Phase 2)* — one row per **revision**: category, title,
  group, `number`, `revision` (a single integer 1-99, not V_1.0's split
  "one-two" pair), status, `previous_revision` (**OneToOne** self-link —
  replaces the `check/` HTTP fetch; its reverse accessor `next_revision` *is*
  "superseded by", so there is no separate column), `content_saved_at`,
  `created_by`. The prefix is derived from the group, not stored. Unique on
  `(group, number, revision)`, and on `(group, title)` for revision 1.
  Phase 3 added logo/footnotes/content version; date derives from `content_saved_at`. **PDF state is not a `Document` field:** it lives in
  `pdfgen.PdfBuild` (Phase 4), and the QR is generated per build, not stored.
- **`DocumentSequence`** ✅ *built (Phase 2)* — per-group counter allocated
  under a row lock; see "Registry numbering" below.
- **`SignOff`** ✅ *model built (Phase 2), written by the workflow (Phase 5); `DocumentEvent` is the audit trail* — role, name,
  position, `signature` ImageField, signed_date. Exists now because the
  register's تدوین/تائید/تصویب columns read from it.
  *(Mongo collapsed these to `[name, date]` and lost role+signature; the JSON
  kept all three — the JSON is the source of truth.)*
- **`Section`** ✅ *built (Phase 3)* — `position` + `type` + a `content` JSON for
  the two text-only block types (Short: `{lines}`, Long: `{heading, body,
  extra_boxes}`), plus a M2M to `DocumentFile` (Long only). The other three types
  are relational because they are read or joined elsewhere. The text stays
  **verbatim**, including V_1.0's inline markers `**bold**` `~~italic~~`
  `--underline--`, which the PDF renderer parses (`to_make_pdf.py:458-541`).
- **`ResponsibilityRow`** ✅ *built (Phase 3)* — four rows with a `role`
  (پاسخگو / پاسخ‌خواه / حسابکش / ناظر) carrying post + supervisor + text, plus any
  number of role-less description notes (printed under «توضیحات»). The register's
  حسابکش / پاسخ خواه / پاسخگو columns are **derived** from these, not stored twice.
- **`ChangeTableRow`** ✅ *built (Phase 3)* — text + a server-assigned `date`. The
  edition number is **not stored**: it is the revision of the document the row was
  written in.
- **`AttachmentReference`** ✅ *built (Phase 3)* — caption + a real FK to the
  target `Document` (`PROTECT`).
- **`DocumentFile`** ✅ *built (Phase 3)* — per-document, deduplicated by SHA-256,
  random on-disk name, original name kept in the database.

### Deliberate corrections
- **`status` is dead** in V_1.0 (created as `""`, never written). The real
  five-state model comes from the Dashboard's column headers
  (`Dashboard.py:344-350`) and lives in `apps/core/constants.DocumentStatus`.
- **`"vali"`** is a typo for valid (`create_confirm…py:1779`) — not carried over.
- **`"creater"`** misspelling **is** carried over (DB field, JSON key, and
  signature filenames like `PO-01-01creater.png` all depend on it).
- **`"00"` revision sentinel** → an explicit draft state instead. ✅ *(Phase 2)*
- **Revision wraps silently at 99** → real integers, capped at 99. ✅ *(Phase 2)*
- **New revisions don't supersede old ones** → `next_revision` link exists ✅; the
  auto-obsolete rule (old revision → منسوخ when the new one is approved) ✅ *(Phase 5)*.
- **Code sequence is racy** (max-of-last-row) → transactional counter + unique constraint. ✅ *(Phase 2)*
- **Blind update bug**: `update_document("json_path", "", …)` patches whichever
  row has an empty path first (`utils.py:691`) → key on PK. ✅ *(Phase 3: every save is
  keyed on the document's primary key)*

**Local storage replaces S3.** Five upload paths become `FileField`/`ImageField`:
logo, signature ×3, PDF, attachments. The `saves/*.json` blob is not stored —
it is normalized into tables.

---

## 5. PDF pipeline

`other_folder/to_make_pdf.py` has **zero GUI imports**, so the ~1090-line
renderer core transplants essentially unchanged; only ~130 lines of
filesystem/network glue are rewritten.

**Stack:** ReportLab **5.0.1**, low-level `pdfgen.canvas` only (no Platypus) —
absolute-coordinate drawing. `arabic-reshaper` 3.0.1 + `python-bidi` 0.6.11.
Requires **Python ≥ 3.12** (PEP 701 nested f-strings).

**Architecture:** `HeaderFooterCanvas(canvas.Canvas)` overrides
`showPage()`/`save()` to inject furniture — footnote every page, small header
from page 2, optional پیش نمایش watermark. `PDFMaker` draws the body via an
**imperative call sequence**: `draw_header` → `draw_control_table` →
per-section `add_body_text`/`add_table`/`attachments`/`responsibilities` →
`generate_pdf()`.

| Lift verbatim | Lift with surgery | Rewrite / delete |
|---|---|---|
| `HeaderFooterCanvas` (`:20-263`); `prepare_rtl`, `add_body_text`, `add_table`, `attachments`, `responsibilities`, `draw_control_table`, `draw_header`, `draw_wrapped_centred_text`, `draw_header_cell`, `draw_data_cell`, `text_merge` | `PDFMaker.__init__` — absolute font/logo/QR paths, accept `BytesIO` | `image_checker` (`:1112-1140`) → read from Django storage |
| `generate_qr` from `utils.py:193` (**not** `qr/gen.py` — side effect on import) | `_register_fonts` → `AppConfig.ready()`; keep names `"Vazir"`/`"Vazir-Bold"` | `Provider`'s module-global `all_documents` → instance-scoped |
| The repo-root Vazir TTFs | `generate_pdf` → return bytes | `deliver_convert.py:260-278` viewer launch + `sys.exit(1)` |

### Must fix while porting
1. **🐛 `image_checker` (`:1124-1134`)** — the `creater` branch writes
   `requests.get(...).content`, but **`approver` and `confirmer` write the
   `Response` object** → `TypeError` on any cache miss. Survived only because
   the dev machine's `./img/` was warm; would fire on first run in a fresh
   container. Moot once reading from local storage.
2. **Concurrency** — `deliver_convert.py` mutates a module global read by a
   `@staticmethod`. Two concurrent Celery tasks in one worker would corrupt
   each other's document.
3. **Blocking network I/O in the render path** — `requests.get` with no
   timeout/status check. Replaced by local reads.
4. **⚠ Font ambiguity** — `Vazir.ttf`/`Vazir-Bold.ttf` exist in two places with
   different md5s and sizes (repo root vs `other_folder/`); which loaded
   depended on cwd. **The repo-root pair is canonical** and is what
   `backend/assets/fonts/` contains (md5 `398b39dd…` / `8cea4a72…`).
5. **⚠ `python-bidi` is pinned to 0.6.11** and the import must stay
   `from bidi.algorithm import get_display` — the legacy pure-Python impl.
   The package also exports a Rust `bidi.get_display` with different edge-case
   output, and 0.7.x removes `bidi.algorithm`. Changing this silently changes
   Persian shaping, so new PDFs would stop matching already-issued ones.
6. **Latent crashers to harden**: `whole_code.split('-')[2]` before its guard
   (`:416`); mutable defaults `creater=[]` then indexed `[0]` (`:942`);
   unguarded bold `setFont` (`:241`); `json.load` on an unvalidated HTTP body
   (`deliver_convert.py:186` — proven broken: `check/teststs-WI-02-02-01.json`
   is a saved S3 `NoSuchKey` error body).

**Rendering fidelity:** the algorithm is ported as written. Its cosmetic quirks
are preserved deliberately — page 1 gets no watermark; the final page's
watermark and footnote each draw twice; furniture draws under body content on
pages ≥2; `add_body_text` wraps on character count rather than `stringWidth`.
Only the crash-level bugs above are fixed.

---

## 6. Workflow, roles, and screens

**Auth in V_1.0:** a hardcoded dict `{"9876543210": "123456789"}`
(`main.py:19-21`), and **login is bypassed entirely** (`main.py:1059`).
Validation has three real bugs: username and password are checked against the
key set and value set *independently*; `not r.isnumeric` is missing `()` so
that branch is unreachable; and the CAPTCHA answer is checked against all six
pairs rather than the displayed one. **There is no session** — the dashboard
hardcodes `کاربر: مدیر عامل` and signer identity comes from modal prompts, so
anyone can type any name and role. V2 takes identity from the session.

**Role matrix** (`register.py:739-769`) — live, but currently gates nothing:
`determiner()` only sets two labels, `successful()` persists nothing, and there
is no role check anywhere in the live tree.

| Access Roll | لول ۱ | لول ۲ | لول ۳ |
|---|---|---|---|
| **کارفرمایی** | مدیر عامل | رئیس هیئت مدیره | عضو هیئت مدیره |
| **ستادی** | نماینده مدیریت | معاون/مشاور | مدیر/رئیس |
| **صفی** | سرپرست | کارشناس | کارمند/اپراتور |

> **Resolved:** who may create vs. confirm vs. approve is not expressed
> anywhere in V_1.0. The product owner confirmed the policy implemented in
> Phase 1 — creator = صفی/ستادی, confirmer = ستادی, approver = کارفرمایی. See
> the capability table in the Phase 1 tracker below.

**Lifecycle:** register slot → compose in Poster → تدوین / تایید / تصویب /
وضعیت کنترل. The four panels **render simultaneously in one scrolling view**
(`main.py:500-512`), not as a wizard.

**مرجوع (Returned) is a no-op today** — wired to `enable_all`, the same handler
as the two ویرایش buttons: no state persisted, no reason captured, no audit.
✅ *Phase 5 built it properly (reviewer returns to DRAFT, reason required, audited).*

**Screens that don't exist yet** in V_1.0 (buttons present but mis-wired):
Document History (`main.py:909` → `change_to_poster` with no args →
`TypeError`), Settings (`:938`, same), Account (`:946`, no command), and
کارتابل/inbox (`create_confirm…py:1676`, no command). These are net-new.

**QR semantics — the most important fix.** Today the QR encodes a *predicted
static S3 PDF URL* built from a label's text (`poster_01.py:1094`). So marking
a document obsolete later doesn't change what a printed QR resolves to; an old
revision's QR serves the old PDF forever still showing معتبر; and editing the
title silently breaks the link. The on-screen copy promises
«با اسکن کد از معتبر بودن مستندات اطمینان حاصل فرمایید». V2 makes that true:
the QR points at `GET /verify/{code}-{revision}`, a live status page.

---

## 7. Progress Tracker

Status: `Not Started` · `In Progress` · `Done`

### Phase 0 — Foundations & cleanup ✅ **Done**
| Item | Status | Notes |
|---|---|---|
| Rewrite `skeleton.md` against real V_1.0 | Done | this file |
| Delete wrong-domain `apps/documents`, `apps/posters` | Done | backed up to scratchpad before removal |
| Delete stale frontend domain pages + components | Done | `documents/`, `posters/`, `validate/` |
| `apps/core/constants.py` — Persian domain vocabulary | Done | groups, categories, statuses, roles, section types |
| Celery app + worker service | Done | `config/celery.py`, compose `celery` service |
| PDF/Persian deps pinned | Done | reportlab 5.0.1, python-bidi 0.6.11, arabic-reshaper 3.0.1, jdatetime 6.1.0 |
| Vazir fonts vendored (repo-root pair) | Done | `backend/assets/fonts/`, checksum-verified |
| Frontend Persian RTL shell | Done | `lang="fa" dir="rtl"`, Vazir via `next/font/local` |
| `lib/jalali.ts` date helpers | Done | Intl `fa-IR-u-ca-persian` |
| `middleware.ts` → `proxy.ts` | Done | required by Next.js 16 |
| Backend `check` + `makemigrations --check` clean | Done | verified |
| Frontend `tsc --noEmit` + `next build` clean | Done | verified |

### Phase 1 — Identity & RBAC ✅ **Done**
Verified on the live docker-compose stack (real Postgres + Redis + Celery), in
a browser, in Persian RTL — not just unit tests.

| Item | Status | Notes |
|---|---|---|
| Persian titles in `User.TITLE_MATRIX` | Done | all 9 combinations tested |
| `AccessRoll`/`AccessLevel` Persian labels | Done | کارفرمایی/ستادی/صفی · لول ۱-۳ |
| Real national-code login replacing the dict | Done | credentials checked **as a pair** (V_1.0 checked them independently) |
| Personnel CRUD that persists | Done | confirmed in Postgres; UI-created user can log in |
| Capability policy (`Capability`, `ROLL_CAPABILITIES`) | Done | see below |
| `HasCapability` DRF permission | Done | `apps/core/permissions.py` |
| Personnel writes gated on `manage_personnel` | Done | reads open to any authenticated user |
| `/auth/me/` exposes `capabilities` | Done | |
| Frontend `CurrentUserProvider` + capability-gated nav/pages | Done | `lib/current-user.tsx` |
| Logout revokes tokens via Redis blacklist | Done | old access **and** refresh tokens return 401 after logout |
| CSRF enforced on cookie-authenticated writes | Done | missing header → 403 |
| `is_staff` not settable through the personnel API | Done | privilege-escalation guard, tested |
| Prod refuses to boot on the dev `SECRET_KEY` | Done | `prod.py`; key also signs JWTs |

**Access policy (confirmed by the product owner):**

| Capability | Granted to |
|---|---|
| `create_document` (تدوین) | صفی، ستادی |
| `confirm_document` (تایید) | ستادی |
| `approve_document` (تصویب) | کارفرمایی |
| `manage_personnel` | کارفرمایی |

Separation of duties is deliberate and tested: no single roll holds the full
create → confirm → approve chain. Capabilities are computed from the access
roll on `User`, not mirrored into Django Groups — the earlier group-syncing
signal and seed migration were removed as a redundant second source of truth.

**Gotchas found while verifying:**
- The Next.js dev server in the container **latches** the "both `middleware.ts`
  and `proxy.ts` detected" error if both exist even momentarily, and then 404s
  every route until restarted (`docker compose restart frontend`). The stale
  state is in the running process, not on disk.
- The compose backend image must be rebuilt (`--build`) after `requirements/`
  changes — the pre-Phase-0 image crashed on `import celery`.
- `.env` is a copy of `.env.example`; a `change-me` `DJANGO_SECRET_KEY` is only
  9 bytes and triggers PyJWT's HS256 key-length warning. Generate a real one.

**Not verified:** Enter-key form submission on the login page — the browser
automation's keypress didn't trigger it, though the button click did. It's a
standard `<form>` with a submit button, so this is likely a tool artifact, but
it hasn't been confirmed by hand.

### Phase 2 — Document registry (ساخت مستند) ✅ **Done**
Verified in a browser against the live stack and by 76 backend tests on real
Postgres — including concurrency tests with real threads. The register reads
**only** from Postgres; it never opens or renders a PDF.

| Item | Status | Notes |
|---|---|---|
| `Document` / `DocumentSequence` / `SignOff` models + migration | Done | constraints enforced in the database, not just the service |
| Gapless, race-free numbering | Done | row lock on the group's counter; a rejected create rolls its number back |
| Group → prefix mapping (پوستر/روش اجرایی/دستورالعمل/فرم → PO/PR/WI/FR) | Done | ported literally; the crossed prefixes are tested |
| `POST /documents/` (create) | Done | needs `create_document` (تدوین) |
| `POST /documents/{id}/revise/` | Done | previous revision must be finished; latest only; capped at 99 |
| `GET /documents/` — search, filters, pagination | Done | server-side; 25/page; N+1-free (3 queries) |
| Persian text normalization | Done | Arabic ي/ك ↔ Persian ی/ک for titles and search; Persian digits in search |
| Register page (13 columns, search, filters, create form, pager) | Done | `frontend/app/(app)/documents/page.tsx` |
| Dashboard shows **real** counts | Done | was hardcoded mock data; all revisions counted; cache invalidated on change |
| `ConflictError` (409 with typed payload) | Done | `apps/core/exceptions.py`; reused by later phases |
| Persian validation messages | Done | V_1.0's «Pleas finish X field» warnings |
| Row actions: تکمیل / اتمام / چاپ | all live: تکمیل (Phase 3), چاپ (Phase 4), the sign-off buttons replacing «اتمام» (Phase 5) | |
| Attachment "Select" mode of the register | Done in Phase 3 | as a picker modal inside the designer |
| چاپ لیست (bulk download of built PDFs) | Not Started | Phase 6 |
| حسابکش / پاسخ خواه / پاسخگو columns | Done in Phase 3 | derived from the Responsibilities block; follow the row labels |
| تدوین / تائید / تصویب columns | Done | name + Jalali date, filled by the sign-off workflow (Phase 5) |

#### Registry numbering
The code is `<PREFIX>-<NN>-<RR>` (e.g. `PR-01-01`). V_1.0's number came from
the *last row in the group* (`group_grouth`, `documents_01.py:658-675`), which
was both racy **and wrong**: revision rows were always stored with
`simple_code: "1"` (the local is initialised at `:694` and never reassigned on
the revision path, `:780`), so after any revision the next new document in the
group was handed a number that already existed.

#### Behavioural differences from V_1.0 (deliberate)
- **A draft shows revision `01`, not `00`.** V_1.0 used `0-0` as a "never
  finalized" sentinel and coerced it to `01` in five places. Here the state is
  the explicit `status = DRAFT`; the revision is always ≥ 1.
- **Typing an existing title is an error, not a silent new revision.** V_1.0
  inferred "new revision" from whether the title happened to exist. Now there are
  two explicit operations, and the error says what to do — «ابتدا آن مستند را
  تکمیل کنید» while it's a draft, «بازنگری جدید» once it's finished.
- **Revision search matches what is displayed.** V_1.0 searched the raw stored
  `"0-1"`, so typing the shown `01` never matched (`documents_01.py:872`); its own
  search placeholder «مثال: برون سازمانی» could never match anything either,
  because V_1.0 stores categories as the English `'Inside Organization'` /
  `'Outside Organization'` (`:1734`).
- **Category labels are a translation.** The Persian labels داخل سازمانی /
  برون سازمانی are mine; V_1.0 displays the English strings. Row-action labels
  (تکمیل / اتمام / چاپ ← Complete / Finish / Print) are translated likewise.
- **Documents can't be edited or deleted through the API** — V_1.0's UI didn't
  offer it either.

#### Notes for the Phase 6 importer
- Derive `number` from the stored **`code`** (`"PO-01"` → 1). **Never trust
  `simple_code`** — see the bug above.
- `review "0-0"` → `revision 1`, `status DRAFT`; otherwise `revision = 10·one + two`.
- After import, set `DocumentSequence.last_number` to the max `number` per group.
- Map `category` with `LEGACY_CATEGORY_VALUES` (`apps/core/constants.py`).
- Normalize titles with `normalize_title` — V_1.0's own data mixes Arabic and
  Persian yeh (its PDF filenames do), which would otherwise split one document
  into two.

#### Gotchas found while verifying
- **The dev database held tables from the *deleted* Phase-0 apps**, including a
  `documents_document` with the old wrong-domain schema — and the rewritten
  migration has the same name (`documents.0001_initial`), so Django considered
  it applied and skipped it. Fixed by dropping the ten stale (empty) tables and
  their `django_migrations` rows. If you see "No migrations to apply" but the
  columns are wrong, that is the cause.
- **A wrong password on the login page silently reloaded it** (Phase 1 bug,
  found and fixed here). `api-client` treated *any* 401 as an expired session —
  including login's own — tried a refresh, failed, and hard-reloaded `/login`.
  Session endpoints (`/auth/login|refresh|logout`) are now excluded.
- The API client only surfaced `{detail}` bodies, so DRF field errors showed as
  an English "Request failed with status 400". Field errors are now flattened
  into one Persian message.
- DRF's `APIException` stringifies every value in a dict `detail`, turning
  `existing_id: 1` into `"1"`. `ConflictError` carries its payload separately.
- SQL `LPad` **truncates** (`lpad('100', 2, '0')` → `'10'`); search uses an
  explicit `CASE` so numbers ≥ 100 still match.
- When the browser pane is hidden, screenshots and clicks time out; reading the
  page and DOM still works.

### Phase 3 — Document designer ✅ **Done**
Verified in a browser against the live stack, by 143 backend tests on real
Postgres (including two-thread concurrency tests) and 38 frontend unit tests.
Every mutation I tried against the backend tests was caught except one equivalent
mutant (see below).

| Item | Status | Notes |
|---|---|---|
| Models + migration (`Section`, `ResponsibilityRow`, `ChangeTableRow`, `AttachmentReference`, `DocumentFile`; `Document` gains logo, footnotes, `content_version`) | Done | |
| `GET/PUT /documents/{id}/content/` | Done | whole body in one transaction, keyed on the PK |
| Optimistic concurrency (`base_version`) | Done | stale save → 409 `version_conflict`; tested with 6 simultaneous threads → exactly one winner |
| Content locked once a document leaves draft | Done | 409 `content_locked`; reads stay open |
| The five block types, reorderable, deletable | Done | تشریحی کوتاه · تشریحی بلند · مسئولیت ها · جدول تغییرات · ضمائم |
| Rich text (B / I / U) | Done | V_1.0's inline markers, stored verbatim; refuses to nest styles (the renderer can't) |
| Responsibilities (4 roles × سمت/ناظر/توضیحات + notes) | Done | سمت/ناظر are **free text with the 9 titles as suggestions** |
| Register columns حسابکش / پاسخ خواه / پاسخگو | Done | derived; **follow the row labels** (V_1.0's positional mapping was a swap); no query per row |
| Changes Table with frozen history across *all* earlier revisions | Done | derived from the revision chain, not copied; dates server-assigned |
| Attachment references (picker modal, real FK, live status) | Done | can't self-attach; a linked row can be removed |
| File uploads (picture / file / video) with progress + cancel | Done | per-document, dedup by content hash, kind decided by extension, authenticated download |
| Logo upload | Done | normalized to **PNG**, EXIF-rotated, ≤1024px |
| **New revision starts as a copy of the previous one** | Done | blocks, footnotes, logo, attachments, files (physically copied); change rows are *not* copied |
| Designer page `/documents/[id]/edit` + read-only mode | Done | |
| Register row actions تکمیل / ویرایش / مشاهده | Done | live; چاپ/نمایش went live in Phase 4, sign-off buttons in Phase 5 |
| نمایش (PDF preview) | Done in Phase 4 | see Phase 4 |
| Attachment "Select" mode of the register | Done differently | a picker modal instead — nothing is lost by choosing one |

#### Behavioural differences from V_1.0 (deliberate)
- **A new revision starts as a copy**, not a blank designer. *(Confirmed by the
  product owner.)* V_1.0 made authors retype the whole document.
- **The Changes Table has no demo rows.** V_1.0 pre-filled every new table with
  two hardcoded rows («Changed Upcoming to Previous», «1403/07/27»;
  `utils.py:1243-1247`) — leftover development data.
- **Change history reaches back through every revision.** V_1.0 downloaded only the
  immediately previous revision's JSON (`deliver_convert.py:163-197`), so revision 3
  lost revision 1's rows.
- **One Responsibilities block and one Changes Table per document.** V_1.0 allowed
  several, then updated the register from whichever it saved last.
- **A linked attachment can be removed**, and an unlinked one is reported instead of
  silently dropped on save (V_1.0's `-` button only popped *unlinked* rows, and only
  `all_labels` was serialized).
- **Files can't collide across documents.** V_1.0 used one shared bucket keyed by bare
  filename and reused any existing object of that name, so two documents attaching
  *different* `form.docx` files silently shared one. Its dedup also read only the
  first 1000 keys (`list_objects_v2`).
- **Downloads need a signed-in user.** V_1.0's files sat in a public bucket.
- **`.xlsx` is allowed.** V_1.0's file dialog offered every Excel flavour except the
  common one (`utils.py:1645-1649`).
- **The `date` on a document is the last-saved date** (derived from
  `content_saved_at`), as in V_1.0, which re-stamped it on every save (`utils.py:511`).
- **Editing is only possible while the document is a draft.**

#### Files and logo
- On disk under `media/document_files/<doc-id>/<uuid>.<ext>` and
  `media/logos/<doc-id>/<uuid>.png`. Nothing user-controlled reaches a path.
- Caps (settings): 100 MB per file, 5 MB per logo, ≤ 25 megapixels.
- A file removed from its block is deleted **when the document is saved**, not
  immediately; an upload never attached to any block is swept by the next save.
  Save is held back while an upload is in flight, or that sweep would delete it.
- **The PDF renderer only draws a `.png` logo** and paints a *black box* for anything
  else (`to_make_pdf.py:159-160`), so a `.jpg` logo silently became a black square in
  V_1.0. Logos are re-encoded to PNG on the way in.

#### Notes for Phase 4 (PDF engine) — written before it was built; see the Phase 4 section below and `docs/08-pdf-engine.md`
- Sections are ordered; render in `position` order. The Long block has
  `heading`, `body`, `extra_boxes[]`, and files.
- **Open question — V_1.0 never printed a Long block's `extra_boxes` or file links.**
  `deliver_convert.py:119` uses only `main_entry + main_textbox`; both are silently
  dropped from the PDF even though the designer collects them. **Decided (Phase 4): extra boxes are printed; file links are not.**
- Change-table edition = the owning document's `revision_display`; earlier revisions'
  rows come from `Document.previous_change_rows()`; numbering continues across them.
- Attachment items have `caption` + `target` (a `Document`) — print the caption, the
  target's `full_code`, and its QR (which will point at the live `/verify/` page).
- The document date on the PDF is the local date of `content_saved_at`.

#### Notes for the Phase 6 importer
- V_1.0's `options[8]` → four `ResponsibilityRow`s: index *i* is the post, *i+4* the
  supervisor; `entries[i]` is the text of role *i*, and `entries[4:]` become notes.
  **Both dropdown values are the placeholder strings** `'Organiztion Post'` /
  `'SuperVisor'` in essentially every saved document — treat them as empty.
- `"type": "label"` change rows and their `previous_change` text are V_1.0's frozen
  rows; don't import the two hardcoded demo rows.
- Attachments: `all_labels[i] = [caption, "CODE-REV", qr_path]` → resolve `CODE-REV`
  to a `Document`; drop `qr_path`.
- Long-block `links` are Liara URLs — fetch them into `DocumentFile`s (or record that
  they were not migrated) rather than storing the URLs.

#### Gotchas found while verifying
- **Tests that pass on the first run deserve suspicion.** Eight behaviors were
  deliberately broken to prove the tests can fail; seven were caught. The survivor —
  removing the early "same bytes → return existing" branch — is an *equivalent
  mutant*: the unique constraint plus the `IntegrityError` fallback still dedupe, so
  dedup has two layers. A test now also asserts a duplicate leaves no stray bytes.
- **The app shell must be window-height.** `min-h-screen` let the shell grow with its
  content, so `<main>`'s `overflow-y-auto` never engaged: long pages scrolled the whole
  window (dragging the sidebar's log-out button to the bottom of the page) and a
  `sticky` bar inside `<main>` had nothing to stick to. Now `h-screen overflow-hidden`.
- **`apiUploadWithProgress` uses XHR**, because `fetch` cannot report upload progress.
- **`new Date("2026-09-19")` is UTC midnight** — the *previous day* west of UTC — so
  bare server dates are parsed as local calendar dates.
- **`fromResponse` keeps block keys across a save.** Otherwise every block remounts,
  and an upload still in flight finishes against a key that no longer exists.
- Blocks update through functional `update(s => …)` for the same reason: a handler
  holding a stale copy would overwrite what was typed while a file uploaded.
- npm: latest **vitest 5** wants `@types/node` ≥ 22, but the project pins `^20` to match
  the `node:20-alpine` runtime; **vitest 3** is used instead of forcing the peer.
- `react-hooks/set-state-in-effect` is an *error* in this project's lint config. The
  Phase 2 register page violated it and I hadn't linted it then; both it and the
  designer now derive loading state instead of setting it synchronously in an effect.
- `media/` still holds a few files from the deleted Phase-0 apps
  (`poster_attachments/test.png`, `qr/*.png`); harmless, and unrelated to V2.

**Not verified:** the Ctrl/⌘+B/I/U keyboard shortcuts (the toolbar buttons, which share
the code path, are verified — the automation's key events don't reach the handler); the
upload **cancel** button and the progress bar mid-transfer (files were tiny); picture and
video uploads in the browser (covered by the backend tests only).

### Phase 4 — PDF engine ✅ **Done**
Verified against V_1.0's own code (byte-for-byte oracle), by 63 new backend tests (209 total, real Postgres, real threads),
7 new frontend tests (45 total), a live 5-way concurrent Celery run, an empty-`media/` run, and in the browser. Detail: [`docs/08-pdf-engine.md`](docs/08-pdf-engine.md).

| Item | Status | Notes |
|---|---|---|
| `apps/pdfgen/renderer.py` — `HeaderFooterCanvas` + `PDFMaker` | Done | near-verbatim; images as PNG **bytes**, output as bytes; fonts registered once in `AppConfig.ready()`; crash fixes only (bold `setFont`, `split('-')[2]` guard, mutable defaults, `image_checker` moot) |
| Pinned stack | Done | `reportlab==5.0.1`, `python-bidi==0.6.11` with `from bidi.algorithm import get_display` (asserted by a test), Vazir via `settings.PDF_FONT_*` |
| `provider.py` (V_1.0 `Provider.deliver_to_pdf`) + `adapter.py` (Postgres → `PdfInput`) | Done | pure/instance-scoped — **no module globals** (V_1.0's `all_documents`/`SHORT` gone); all-revision change history; QR = `{FRONTEND_BASE_URL}/verify/{code}` |
| `PdfBuild` model (document × kind: official / preview) + migration | Done | status building/ready/failed, token, path, sha256, size, built_at, error |
| Celery task `pdfgen.build_pdf` | Done | idempotent, token compare-and-set, retries on transient errors, Persian failure text, time limits from settings |
| API `GET/POST /documents/{id}/pdf/{kind}/`, `GET …/download/` | Done | 202 + polling; typed 409s `not_finalized` / `build_in_progress`; authenticated inline download; register rows carry `pdf_status` with no extra query |
| Storage | Done | `media/pdfs/<id>/<code>.pdf` replaced atomically; `media/pdf_previews/<id>.pdf` |
| Capability `print_document` | Done | new, granted to all rolls; `HasCapability` on POST |
| Register buttons چاپ / بازسازی / نمایش | Done | live (the designer's own «نمایش» was wired in Phase 5) |
| Fidelity | Done | 4 golden PDFs from V_1.0's own renderer, byte-identical; mutation-checked; layout compared to `نمونه-PR-01-01.pdf` |

**Decisions (user):** explicit «ساخت PDF»; one file per revision replaced on rebuild; on-demand watermarked preview; Long `extra_boxes` **printed**
(V_1.0 dropped them); blank empty signature cells.

**Not fixed on purpose (user: preserve quirks) but worth their attention:** long body lines clip at the page edge (character-count wrapping);
`text_merge` drops a final wrapped word and can duplicate a chunk. Both listed in `docs/07-known-gaps.md` with the one-line cause.

**Not verified:** the PDF rendered inside a browser tab (the pane didn't surface the popup; requests + `pdftoppm` renders were checked instead);
the ناموفق banner / no-capability state by hand (unit-tested); archived-PDF comparison covers only Short blocks (they are all the archives contain).

**Carried into Phase 5 — all done:** rebuild on supersede, serve `/verify/{code}`, normalise signature PNGs on upload.

### Phase 5 — Workflow, signatures, status ✅ **Done**
Verified by 50 new backend tests (259 total; real Postgres, real threads; **11 mutations, each caught**), 12 new frontend tests (57 total), a live run through the real Celery
worker, and in the browser. Detail: [`docs/09-workflow.md`](docs/09-workflow.md).

| Item | Status | Notes |
|---|---|---|
| State machine DRAFT → AWAITING_CONFIRMATION → AWAITING_APPROVAL → UNDER_CONTROL | Done | `apps/documents/workflow.py`; one transaction + row lock per step; typed 409s `wrong_status` / `same_person` / `content_missing` |
| Four panels | Done differently | a sign dialog per step on the register/designer instead of four simultaneous panels; identity from the **session** (V_1.0 let anyone type any name) |
| Web signature pad | Done | canvas → PNG multipart; server normalises to opaque PNG, refuses a blank pad |
| مرجوع | Done | reviewer → DRAFT, **reason required**, sign-offs cleared, audited (V_1.0's was a no-op) |
| Separation of duties | Done | one person per step, enforced server-side; roll capabilities on top |
| Auto-obsolete the previous revision | Done | on approval; event SUPERSEDED |
| Auto-build PDFs on approval | Done | new revision built; superseded one rebuilt so it prints «منسوخ» |
| Audit trail (`DocumentEvent`) + `GET /documents/{id}/history/` | Done | actor name/post snapshotted; read-only admin |
| Register: per-user workflow buttons, name+date in تدوین/تائید/تصویب | Done | `row.workflow` computed without extra queries (list still 4 queries/page) |
| Designer: return banner, timeline, workflow buttons, live «نمایش» | Done | «نمایش» had been left disabled in Phase 4 — fixed |
| **Public `/verify/{code}`** (page + `GET /api/v1/verify/{code}/`) | Done | live status (valid / obsolete + pointer to the current revision / pending, which discloses nothing), per-IP rate limit, no cookies read, no-store |
| Migration `0003` | Done | `DocumentEvent`, `SignOff.signed_by`, signature path `signatures/<doc-id>/…` |

**Decisions (user):** reviewer returns to DRAFT with a mandatory reason and sign-offs cleared; each step needs a different person; auto-obsolete + auto-build; draw a signature at every sign-off.
**Not built on purpose:** inbox/کارتابل, withdrawing a submitted document, the PDF's free «متن آزاد» control text (V_1.0 `extra_header`).
**Not verified:** the approver's *browser* session (driven through the API), the pad on a touch device, the «پاک کردن» button, rate limiting behind a reverse proxy.
**Also fixed on the way:** Phase 4's stray dev user (helper bug) and the designer's dead «نمایش» button.

### Phase 6 — Dashboard, history, export, migration — **Not Started**
Real aggregate counts (V_1.0's are mock) · Document History as a genuine new
feature · چاپ لیست bulk download · Mongo + `saves/*.json` + `img/` signatures →
Postgres importer as a Celery job.

---

## 8. Verification

- **Per phase:** `docker compose up` clean; `manage.py check` and
  `makemigrations --check` pass; `tsc --noEmit` and `next build` pass; the
  phase's runnable outcome demonstrated in the browser in Persian RTL.
- **PDF fidelity (Phase 4 gate):** regenerate a document whose original exists
  (`نمونه-PR-01-01.pdf`, `روش اجرايي کنترل مستندات-PO-01-01.pdf`) from migrated
  data and compare page count, embedded font subsets (`Vazir`/`Vazir-Bold` as
  `/FontFile2`), control-table contents, and a visual diff of page 1.
- **Concurrency (Phase 4):** two simultaneous renders through Celery, confirm
  no cross-contamination — the exact failure the old module-global caused.
- **Fresh-container check:** build with an empty `media/` so the
  `image_checker` cache-miss path is exercised rather than masked.
- **Migration (Phase 6):** row counts match Mongo; every `saves/*.json` section
  survives round-trip; signature images resolve.
- **Data integrity:** the code/revision unique constraint holds under
  concurrent creates.
