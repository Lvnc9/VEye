"""The form body (Phase 11, ADR-011): body kind, element validation, the
content API for a فرم, and copying forward into a revision."""
from django.test import SimpleTestCase

from apps.core.constants import BodyKind, DocumentGroup, SectionType

from . import form_schema, services
from .models import Section
from .test_designer import DesignerTestCase, short
from .tests import finalize, new_doc

FORM = SectionType.FORM_ELEMENT


def el(kind, section_id=None, **props):
    return {"id": section_id, "type": FORM, "kind": kind, **props}


class BodyKindTests(DesignerTestCase):
    def test_a_new_form_gets_the_form_body_and_default_settings(self):
        form = new_doc(self.author, "فرم استخدام", DocumentGroup.FORM)
        self.assertEqual(form.body_kind, BodyKind.FORM)
        self.assertEqual(form.form_settings, form_schema.default_settings())
        self.assertEqual(form.form_settings["orientation"], "portrait")

    def test_every_other_group_keeps_blocks(self):
        for group in (DocumentGroup.POSTER, DocumentGroup.PROCEDURE, DocumentGroup.INSTRUCTION):
            with self.subTest(group=group):
                doc = new_doc(self.author, f"سند {group}", group)
                self.assertEqual(doc.body_kind, BodyKind.BLOCKS)
                self.assertEqual(doc.form_settings, {})

    def test_the_content_api_reports_the_body_kind(self):
        form = new_doc(self.author, "فرم", DocumentGroup.FORM)
        data = self.get_content(form)
        self.assertEqual(data["body_kind"], "form")
        self.assertEqual(data["form_settings"]["base_font_size"], 10)
        data = self.get_content()
        self.assertEqual(data["body_kind"], "blocks")
        self.assertIsNone(data["form_settings"])


class FormContentTests(DesignerTestCase):
    def setUp(self):
        super().setUp()
        self.form = new_doc(self.author, "فرم استخدام", DocumentGroup.FORM)

    def put_form(self, sections, **extra):
        return self.put(sections, doc=self.form, **extra)

    def test_elements_round_trip_normalised(self):
        data = self.save(
            [
                el("heading", text="مشخصات فردی", numbered=True, junk="dropped"),
                el("text", text="با **خودکار** بنویسید.", boxed=True),
                el("divider", style="double", thickness=1.5),
                el("spacer", height=12),
                el("page_break"),
            ],
            doc=self.form,
        )
        sections = data["sections"]
        self.assertEqual([s["kind"] for s in sections], ["heading", "text", "divider", "spacer", "page_break"])
        self.assertTrue(all(s["type"] == FORM for s in sections))
        heading = sections[0]
        # Defaults filled in, unknown keys dropped.
        self.assertEqual(heading["style"], "band")
        self.assertEqual(heading["level"], 1)
        self.assertNotIn("junk", heading)
        self.assertEqual(sections[1]["text"], "با **خودکار** بنویسید.")
        self.assertEqual(sections[2]["thickness"], 1.5)
        self.assertEqual(sections[3]["height"], 12)
        stored = Section.objects.get(pk=heading["id"])
        self.assertEqual(stored.type, FORM)
        self.assertEqual(stored.content["kind"], "heading")

    def test_a_saved_element_keeps_its_id(self):
        first = self.save([el("heading", text="الف")], doc=self.form)["sections"][0]["id"]
        again = self.save([el("heading", first, text="ب"), el("spacer")], doc=self.form)["sections"]
        self.assertEqual(again[0]["id"], first)
        self.assertEqual(again[0]["text"], "ب")
        self.assertEqual(Section.objects.filter(document=self.form).count(), 2)

    def test_settings_are_saved(self):
        settings = {
            "orientation": "landscape",
            "base_font_size": 11,
            "approval_strip": False,
            "header": {"subtitle": "واحد منابع انسانی", "show_letter_box": True},
        }
        data = self.save([], doc=self.form, form_settings=settings)
        self.assertEqual(data["form_settings"]["orientation"], "landscape")
        self.assertEqual(data["form_settings"]["header"]["subtitle"], "واحد منابع انسانی")
        self.assertTrue(data["form_settings"]["header"]["show_company_name"])  # default kept
        self.form.refresh_from_db()
        self.assertFalse(self.form.form_settings["approval_strip"])

    def test_bad_settings_are_refused_in_persian(self):
        response = self.put_form([], form_settings={"orientation": "diagonal", "base_font_size": 30})
        self.assertEqual(response.status_code, 400)
        messages = response.data["form_settings"]
        self.assertTrue(any("جهت صفحه" in m for m in messages), messages)
        self.assertTrue(any("اندازه قلم" in m for m in messages), messages)

    def test_a_form_refuses_classic_blocks(self):
        response = self.put_form([short("متن")])
        self.assertEqual(response.status_code, 400)
        self.assertIn("فقط اجزای فرم", str(response.data["sections"]))

    def test_a_block_document_refuses_form_elements(self):
        response = self.put([el("heading", text="x")])
        self.assertEqual(response.status_code, 400)
        self.assertIn("فقط در مستندهای فرم", str(response.data["sections"]))

    def test_invalid_elements_are_all_reported_with_their_position(self):
        response = self.put_form(
            [
                el("heading", text="ok"),
                el("heading", text="x", level=5),
                el("banana"),
                el("divider", thickness=True),
                el("text", text="ب" * (form_schema.MAX_TEXT + 1)),
            ]
        )
        self.assertEqual(response.status_code, 400)
        messages = response.data["sections"]
        self.assertEqual(len(messages), 4, messages)
        self.assertIn("جزء ۲ (عنوان بخش)", messages[0])
        self.assertIn("سطح عنوان", messages[0])
        self.assertIn("جزء ۳: نوع جزء فرم نامعتبر است", messages[1])
        self.assertIn("ضخامت خط", messages[2])
        self.assertIn("۵۰۰۰", messages[3])

    def test_the_element_cap(self):
        response = self.put_form([el("spacer")] * (form_schema.MAX_ELEMENTS + 1))
        self.assertEqual(response.status_code, 400)
        ok = self.put_form([el("spacer")] * form_schema.MAX_ELEMENTS)
        self.assertEqual(ok.status_code, 200)

    def test_block_documents_keep_their_100_block_cap(self):
        response = self.put([short("x")] * 101)
        self.assertEqual(response.status_code, 400)
        self.assertIn("بیش از 100 بخش", str(response.data["sections"]))

    def test_settings_sent_to_a_block_document_are_ignored(self):
        self.save([short("x")], form_settings={"orientation": "landscape"})
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.form_settings, {})

    def test_a_revision_keeps_the_form(self):
        self.save(
            [el("heading", text="مشخصات"), el("divider")],
            doc=self.form,
            form_settings={"orientation": "landscape"},
        )
        finalize(self.form)
        revision = services.create_revision(user=self.author, document_id=self.form.pk)
        self.assertEqual(revision.body_kind, BodyKind.FORM)
        self.assertEqual(revision.form_settings["orientation"], "landscape")
        copied = list(revision.sections.order_by("position").values_list("type", "content"))
        self.assertEqual([c["kind"] for _, c in copied], ["heading", "divider"])
        self.assertTrue(all(t == FORM for t, _ in copied))

    def test_a_revision_of_an_old_form_keeps_its_blocks(self):
        # A فرم made before Phase 11 (or imported) has a block body; so do its revisions.
        old = new_doc(self.author, "فرم قدیمی", DocumentGroup.FORM)
        type(old).objects.filter(pk=old.pk).update(body_kind=BodyKind.BLOCKS, form_settings={})
        old.refresh_from_db()
        self.save([short("خط")], doc=old)
        finalize(old)
        revision = services.create_revision(user=self.author, document_id=old.pk)
        self.assertEqual(revision.body_kind, BodyKind.BLOCKS)


class FormSchemaTests(SimpleTestCase):
    def test_every_kind_has_complete_defaults(self):
        for kind in form_schema.ELEMENTS:
            with self.subTest(kind=kind):
                cleaned = form_schema.clean_element({"kind": kind}, number=1)
                self.assertEqual(cleaned["kind"], kind)
                # Cleaning the cleaned form changes nothing (stored data is stable).
                self.assertEqual(form_schema.clean_element(cleaned, number=1), cleaned)

    def test_numbers_are_numbers_not_booleans_or_strings(self):
        for value in (True, "3", None):
            with self.subTest(value=value):
                with self.assertRaises(form_schema.FormSchemaError):
                    form_schema.clean_element({"kind": "spacer", "height": value}, number=1)

    def test_heading_level_must_be_an_integer(self):
        with self.assertRaises(form_schema.FormSchemaError):
            form_schema.clean_element({"kind": "heading", "level": 1.5}, number=1)
        self.assertEqual(form_schema.clean_element({"kind": "heading", "level": 2.0}, number=1)["level"], 2)

    def test_a_non_dict_element_is_refused(self):
        with self.assertRaises(form_schema.FormSchemaError):
            form_schema.clean_element(["heading"], number=1)

    def test_default_settings(self):
        self.assertEqual(
            form_schema.default_settings(),
            {
                "v": 1,
                "orientation": "portrait",
                "base_font_size": 10,
                "approval_strip": True,
                "header": {"subtitle": "", "show_company_name": True, "show_letter_box": False},
            },
        )


class InputElementSchemaTests(SimpleTestCase):
    def clean(self, raw):
        return form_schema.clean_element(raw, number=4)

    def messages(self, raw):
        with self.assertRaises(form_schema.FormSchemaError) as caught:
            self.clean(raw)
        return caught.exception.messages

    def test_fields_default_to_a_name_row(self):
        fields = self.clean({"kind": "fields"})
        self.assertEqual([c["label"] for c in fields["rows"][0]["cells"]], ["نام", "نام خانوادگی"])
        self.assertEqual(fields["blank"], "underline")
        self.assertFalse(fields["photo"])

    def test_a_row_must_add_up_to_100(self):
        row = {"cells": [{"label": "الف", "width": 30}, {"label": "ب", "width": 30}]}
        [message] = self.messages({"kind": "fields", "rows": [row]})
        self.assertIn("جزء ۴ (فیلدها) — ردیف ۱", message)
        self.assertIn("۱۰۰ درصد", message)
        row["cells"][1]["width"] = 70.4  # within the tolerance
        self.clean({"kind": "fields", "rows": [row]})

    def test_nested_problems_name_their_cell(self):
        rows = [{"cells": [{"label": "x", "width": 100, "type": "passport"}]}]
        [message] = self.messages({"kind": "fields", "rows": rows})
        self.assertIn("ردیف ۱ — خانه ۱", message)
        self.assertIn("نوع خانه", message)

    def test_field_caps(self):
        too_many_cells = [{"cells": [{"label": "", "width": 100 / 7}] * 7}]
        self.assertTrue(self.messages({"kind": "fields", "rows": too_many_cells}))
        self.assertTrue(self.messages({"kind": "fields", "rows": []}))  # at least one row
        narrow = [{"cells": [{"label": "", "width": 2}, {"label": "", "width": 98}]}]
        self.assertTrue(self.messages({"kind": "fields", "rows": narrow}))

    def test_signatures_hold_one_to_four_boxes(self):
        self.assertEqual(len(self.clean({"kind": "signatures"})["boxes"]), 1)
        self.assertTrue(self.messages({"kind": "signatures", "boxes": []}))
        self.assertTrue(self.messages({"kind": "signatures", "boxes": [{"caption": "x"}] * 5}))
        box = self.clean({"kind": "signatures", "boxes": [{"caption": "مدیر"}]})["boxes"][0]
        self.assertEqual(box, {"caption": "مدیر", "name_line": True, "date_line": True})

    def test_answer_box_ranges(self):
        self.assertEqual(self.clean({"kind": "answer_box"})["lines"], 4)
        self.assertTrue(self.messages({"kind": "answer_box", "lines": 26}))
        self.assertTrue(self.messages({"kind": "answer_box", "lines": 2.5}))
        self.assertTrue(self.messages({"kind": "answer_box", "height": 500}))


class TableSchemaTests(SimpleTestCase):
    def clean(self, raw):
        return form_schema.clean_element({"kind": "table", **raw}, number=2)

    def messages(self, raw):
        with self.assertRaises(form_schema.FormSchemaError) as caught:
            self.clean(raw)
        return caught.exception.messages

    def test_a_default_table(self):
        table = self.clean({})
        self.assertEqual([c["type"] for c in table["columns"]], ["row_number", "text", "text"])
        self.assertEqual(table["header"], [["ردیف", "عنوان", "توضیحات"]])
        self.assertEqual(table["blank_rows"], 5)

    def test_rows_must_match_the_columns(self):
        columns = [{"width": 50}, {"width": 50}]
        [message] = self.messages({"columns": columns, "header": [["الف", "ب"]], "rows": [["فقط یکی"]]})
        self.assertIn("ردیف‌های متن‌دار — ردیف ۱", message)
        self.assertIn("(۲)", message)
        self.assertTrue(self.messages({"columns": columns, "header": [["الف"]]}))

    def test_widths_and_column_caps(self):
        self.assertTrue(self.messages({"columns": [{"width": 50}, {"width": 20}], "header": [["", ""]]}))
        self.assertTrue(self.messages({"columns": [{"width": 3}, {"width": 97}], "header": [["", ""]]}))
        many = [{"width": 100 / 21}] * 21
        self.assertTrue(self.messages({"columns": many, "header": [[""] * 21]}))

    def test_header_rows_and_the_row_cap(self):
        columns = [{"width": 100}]
        self.assertTrue(self.messages({"columns": columns, "header": [[""]] * 4}))
        self.assertTrue(self.messages({"columns": columns, "header": []}))
        self.assertTrue(self.messages({"columns": columns, "header": [[""]], "rows": [[""]] * 200, "blank_rows": 101}))
        self.clean({"columns": columns, "header": [[""]], "rows": [[""]] * 200, "blank_rows": 100})

    def test_cells_are_text_of_bounded_length(self):
        columns = [{"width": 100}]
        self.assertTrue(self.messages({"columns": columns, "header": [[1]]}))
        self.assertTrue(self.messages({"columns": columns, "header": [[""]], "rows": [["ب" * 1001]]}))


class MergeSchemaTests(SimpleTestCase):
    BASE = {
        "kind": "table",
        "columns": [{"width": 25}, {"width": 25}, {"width": 50}],
        "header": [["الف", "ب", "ج"], ["", "", ""]],
        "rows": [["", "", ""], ["", "", ""]],
    }

    def clean(self, *merges):
        return form_schema.clean_element({**self.BASE, "merges": list(merges)}, number=1)

    def messages(self, *merges):
        with self.assertRaises(form_schema.FormSchemaError) as caught:
            self.clean(*merges)
        return caught.exception.messages

    def test_valid_merges(self):
        table = self.clean({"row": 0, "col": 1, "colspan": 2}, {"row": 0, "col": 0, "rowspan": 2}, {"row": 2, "col": 0, "rowspan": 2, "colspan": 3})
        self.assertEqual(len(table["merges"]), 3)
        self.assertEqual(table["merges"][0], {"row": 0, "col": 1, "rowspan": 1, "colspan": 2})
        self.assertEqual(form_schema.clean_element({"kind": "table"}, number=1)["merges"], [])

    def test_out_of_the_table(self):
        self.assertIn("بیرون", self.messages({"row": 3, "col": 0, "rowspan": 2})[0])
        self.assertIn("بیرون", self.messages({"row": 0, "col": 2, "colspan": 2})[0])
        self.assertTrue(self.messages({"row": 4, "col": 0, "colspan": 2}))  # blank rows cannot be merged

    def test_one_cell_is_not_a_merge(self):
        self.assertIn("دو خانه", self.messages({"row": 0, "col": 0})[0])

    def test_header_and_body_stay_apart(self):
        self.assertIn("سرستون", self.messages({"row": 1, "col": 0, "rowspan": 2})[0])

    def test_overlaps_are_refused_naming_the_other_merge(self):
        [message] = self.messages({"row": 0, "col": 0, "colspan": 2}, {"row": 0, "col": 1, "rowspan": 2})
        self.assertIn("ادغام ۲", message)
        self.assertIn("ادغام ۱", message)


class StoredElementTests(DesignerTestCase):
    """Elements saved before a property existed still load and print."""

    def test_an_old_table_gains_its_new_properties_when_read(self):
        form = new_doc(self.author, "فرم قدیمی‌تر", DocumentGroup.FORM)
        old = form_schema.clean_element({"kind": "table"}, number=1)
        del old["merges"]  # as stored before merged cells existed
        Section.objects.create(document=form, position=0, type=FORM, content=old)
        [table] = self.get_content(form)["sections"]
        self.assertEqual(table["merges"], [])

    def test_old_settings_gain_new_properties_when_read(self):
        form = new_doc(self.author, "فرم تنظیمات قدیمی", DocumentGroup.FORM)
        type(form).objects.filter(pk=form.pk).update(form_settings={"v": 1, "orientation": "landscape"})
        settings = self.get_content(form)["form_settings"]
        self.assertEqual(settings["orientation"], "landscape")
        self.assertTrue(settings["approval_strip"])
        self.assertEqual(settings["header"]["subtitle"], "")

    def test_content_that_breaks_newer_rules_is_shown_as_stored(self):
        form = new_doc(self.author, "فرم نامعتبر", DocumentGroup.FORM)
        broken = {"kind": "heading", "text": "x", "level": 9}
        Section.objects.create(document=form, position=0, type=FORM, content=broken)
        [heading] = self.get_content(form)["sections"]
        self.assertEqual(heading["level"], 9)
        self.assertEqual(form_schema.normalize_stored(broken), broken)
