"""V_1.0 row/JSON -> V_2 records: the pure mapping layer (no database)."""
from datetime import date

from django.test import SimpleTestCase

from apps.core.constants import DocumentCategory, DocumentGroup, DocumentStatus, SectionType, SignOffRole
from apps.importer import mapping
from apps.importer.mapping import RowError


def row(**over):
    base = {
        "category": "Inside Organization", "title": "روش کنترل", "group": "روش اجرایی", "review": "0-1",
        "code": "PR-01", "valid": "vali", "json_path": "https://files.invalid/user-files/x-PR-01-01.json",
        "simple_code": "1",
    }
    base.update(over)
    return base


def map_row(**over):
    return mapping.map_index_row(row(**over), 1)


class RevisionTests(SimpleTestCase):
    def test_review_is_tens_dash_units_and_0_0_means_never_saved(self):
        self.assertEqual(mapping.revision_for("0-0"), (1, True))
        self.assertEqual(mapping.revision_for("0-1"), (1, False))
        self.assertEqual(mapping.revision_for("0-9"), (9, False))
        self.assertEqual(mapping.revision_for("1-0"), (10, False))
        self.assertEqual(mapping.revision_for("9-9"), (99, False))
        self.assertEqual(mapping.revision_for(" 0 - 2 "), (2, False))

    def test_a_bad_review_is_a_row_error(self):
        for bad in ("", "x", "0-", "0-x", None, "1", "10-0", "0-100"):
            with self.assertRaises(RowError, msg=repr(bad)) as ctx:
                mapping.revision_for(bad)
            self.assertIn(ctx.exception.note.code, ("bad_review", "revision_out_of_range"))

    def test_status_comes_from_valid_because_v1_never_wrote_status(self):
        self.assertEqual(mapping.status_for("vali", "0-1")[0], DocumentStatus.UNDER_CONTROL)
        self.assertEqual(mapping.status_for("outdated", "0-1")[0], DocumentStatus.OBSOLETE)
        self.assertEqual(mapping.status_for("unknown", "0-0"), (DocumentStatus.DRAFT, []))
        status, notes = mapping.status_for("valid", "0-1")  # not V_1.0's spelling: don't guess
        self.assertEqual(status, DocumentStatus.DRAFT)
        self.assertEqual(notes[0].code, "unknown_valid")


class IndexRowTests(SimpleTestCase):
    def test_a_normal_row(self):
        rec = map_row()
        self.assertEqual((rec.full_code, rec.group, rec.number, rec.revision), ("PR-01-01", DocumentGroup.PROCEDURE, 1, 1))
        self.assertEqual((rec.status, rec.category), (DocumentStatus.UNDER_CONTROL, DocumentCategory.INSIDE))
        self.assertEqual(rec.json_name, "x-PR-01-01.json")
        self.assertEqual(rec.family, (DocumentGroup.PROCEDURE, 1))

    def test_number_comes_from_code_never_from_simple_code(self):
        # V_1.0 stored simple_code "1" for every revision row and after any revision (documents_01.py:694).
        self.assertEqual(map_row(code="PR-07", simple_code="1").number, 7)
        self.assertEqual(map_row(code="PR-123").number, 123)  # three digits simply grow, as in V_2

    def test_every_group_and_its_deliberately_crossed_prefix(self):
        for label, prefix, group in (("پوستر", "PO", "POSTER"), ("روش اجرایی", "PR", "PROCEDURE"),
                                     ("دستورالعمل", "WI", "INSTRUCTION"), ("فرم", "FR", "FORM")):
            self.assertEqual(map_row(group=label, code=f"{prefix}-01").group, group)

    def test_group_labels_are_matched_across_arabic_and_persian_letters(self):
        self.assertEqual(map_row(group="روش اجرايي").group, DocumentGroup.PROCEDURE)  # Arabic yeh, as in V_1.0's data
        self.assertEqual(map_row(group="POSTER", code="PO-02").group, "POSTER")  # an enum value is accepted too

    def test_unknown_group_and_prefix_mismatch_are_errors(self):
        with self.assertRaises(RowError) as ctx:
            map_row(group="ناشناخته")
        self.assertEqual(ctx.exception.note.code, "unknown_group")
        with self.assertRaises(RowError) as ctx:
            map_row(group="پوستر", code="PR-01")  # POSTER is PO, not PR
        self.assertEqual(ctx.exception.note.code, "code_group_mismatch")
        self.assertIn("PO", ctx.exception.note.message)

    def test_bad_codes_are_errors(self):
        for bad in ("", "PR", "PR-", "PR-00", "1-PR", "PR-01-01", None):
            with self.assertRaises(RowError, msg=repr(bad)):
                map_row(code=bad)

    def test_title_is_normalised_and_required(self):
        self.assertEqual(map_row(title="  روش   اجرايي  كنترل ").title, "روش اجرایی کنترل")
        for empty in ("", "   ", None):
            with self.assertRaises(RowError) as ctx:
                map_row(title=empty)
            self.assertEqual(ctx.exception.note.code, "missing_title")

    def test_never_saved_row_is_a_draft_of_revision_one(self):
        rec = map_row(review="0-0", valid="unknown", json_path="")
        self.assertEqual((rec.revision, rec.status, rec.json_name), (1, DocumentStatus.DRAFT, ""))

    def test_valid_on_a_never_saved_row_is_downgraded_with_a_warning(self):
        rec = map_row(review="0-0", valid="vali")
        self.assertEqual(rec.status, DocumentStatus.DRAFT)
        self.assertIn("valid_but_never_saved", [n.code for n in rec.notes])

    def test_category_uses_the_legacy_english_strings_and_warns_on_unknown(self):
        self.assertEqual(map_row(category="Outside Organization").category, DocumentCategory.OUTSIDE)
        self.assertEqual(map_row(category="OUTSIDE").category, DocumentCategory.OUTSIDE)
        rec = map_row(category="???")
        self.assertEqual(rec.category, DocumentCategory.INSIDE)
        self.assertIn("unknown_category", [n.code for n in rec.notes])

    def test_the_index_rows_overwritten_signer_shape_is_kept_for_later(self):
        rec = map_row(creater=["علی", "1404/01/19"], confirmer=["", ""], approver="oops")
        self.assertEqual(rec.index_signers, {"creater": ["علی", "1404/01/19"]})

    def test_json_name_is_only_ever_a_bare_file_name(self):
        self.assertEqual(map_row(json_path="https://h/user-files/a%20b.json").json_name, "a b.json")
        self.assertEqual(map_row(json_path="../../etc/passwd").json_name, "passwd")
        self.assertEqual(map_row(json_path="..\\..\\evil.json").json_name, "evil.json")
        self.assertEqual(map_row(json_path="..").json_name, "")

    def test_a_non_dict_row_is_an_error(self):
        with self.assertRaises(RowError):
            mapping.map_index_row("nope", 3)


class HelperTests(SimpleTestCase):
    def test_jalali_dates(self):
        self.assertEqual(mapping.parse_jalali("1404/01/19"), date(2025, 4, 8))  # the archived sample's date
        self.assertEqual(mapping.parse_jalali(" 1403/12/30 "), date(2025, 3, 20))
        self.assertEqual(mapping.parse_jalali("1404-1-1"), date(2025, 3, 21))
        for bad in ("", None, "1404/13/01", "1404/02/32", "2025/04/08x", "x", 5):
            self.assertIsNone(mapping.parse_jalali(bad), repr(bad))

    def test_document_codes(self):
        self.assertEqual(mapping.parse_document_code("pr-1-1"), ("PROCEDURE", 1, 1))
        self.assertEqual(mapping.parse_document_code("WI-02-02"), ("INSTRUCTION", 2, 2))
        self.assertIsNone(mapping.parse_document_code("XX-01-01"))
        self.assertIsNone(mapping.parse_document_code("PR-01"))
        self.assertEqual(mapping.normalize_document_number("po-3-7"), "PO-03-07")


def content(items=None, **over):
    data = {"title": "t", "logo_path": "https://h/logos/b-icon-new.png", "document_number": "PR-01-01", "date": "1404/01/19",
            "creater": ["علی رضایی", "کارشناس", "https://h/user-files/PR-01-00creater.png"],
            "approver": ["", "", ""], "confirmer": ["", "", ""], "validation": "معتبر",
            "footnotes": {"footnote1": "بالا", "footnote2": "پایین"}, "dynamic_items": items or []}
    data.update(over)
    return mapping.map_content(data)


class ContentTests(SimpleTestCase):
    def test_header_signers_and_footnotes(self):
        rec = content()
        self.assertEqual(rec.date, date(2025, 4, 8))
        self.assertEqual((rec.logo_name, rec.footnote1, rec.footnote2), ("b-icon-new.png", "بالا", "پایین"))
        self.assertEqual([(s.role, s.name, s.position, s.signature_name) for s in rec.signers],
                         [(SignOffRole.CREATER, "علی رضایی", "کارشناس", "PR-01-00creater.png")])  # blank signers skipped

    def test_short_and_long_blocks(self):
        rec = content([
            {"type": "Short Explanation", "content": ["1-هدف", "متن"]},
            {"type": "Long Explanation", "content": {"main_entry": "2-شرح", "main_textbox": "بدنه", "additional_textboxes": ["جعبه ۱", "جعبه ۲"],
                                                    "links": ["https://h/a.pdf", "https://h/b.pdf"]}},
        ])
        self.assertEqual(rec.sections[0], (SectionType.SHORT_EXPLANATION, {"lines": ["1-هدف", "متن"]}))
        self.assertEqual(rec.sections[1], (SectionType.LONG_EXPLANATION,
                                           {"heading": "2-شرح", "body": "بدنه", "extra_boxes": ["جعبه ۱", "جعبه ۲"]}))
        links = [n for n in rec.notes if n.code == "links_not_migrated"]
        self.assertEqual(len(links), 1)
        self.assertIn("2", links[0].message)  # says how many were left behind

    def test_responsibilities_split_the_eight_option_slots_and_drop_the_placeholders(self):
        # options[i] = post, options[i+4] = supervisor; both dropdowns held one hardcoded placeholder.
        rec = content([{"type": "Responsibilities", "content": {
            "options": ["مدیر", "Organiztion Post", "کارشناس", "", "ناظر ۱", "SuperVisor", "", "ناظر ۴"],
            "entries": ["متن ۱", "متن ۲", "متن ۳", "متن ۴", "یادداشت الف", "یادداشت ب"]}}])
        _, payload = rec.sections[0]
        self.assertEqual([(r["role"], r["post"], r["supervisor"], r["text"]) for r in payload["roles"]], [
            ("responder", "مدیر", "ناظر ۱", "متن ۱"),
            ("receiver", "", "", "متن ۲"),                # both placeholders -> empty
            ("cash_account", "کارشناس", "", "متن ۳"),
            ("supervisor", "", "ناظر ۴", "متن ۴"),
        ])
        self.assertEqual(payload["notes"], ["یادداشت الف", "یادداشت ب"])

    def test_short_options_and_entries_are_padded_not_crashed(self):
        rec = content([{"type": "Responsibilities", "content": {"options": ["مدیر"], "entries": ["فقط یکی"]}}])
        roles = rec.sections[0][1]["roles"]
        self.assertEqual((roles[0]["post"], roles[0]["text"], roles[3]["text"]), ("مدیر", "فقط یکی", ""))

    def test_changes_table_keeps_only_this_revisions_own_rows(self):
        entry = lambda text, when, kind="entry": {"column_number": "1", "edition": "01", "date": when,
                                                  "content": {"text": text, "type": kind, "previous_change": None}}
        rec = content([{"type": "Changes Table", "content": {"rows": [
            entry("قدیمی", "1403/12/30", "label"),           # frozen from an earlier revision: derived in V_2
            entry("جدید", "1404/01/19"),
            entry("تاریخ بد", "not-a-date"),
            entry("", "1404/01/19"),                          # empty text: nothing to import
        ]}}])
        rows = rec.sections[0][1]["rows"]
        self.assertEqual([(r["text"], r["date"]) for r in rows],
                         [("جدید", date(2025, 4, 8)), ("تاریخ بد", date(2025, 4, 8))])  # bad date -> the document's date
        codes = [n.code for n in rec.notes]
        self.assertIn("frozen_change_rows", codes)
        self.assertIn("bad_change_date", codes)

    def test_a_change_row_with_no_usable_date_at_all_is_dropped_with_a_warning(self):
        rec = content([{"type": "Changes Table", "content": {"rows": [
            {"date": "bad", "content": {"text": "x", "type": "entry"}}]}}], date="")
        self.assertEqual(rec.sections[0][1]["rows"], [])
        self.assertIn("change_row_dropped", [n.code for n in rec.notes])

    def test_attachments_are_caption_and_code_and_the_qr_path_is_dropped(self):
        rec = content([{"type": "Attachment", "content": [], "all_labels": [
            ["فرم درخواست", "pr-02-01", "./qr/PR-02-01.png"], ["", "PO-01-01", "x"], ["بدون کد", "", "x"], "junk"]}])
        self.assertEqual(rec.sections[0], (SectionType.ATTACHMENT, {"items": [("فرم درخواست", "PR-02-01")]}))
        self.assertEqual(rec.attachments, [("فرم درخواست", "PR-02-01")])

    def test_one_responsibilities_and_one_changes_block_per_document(self):
        block = {"type": "Responsibilities", "content": {"options": [], "entries": []}}
        rec = content([block, block])
        self.assertEqual(len(rec.sections), 1)
        self.assertIn("duplicate_block", [n.code for n in rec.notes])

    def test_unknown_blocks_and_garbage_are_noted_not_fatal(self):
        rec = content([{"type": "Mystery", "content": 1}, "junk", {"type": "Short Explanation", "content": "not a list"}])
        self.assertIn("unknown_block", [n.code for n in rec.notes])
        self.assertEqual(rec.sections, [(SectionType.SHORT_EXPLANATION, {"lines": []})])
        self.assertEqual(mapping.map_content("nope").notes[0].code, "bad_content")
        self.assertEqual(mapping.map_content({}).sections, [])
