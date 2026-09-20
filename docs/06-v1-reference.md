# V_1.0 reference (the original app) — what to read, what to ignore

`/Users/samlv/WorkFlow/VEye/V_1.0` — CustomTkinter desktop app, ~25k lines, MongoDB on Liara + Liara S3.
It is the **spec for behaviour**, not a source of code to copy (except the PDF renderer).

## LIVE files (9) — plan against these only
`main.py`, and in `other_folder/`: `Dashboard.py`, `documents_01.py`, `create_confirm_approval_statusControl.py`,
`register.py`, `poster_01.py`, `utils.py`, `deliver_convert.py`, `to_make_pdf.py`.

## DEAD files — do not port from these
`other_folder/{documents,poster,utils_01,test01-04}.py`, `clearing_the_database.py`, `qr/gen.py`, and
**`documents_01 (1).py` at the repo root** (cannot import; English group names — using it would wire the wrong
prefix mapping). Live group names are Persian.

## Where things are in V_1.0
| Topic | Location |
|---|---|
| Group→code prefix mapping | `documents_01.py:699-706` |
| Index-row fields written to Mongo | `documents_01.py:714-733` |
| Content JSON shape | `utils.py:507-525` |
| Role×level سمت matrix | `register.py:739-769` |
| Register row actions (Complete/Finish/Print/Select) | `documents_01.py:886-902` |
| Four sign-off panels, rendered simultaneously | `main.py:500-512`; workflow in `create_confirm_approval_statusControl.py` |
| PDF renderer | `to_make_pdf.py` (~1090 lines, no GUI imports) |
| PDF data adapter (`Provider`) | `deliver_convert.py` |
| QR generation to reuse | `utils.py:193` `generate_qr` (**not** `qr/gen.py`) |
| Dashboard status columns | `Dashboard.py:344-350` |

## Sample data available for verification
`saves/*.json` (content per document), `check/` (cached previous-revision JSON; `check/teststs-WI-02-02-01.json` is a saved S3
error body — broken), `qr/`, `img/` (signatures named `<CODE>-<REV>{creater|confirmer|approver}.png`), and archived PDFs
in the V_1.0 root (e.g. `نمونه-PR-01-01.pdf`, `روش اجرايي کنترل مستندات-PO-01-01.pdf`). Two Vazir font pairs exist
(repo root vs `other_folder/`, different md5s) — **the repo-root pair is authoritative** and is vendored in `backend/assets/fonts/`.

## ⚠ Secrets — never carry into V_2.0
Committed in V_1.0 and its git history: Mongo URI + password (`other_folder/utils.py:90`, `clearing_the_database.py:21`, `test02/03.py`),
Liara S3 access key/secret (`utils.py:26-27,1629-1630`, `create_confirm…py:18-19`, `utils_01.py:1444-1445`), app login dict
(`main.py:19-21`). **The user still needs to rotate these.** Nothing in V_2.0 uses them; do not read them into any file, log or prompt.
The Phase 6 importer (`manage.py import_v1`) takes Mongo access only through an environment variable supplied at run time (or a mongoexport file) — see [10-phase-6.md](10-phase-6.md). V_1.0's Mongo database/collection defaults are `my_database` / `my_collection` (`utils.py` `MongoDBClient`).

## Real V_1.0 bugs (so you don't reproduce them)
- Login checked username and password against key/value sets independently; login itself was bypassed (`main.py:1059`).
- Registered personnel were never persisted; مرجوع is a no-op wired to `enable_all`.
- Document History / Settings / Account / کارتابل buttons are dead or mis-wired.
- `status` field never written; `"vali"` typo; `"00"` revision sentinel coerced to `"01"` in five places; revision wraps at 99.
- Code numbering racy and wrong (`simple_code`); blind `update_document("json_path","",…)` patches the wrong row.
- QR encoded a predicted static S3 PDF URL built from a label's text → V_2 points at a live `/verify/` page.
- `image_checker` writes the `Response` object (not `.content`) for two of three signature roles → TypeError on any cache miss.
- Module-global `all_documents` in `deliver_convert.py` → concurrent renders would corrupt each other.

## Field-name traps
`creater` (misspelled everywhere), `questioner` = پاسخ‌خواه, `accountant` = حسابکش, `responder` = پاسخگو. In V_2 the register
columns follow the row labels: حسابکش←Cash Account, پاسخ‌خواه←Receiver, پاسخگو←Responder.
