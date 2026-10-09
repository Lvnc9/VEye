"""The compact form PDF (Phase 11, ADR-011): RTL wrapping, the renderer's page
furniture, the adapter, and building a form through the real task."""
import re
import shutil
import tempfile
from io import BytesIO
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import KeepTogether
from rest_framework.test import APIClient

from apps.core.constants import DocumentCategory, DocumentGroup, SectionType, SignOffRole
from apps.documents import form_schema
from apps.documents import services as document_services
from apps.documents.models import Section, SignOff
from apps.pdfgen import form_adapter, form_renderer, render, rtl, storage
from apps.pdfgen.models import PdfBuild, PdfKind, PdfStatus

from . import cases as C
from .helpers import LOCMEM_CACHE, fixture_bytes, make_author
from .test_pdf_api import eager

MEDIA = tempfile.mkdtemp(prefix="veye-formpdf-media-")


def tearDownModule():
    shutil.rmtree(MEDIA, ignore_errors=True)


def font(size=10):
    return rtl.Font(regular="Vazir", bold="Vazir-Bold", size=size)


def words(line):
    return "".join(text for text, _ in line).split()


def elements(*raw):
    return tuple(form_schema.clean_element(item, number=i + 1) for i, item in enumerate(raw))


def form_input(**overrides):
    values = dict(title="فرم درخواست", full_code="FR-01-01", revision="01", date="1405/07/04")
    values.update(overrides)
    return form_renderer.FormPdfInput(**values)


def page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type /Page\b", pdf))


class RecordingCanvas(Canvas):
    """Remembers every string drawn and where."""

    def __init__(self, *args, **kwargs):
        super().__init__(BytesIO(), *args, **kwargs)
        self.drawn = []

    def drawString(self, x, y, text, *args, **kwargs):
        self.drawn.append((x, y, text))
        super().drawString(x, y, text, *args, **kwargs)

    def drawCentredString(self, x, y, text, *args, **kwargs):
        self.drawn.append((x, y, text))
        super().drawCentredString(x, y, text, *args, **kwargs)

    def texts(self):
        return [text for _, _, text in self.drawn]


class WrapTests(SimpleTestCase):
    """Wrap first, in logical order; shape and reorder each line afterwards."""

    SENTENCE = "یک دو سه چهار پنج شش هفت هشت نه ده یازده دوازده سیزده چهارده پانزده"

    def test_lines_come_out_in_reading_order(self):
        lines = rtl.wrap(self.SENTENCE, font(), 80)
        self.assertGreater(len(lines), 2)
        # Concatenating the lines gives the sentence back, word for word, in order —
        # wrapping an already reordered paragraph would give the last words first.
        self.assertEqual([w for line in lines for w in words(line)], self.SENTENCE.split())
        self.assertEqual(words(lines[0])[0], "یک")

    def test_every_line_fits(self):
        for width in (40, 80, 200):
            with self.subTest(width=width):
                for line in rtl.wrap(self.SENTENCE, font(), width):
                    self.assertLessEqual(rtl.line_width(line, font()), width + 0.01)

    def test_no_space_at_either_end_of_a_line(self):
        for line in rtl.wrap(self.SENTENCE, font(), 70):
            text = "".join(t for t, _ in line)
            self.assertEqual(text, text.strip())

    def test_hard_breaks_and_empty_paragraphs_are_kept(self):
        lines = rtl.wrap("اول\n\nسوم", font(), 500)
        self.assertEqual([words(line) for line in lines], [["اول"], [], ["سوم"]])

    def test_a_word_longer_than_the_line_is_cut_not_overflowing(self):
        long_word = "الف" * 40
        lines = rtl.wrap(long_word, font(), 60)
        self.assertGreater(len(lines), 1)
        self.assertEqual("".join("".join(t for t, _ in line) for line in lines), long_word)
        for line in lines:
            self.assertLessEqual(rtl.line_width(line, font()), 60.01)

    def test_markers_become_styles_and_neighbours_merge(self):
        [line] = rtl.wrap("این **مهم** است و ~~کج~~ و --خط--", font(), 1000)
        self.assertEqual(
            line,
            [("این ", rtl.NORMAL), ("مهم", rtl.BOLD), (" است و ", rtl.NORMAL), ("کج", rtl.ITALIC),
             (" و ", rtl.NORMAL), ("خط", rtl.UNDERLINE)],
        )

    def test_bold_option_sets_unmarked_text_bold(self):
        [line] = rtl.wrap("عنوان ~~کج~~", font(), 1000, bold=True)
        self.assertEqual(line, [("عنوان ", rtl.BOLD), ("کج", rtl.ITALIC)])

    def test_the_first_run_is_drawn_rightmost(self):
        canvas = RecordingCanvas()
        rtl.draw_line(canvas, [("اول ", rtl.NORMAL), ("دوم", rtl.BOLD)], font(), x_right=300, y=100)
        (x_first, _, first), (x_second, _, second) = canvas.drawn
        self.assertEqual(first, rtl.shape("اول "))
        self.assertGreater(x_first, x_second)
        # Flush right: the first run ends exactly at x_right.
        self.assertAlmostEqual(x_first + canvas.stringWidth(first, "Vazir", 10), 300, places=3)


class NumberingTests(SimpleTestCase):
    def test_levels_count_and_reset(self):
        numbering = form_renderer._Numbering()
        self.assertEqual(
            [numbering.next(level) for level in (1, 2, 2, 1, 2, 3, 1)],
            ["1. ", "1.1. ", "1.2. ", "2. ", "2.1. ", "2.1.1. ", "3. "],
        )

    def test_the_separator_keeps_digits_in_order_after_bidi(self):
        # «2.1» must not come out as «1.2»: a "-" there would (see _Numbering).
        self.assertIn("2.1", rtl.shape("2.1. مقطع"))


class FurnitureTests(SimpleTestCase):
    def test_the_header_names_the_sheet(self):
        canvas = RecordingCanvas(pagesize=A4)
        data = form_input(obsolete=True, company_name="شرکت نمونه", subtitle="منابع انسانی")
        form_renderer._draw_header(canvas, data, 2, 3)
        texts = canvas.texts()
        for expected in (
            "صفحه 2 از 3",
            "کد: FR-01-01",
            "بازنگری: 01",
            "تاریخ: 1405/07/04",
            "فرم درخواست",
            "شرکت نمونه",
            "منابع انسانی",
        ):
            self.assertIn(rtl.shape(expected), texts, expected)

    def test_the_header_never_prints_a_validity_line(self):
        # 2026-09-30: a superseded revision is marked by the «منسوخ» watermark, not by a «وضعیت» row.
        for data in (form_input(), form_input(obsolete=True)):
            canvas = RecordingCanvas(pagesize=A4)
            form_renderer._draw_header(canvas, data, 1, 1)
            self.assertFalse(any("وضعیت" in text or rtl.shape("وضعیت") in text for text in canvas.texts()))

    def test_the_footer_prints_both_footnotes(self):
        canvas = RecordingCanvas(pagesize=A4)
        form_renderer._draw_footer(canvas, form_input(footnote1="بالا", footnote2="پایین"))
        self.assertEqual(canvas.texts(), [rtl.shape("بالا"), rtl.shape("پایین")])


@override_settings(FRONTEND_BASE_URL=C.FRONTEND)
class RenderTests(SimpleTestCase):
    def test_a_page_break_makes_two_pages_and_every_page_is_numbered(self):
        data = form_input(elements=elements({"kind": "heading", "text": "یک"}, {"kind": "page_break"},
                                            {"kind": "heading", "text": "دو"}))
        with mock.patch.object(form_renderer, "_draw_header", wraps=form_renderer._draw_header) as header:
            pdf = form_renderer.render(data)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertEqual(page_count(pdf), 2)
        self.assertEqual([call.args[2:] for call in header.call_args_list], [(1, 2), (2, 2)])

    def test_a_page_break_at_the_top_of_a_page_adds_no_blank_page(self):
        self.assertEqual(page_count(form_renderer.render(form_input(elements=elements({"kind": "page_break"})))), 1)

    def test_an_empty_form_still_prints_one_page(self):
        self.assertEqual(page_count(form_renderer.render(form_input())), 1)

    def test_landscape(self):
        for orientation, expected in (("landscape", landscape(A4)), ("portrait", A4)):
            with self.subTest(orientation=orientation):
                pdf = form_renderer.render(form_input(orientation=orientation))
                box = re.search(rb"/MediaBox \[ 0 0 ([\d.]+) ([\d.]+) \]", pdf)
                self.assertAlmostEqual(float(box.group(1)), expected[0], places=2)
                self.assertAlmostEqual(float(box.group(2)), expected[1], places=2)

    def test_the_watermark_is_on_every_preview_page_only(self):
        data = form_input(elements=elements({"kind": "spacer"}, {"kind": "page_break"}, {"kind": "spacer"}))
        with mock.patch.object(form_renderer, "_draw_watermark") as watermark:
            form_renderer.render(data)
            self.assertEqual(watermark.call_count, 0)
            form_renderer.render(data, preview=True)
            self.assertEqual(watermark.call_count, 2)

    def test_long_text_flows_onto_the_next_page(self):
        long_text = "سطر\n" * 1200
        pdf = form_renderer.render(form_input(elements=elements({"kind": "text", "text": long_text, "boxed": True})))
        self.assertGreater(page_count(pdf), 1)

    def test_invariant_output_is_reproducible(self):
        data = form_input(elements=elements({"kind": "heading", "text": "ثابت"}))
        self.assertEqual(form_renderer.render(data, invariant=True), form_renderer.render(data, invariant=True))

    def test_the_approval_strip_puts_the_author_on_the_right(self):
        signers = (form_renderer.Signer("تدوین کننده", "الف"), form_renderer.Signer("تایید کننده", "ب"),
                   form_renderer.Signer("تصویب کننده", "ج"))
        [_, anchored] = form_renderer._approval_strip(form_input(signers=signers), 500)
        table = anchored.content
        first_row = [unwrap(cell).text for cell in table._cellvalues[0]]
        self.assertEqual(first_row, ["تصویب کننده:", "تایید کننده:", "تدوین کننده:"])

    def test_empty_headings_and_text_print_nothing(self):
        flowables = form_renderer.story(
            form_input(elements=elements({"kind": "heading", "text": "  "}, {"kind": "text", "text": ""})), 500
        )
        self.assertEqual(flowables, [])

    def test_an_unknown_kind_is_skipped(self):
        data = form_input(elements=({"kind": "from-the-future"},))
        self.assertEqual(form_renderer.story(data, 500), [])


@override_settings(MEDIA_ROOT=MEDIA, FRONTEND_BASE_URL=C.FRONTEND, CACHES=LOCMEM_CACHE)
class FormBuildTests(TestCase):
    def setUp(self):
        self.user = make_author()
        self.form = document_services.create_document(
            user=self.user, category=DocumentCategory.INSIDE, title="فرم استخدام", group=DocumentGroup.FORM
        )
        for position, element in enumerate(elements({"kind": "heading", "text": "مشخصات"}, {"kind": "divider"})):
            Section.objects.create(document=self.form, position=position, type=SectionType.FORM_ELEMENT, content=element)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_the_adapter_reads_the_form(self):
        SignOff.objects.create(
            document=self.form, role=SignOffRole.CREATER, name="نویسنده", position="کارشناس",
            signature=None, signed_date="2026-09-26",
        )
        data = form_adapter.load(self.form.pk)
        self.assertEqual(data.full_code, "FR-01-01")
        self.assertEqual([e["kind"] for e in data.elements], ["heading", "divider"])
        self.assertEqual([s.role_label for s in data.signers], ["تهیه کننده", "تایید کننده", "تصویب کننده"])
        self.assertEqual(data.signers[0].name, "نویسنده")
        self.assertEqual(data.signers[0].date, "1405/07/04")
        self.assertFalse(data.obsolete)  # a draft is not superseded
        self.assertIsNotNone(data.qr)
        self.assertEqual(data.orientation, "portrait")

    def test_the_header_settings_reach_the_pdf(self):
        self.form.form_settings = form_schema.clean_settings(
            {"header": {"subtitle": "واحد منابع انسانی", "show_company_name": False, "show_letter_box": True}}
        )
        self.form.save()
        data = form_adapter.load(self.form.pk)
        self.assertEqual(data.subtitle, "واحد منابع انسانی")
        self.assertEqual(data.company_name, "")
        self.assertTrue(data.show_letter_box)

    def test_a_logo_is_read(self):
        from django.core.files.base import ContentFile

        self.form.logo.save("logo.png", ContentFile(fixture_bytes("logo.png")))
        self.assertIsNotNone(form_adapter.load(self.form.pk).logo)

    def test_the_dispatch_picks_the_renderer_by_body_kind(self):
        with mock.patch.object(render.form_renderer, "render", return_value=b"form") as form_render, \
                mock.patch.object(render.provider, "deliver_to_pdf", return_value=b"blocks") as block_render:
            self.assertEqual(render.render(self.form.pk, preview=False), b"form")
            poster = document_services.create_document(
                user=self.user, category=DocumentCategory.INSIDE, title="پوستر", group=DocumentGroup.POSTER
            )
            self.assertEqual(render.render(poster.pk, preview=True), b"blocks")
        self.assertEqual(form_render.call_count, 1)
        self.assertEqual(block_render.call_args.kwargs, {"preview": True})

    def test_a_preview_builds_through_the_real_task(self):
        with eager(), self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("pdf-build", kwargs={"document_id": self.form.pk, "kind": "preview"}))
        self.assertEqual(response.status_code, 202)
        build = PdfBuild.objects.get(document=self.form, kind=PdfKind.PREVIEW)
        self.assertEqual(build.status, PdfStatus.READY, build.error)
        pdf = storage.absolute_path(build.path).read_bytes()
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertEqual(page_count(pdf), 1)


class InputElementTests(SimpleTestCase):
    def fields(self, rows, **extra):
        return form_schema.clean_element({"kind": "fields", "rows": rows, **extra}, number=1)

    def row(self, *labels):
        width = 100 / len(labels)
        return {"cells": [{"label": label, "width": width} for label in labels]}

    def test_the_first_field_is_drawn_on_the_right(self):
        element = self.fields([self.row("اول", "دوم")])
        grid = form_renderer.FieldGrid(element, 10)
        canvas = RecordingCanvas(pagesize=A4)
        grid.wrap(400, 800)
        grid.drawOn(canvas, 0, 0)
        x = {text: left for left, _, text in canvas.drawn}
        self.assertGreater(x[rtl.shape("اول:")], x[rtl.shape("دوم:")])

    def test_a_checkbox_has_no_colon(self):
        element = self.fields([{"cells": [{"label": "متأهل", "type": "checkbox", "width": 100}]}])
        canvas = RecordingCanvas(pagesize=A4)
        grid = form_renderer.FieldGrid(element, 10)
        grid.wrap(400, 800)
        grid.drawOn(canvas, 0, 0)
        self.assertEqual(canvas.texts(), [rtl.shape("متأهل")])

    def test_the_grid_splits_between_rows(self):
        element = self.fields([self.row(str(i)) for i in range(10)], row_height=10)
        grid = form_renderer.FieldGrid(element, 10)
        first, rest = grid.split(400, 45 * form_renderer.mm)
        self.assertEqual(len(first.rows), 4)
        self.assertEqual(len(rest.rows), 6)

    def test_the_photo_stays_with_rows_tall_enough_for_it(self):
        element = self.fields([self.row(str(i)) for i in range(10)], row_height=10, photo=True)
        grid = form_renderer.FieldGrid(element, 10)
        self.assertEqual(grid.split(400, 30 * form_renderer.mm), [])  # the photo would not fit: move on
        first, rest = grid.split(400, 60 * form_renderer.mm)
        self.assertTrue(first.photo)
        self.assertFalse(rest.photo)
        # With fewer rows than the photo is tall, the photo sets the height.
        short = form_renderer.FieldGrid(self.fields([self.row("x")], row_height=9, photo=True), 10)
        _, height = short.wrap(400, 800)
        self.assertGreater(height, form_renderer.PHOTO_HEIGHT * form_renderer.mm)

    def test_an_answer_box_never_outgrows_the_page(self):
        element = form_schema.clean_element({"kind": "answer_box", "lines": 0, "height": 200}, number=1)
        box = form_renderer.AnswerBox(element, 10, max_height=120 * form_renderer.mm)
        _, height = box.wrap(400, 1000)
        self.assertLessEqual(height, 120 * form_renderer.mm)

    def test_signature_boxes_run_right_to_left_then_the_stamp(self):
        element = form_schema.clean_element(
            {"kind": "signatures", "boxes": [{"caption": "متقاضی"}, {"caption": "بررسی"}], "stamp": True}, number=1
        )
        row = form_renderer.SignatureRow(element, 10)
        canvas = RecordingCanvas(pagesize=A4)
        row.wrap(500, 800)
        row.drawOn(canvas, 0, 0)
        x = {text: left for left, _, text in canvas.drawn}
        self.assertGreater(x[rtl.shape("متقاضی")], x[rtl.shape("بررسی")])
        self.assertGreater(x[rtl.shape("بررسی")], x[rtl.shape("محل مهر")])

    def test_a_full_hiring_form_renders_in_landscape_too(self):
        items = elements(
            {"kind": "fields", "photo": True, "rows": [
                {"cells": [{"label": "نام", "width": 50}, {"label": "تاریخ تولد", "type": "date", "width": 50}]},
                {"cells": [{"label": "کد ملی", "type": "national_code", "width": 60},
                           {"label": "همراه", "type": "phone", "width": 40}]},
            ]},
            {"kind": "answer_box", "label": "توضیحات", "lines": 0, "height": 200},
            {"kind": "signatures", "stamp": True},
        )
        for orientation in ("portrait", "landscape"):
            with self.subTest(orientation=orientation):
                pdf = form_renderer.render(form_input(orientation=orientation, elements=items))
                self.assertTrue(pdf.startswith(b"%PDF-"))


class TableTests(SimpleTestCase):
    def table(self, **raw):
        element = form_schema.clean_element({"kind": "table", **raw}, number=1)
        flowables = form_renderer._table(element, form_input(), form_renderer._Numbering())
        return [f for f in flowables if isinstance(f, form_renderer._TableFlowable)][0]

    def texts(self, row):
        return [getattr(cell, "text", None) for cell in row]

    def test_column_one_is_on_the_right(self):
        flowable = self.table(
            columns=[{"width": 20}, {"width": 30}, {"width": 50}], header=[["اول", "دوم", "سوم"]], blank_rows=0
        )
        flowable.wrap(500, 800)
        platypus = flowable._table
        self.assertEqual(self.texts(platypus._cellvalues[0]), ["سوم", "دوم", "اول"])
        self.assertEqual([round(w) for w in platypus._colWidths], [250, 150, 100])

    def test_body_rows_are_numbered_and_blank_rows_keep_their_height(self):
        flowable = self.table(row_height=10)
        flowable.wrap(500, 800)
        platypus = flowable._table
        self.assertEqual(len(platypus._cellvalues), 1 + 5)
        # «ردیف» is column 1, so the last one after reversal.
        self.assertEqual([row[-1].text for row in platypus._cellvalues[1:]], ["1", "2", "3", "4", "5"])
        for height in platypus._argH[1:]:
            self.assertAlmostEqual(height, 10 * form_renderer.mm)

    def test_long_text_grows_its_row(self):
        flowable = self.table(columns=[{"width": 100}], header=[["متن"]], rows=[["کلمه " * 80]], blank_rows=0, row_height=8)
        flowable.wrap(300, 800)
        self.assertGreater(flowable._table._argH[1], 8 * form_renderer.mm * 2)

    def test_checkbox_and_date_columns_draw_their_blanks(self):
        flowable = self.table(
            columns=[{"width": 50, "type": "checkbox"}, {"width": 50, "type": "date"}], header=[["تأیید", "تاریخ"]], blank_rows=1
        )
        flowable.wrap(500, 800)
        date_cell, check_cell = flowable._table._cellvalues[1]
        self.assertIsInstance(check_cell, form_renderer.CheckCell)
        self.assertIsInstance(date_cell, form_renderer.DateCell)

    def test_the_header_repeats_only_when_asked(self):
        self.table().wrap(500, 800)
        for repeat, expected in ((True, 2), (False, 0)):
            flowable = self.table(header=[["", "", ""], ["ردیف", "عنوان", "توضیحات"]], repeat_header=repeat)
            flowable.wrap(500, 800)
            self.assertEqual(flowable._table.repeatRows, expected)

    def test_a_long_table_flows_onto_more_pages_with_its_header(self):
        items = elements({"kind": "table", "blank_rows": 120})
        pdf = form_renderer.render(form_input(elements=items))
        self.assertGreaterEqual(page_count(pdf), 3)

    def test_the_title_stays_with_the_table(self):
        element = form_schema.clean_element({"kind": "table", "title": "سوابق"}, number=1)
        title = form_renderer._table(element, form_input(), form_renderer._Numbering())[0]
        self.assertTrue(title.keepWithNext)


class MergedCellTests(SimpleTestCase):
    def built(self, **raw):
        element = form_schema.clean_element({"kind": "table", "blank_rows": 1, **raw}, number=1)
        flowable = [f for f in form_renderer._table(element, form_input(), form_renderer._Numbering())
                    if isinstance(f, form_renderer._TableFlowable)][0]
        flowable.wrap(400, 800)
        return flowable._table

    def spans(self, table):
        return [(cmd[1], cmd[2]) for cmd in table._spanCmds]

    def test_a_logical_range_becomes_the_mirrored_platypus_span(self):
        table = self.built(
            columns=[{"width": 25}, {"width": 25}, {"width": 50}],
            header=[["الف", "مدت", ""]],
            merges=[{"row": 0, "col": 1, "colspan": 2}],
        )
        # Logical columns 1-2 (0-based) are platypus columns 0-1.
        self.assertEqual(self.spans(table), [((0, 0), (1, 0))])
        # The text moves to the span's first platypus cell, which platypus draws.
        self.assertEqual(table._cellvalues[0][0].text, "مدت")
        self.assertEqual(table._cellvalues[0][2].text, "الف")

    def test_a_tall_merged_cell_grows_its_rows(self):
        text = "کلمه " * 60
        plain = self.built(columns=[{"width": 50}, {"width": 50}], header=[["", ""]], rows=[[text, ""], ["", ""]], row_height=5)
        merged = self.built(
            columns=[{"width": 50}, {"width": 50}], header=[["", ""]], rows=[[text, ""], ["", ""]], row_height=5,
            merges=[{"row": 1, "col": 0, "rowspan": 2}],
        )
        # The two spanned rows together are exactly as tall as the text needs —
        # the same height as the unmerged row that holds it, no taller.
        self.assertAlmostEqual(sum(merged._argH[1:3]), plain._argH[1], delta=0.5)

    def test_a_table_with_merges_renders(self):
        items = elements({
            "kind": "table",
            "columns": [{"width": 10, "type": "row_number"}, {"width": 45}, {"width": 45}],
            "header": [["ردیف", "مدت همکاری", ""], ["", "از", "تا"]],
            "merges": [{"row": 0, "col": 1, "colspan": 2}, {"row": 0, "col": 0, "rowspan": 2}],
            "blank_rows": 60,
        })
        pdf = form_renderer.render(form_input(elements=items))
        self.assertGreaterEqual(page_count(pdf), 2)  # a spanned, repeated header across pages


@override_settings(MEDIA_ROOT=MEDIA, FRONTEND_BASE_URL=C.FRONTEND, CACHES=LOCMEM_CACHE)
class StoredElementPdfTests(TestCase):
    def test_a_table_saved_before_merges_still_prints(self):
        user = make_author()
        form = document_services.create_document(
            user=user, category=DocumentCategory.INSIDE, title="فرم قدیمی", group=DocumentGroup.FORM
        )
        old = form_schema.clean_element({"kind": "table"}, number=1)
        del old["merges"]
        Section.objects.create(document=form, position=0, type=SectionType.FORM_ELEMENT, content=old)
        data = form_adapter.load(form.pk)
        self.assertEqual(data.elements[0]["merges"], [])
        self.assertTrue(form_renderer.render(data).startswith(b"%PDF-"))


class QuestionElementTests(SimpleTestCase):
    def group(self, **raw):
        element = form_schema.clean_element({"kind": "choices", **raw}, number=1)
        group = form_renderer.ChoiceGroup(element, 10)
        group.wrap(300, 800)
        return group

    def test_inline_options_run_right_to_left_and_wrap(self):
        group = self.group(label="وضعیت", options=["اول", "دوم"])
        (line1, x1, _, _), (line2, x2, _, _) = group._placed
        self.assertEqual((line1, line2), (0, 0))
        self.assertGreater(x1, x2)
        many = self.group(label="بلند", options=[f"گزینهٔ شمارهٔ {i}" for i in range(12)])
        self.assertGreater(max(line for line, *_ in many._placed), 0)
        for line, x_right, text, _ in many._placed:
            self.assertGreaterEqual(x_right - many._option_width(text, False), -0.01)

    def test_columns_fill_right_to_left_then_down(self):
        group = self.group(label="", options=["الف", "ب", "ج"], layout="columns", columns=2)
        (l1, x1, _, _), (l2, x2, _, _), (l3, x3, _, _) = group._placed
        self.assertEqual((l1, l2, l3), (0, 0, 1))
        self.assertGreater(x1, x2)
        self.assertEqual(x3, x1)

    def test_vertical_with_other(self):
        group = self.group(label="سؤال", options=["الف", "ب"], layout="vertical", other=True)
        self.assertEqual([line for line, *_ in group._placed], [1, 2, 3])
        self.assertTrue(group._placed[-1][3])  # «سایر» comes last

    def test_the_matrix_puts_the_items_on_the_right(self):
        element = form_schema.clean_element({"kind": "matrix", "comment": True}, number=1)
        flowable = form_renderer.MatrixFlowable(element, form_input())
        flowable.wrap(500, 800)
        header = flowable._table._cellvalues[0]
        self.assertEqual(header[-1].text, "شرح")
        self.assertEqual(header[0].text, "توضیحات")
        self.assertEqual(flowable._table.repeatRows, 1)
        self.assertIsInstance(flowable._table._cellvalues[1][1], form_renderer.CheckCell)

    def test_a_question_stays_with_its_answer(self):
        element = form_schema.clean_element(
            {"kind": "questions", "items": [{"text": "چرا؟", "answer": "lines", "lines": 3}, {"text": "بله؟", "answer": "yes_no"}]},
            number=1,
        )
        flowables = form_renderer._questions(element, form_input(), form_renderer._Numbering(), 200 * form_renderer.mm)
        keeps = [f for f in flowables if isinstance(f, KeepTogether)]
        self.assertEqual(len(keeps), 2)
        self.assertEqual(keeps[0]._content[0].text, "1. چرا؟")
        self.assertIsInstance(keeps[1]._content[1], form_renderer.ChoiceGroup)

    def test_a_questionnaire_renders(self):
        items = elements(
            {"kind": "choices", "label": "x", "options": ["a", "b"], "other": True},
            {"kind": "matrix", "items": [f"مورد {i}" for i in range(40)]},
            {"kind": "questions", "items": [{"text": "پرسش", "answer": "box", "height": 150}] * 5},
        )
        for orientation in ("portrait", "landscape"):
            with self.subTest(orientation=orientation):
                self.assertTrue(form_renderer.render(form_input(orientation=orientation, elements=items)).startswith(b"%PDF-"))


def unwrap(cell):
    """The flowable of a table cell (ReportLab wraps it in a tuple once the table has been measured)."""
    while isinstance(cell, (tuple, list)):
        cell = cell[0]
    return cell


class ApprovalStripTests(SimpleTestCase):
    """The strip that closes a فرم (owner's request, 2026-09-30): role, سمت, name, signature."""

    SIGNERS = (
        form_renderer.Signer("تهیه کننده", "علی رضایی", "مدیر واحد", "1405/07/04", fixture_bytes("sign_creater.png")),
        form_renderer.Signer("تایید کننده", "سارا احمدی", "معاون", "", None),
        form_renderer.Signer("تصویب کننده", "", "", "", fixture_bytes("sign_creater.png")),
    )

    def table(self, signers=None):
        [_, anchored] = form_renderer._approval_strip(form_input(signers=signers or self.SIGNERS), 500)
        return anchored.content

    def test_each_column_stacks_role_then_post_then_name_then_signature(self):
        table = self.table()
        rightmost = [unwrap(row[-1]) for row in table._cellvalues]  # a table lays out left to right: the author is last
        self.assertEqual(rightmost[0].text, "تهیه کننده:")
        # a signed step prints its values alone — «مدیر واحد», not «سمت: مدیر واحد»
        self.assertEqual(rightmost[1].text, "مدیر واحد")
        self.assertEqual(rightmost[2].text, "علی رضایی")
        self.assertIsInstance(rightmost[3], form_renderer._SignatureCell)
        self.assertIsNotNone(rightmost[3].reader)
        self.assertIsNone(unwrap(self.table()._cellvalues[3][1]).reader, "an unsigned column keeps its «امضا:» placeholder")

    def test_only_the_role_titles_sit_four_spaces_to_the_right(self):
        table = self.table()
        space = form_renderer._fonts(form_input().base_font_size).width(" ", form_renderer.rtl.BOLD)
        for cell in table._cellvalues[0]:
            self.assertAlmostEqual(unwrap(cell).shift, 4 * space, places=1)
        for row in table._cellvalues[1:3]:
            for cell in row:
                self.assertEqual(unwrap(cell).shift, 0.0, "سمت and name stay where they were")

    def test_no_date_is_printed(self):
        table = self.table()
        texts = [getattr(unwrap(cell), "text", "") for row in table._cellvalues for cell in row]
        self.assertFalse(any("1405/07/04" in text or "تاریخ" in text for text in texts))
        self.assertEqual(len(table._cellvalues), 4)

    def test_an_unnamed_role_still_shows_its_labels(self):
        left = [unwrap(row[0]) for row in self.table()._cellvalues]  # the approver, leftmost
        self.assertIn("سمت تصویب کننده:", left[1].text)
        self.assertIn("نام و نام خانوادگی تصویب کننده:", left[2].text)

    def test_markers_in_a_name_are_not_styling(self):
        signers = (form_renderer.Signer("تهیه کننده", "**علی**--رضایی"),)
        [row] = [self.table(signers)._cellvalues[2]]
        self.assertEqual(unwrap(row[0]).text, "علیرضایی")

    def test_it_draws_no_grid_and_no_shading(self):
        style = [command[0] for command in self.table()._bkgrndcmds + self.table()._linecmds]
        self.assertEqual(style, [], "plain text, not a boxed table (owner, 2026-10-01)")

    def test_it_is_a_conditional_break_then_a_bottom_anchored_table(self):
        [before, anchored] = form_renderer._approval_strip(form_input(signers=self.SIGNERS), 500)
        self.assertIsInstance(before, form_renderer.CondPageBreak)
        self.assertIsInstance(anchored, form_renderer._BottomAnchored)


def _build(flowables, *, width=500, height=200 * mm):
    """Lay flowables out in a frame of `height`; returns (pages, y of each anchored strip)."""
    from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate

    seen = []
    real = form_renderer._BottomAnchored.draw

    def record(self):
        seen.append(self.canv._currentMatrix[5])
        return real(self)

    doc = BaseDocTemplate(BytesIO(), pagesize=A4)
    doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(20 * mm, 30 * mm, width, height, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)])])
    with mock.patch.object(form_renderer._BottomAnchored, "draw", record):
        doc.build(flowables)
    return doc.page, seen


class StripPositionTests(SimpleTestCase):
    def strip(self):
        return form_renderer._approval_strip(form_input(signers=ApprovalStripTests.SIGNERS), 500)

    def test_the_strip_is_pinned_to_the_bottom_of_the_frame(self):
        pages, seen = _build([form_renderer.Spacer(1, 10 * mm)] + self.strip())
        self.assertEqual(pages, 1)
        self.assertAlmostEqual(seen[0], 30 * mm, places=2)  # the frame's bottom edge, not under the spacer

    def test_content_that_leaves_no_room_pushes_the_strip_to_a_new_page(self):
        pages, seen = _build([form_renderer.Spacer(1, 199 * mm)] + self.strip())
        self.assertEqual(pages, 2)
        self.assertEqual(len(seen), 1)
        self.assertAlmostEqual(seen[0], 30 * mm, places=2)

    def test_with_no_content_the_strip_still_prints_alone(self):
        pages, seen = _build(self.strip())
        self.assertEqual((pages, len(seen)), (1, 1))

    def test_render_puts_the_strip_on_the_last_page_only(self):
        with mock.patch.object(form_renderer._BottomAnchored, "draw", autospec=True, side_effect=form_renderer._BottomAnchored.draw) as draw:
            form_renderer.render(form_input(
                signers=ApprovalStripTests.SIGNERS,
                elements=elements({"kind": "spacer"}, {"kind": "page_break"}, {"kind": "spacer"}),
            ))
        self.assertEqual(draw.call_count, 1)


class ObsoleteWatermarkTests(SimpleTestCase):
    PAGES = elements({"kind": "spacer"}, {"kind": "page_break"}, {"kind": "spacer"})

    def marks(self, **kwargs):
        with mock.patch.object(form_renderer, "_draw_watermark") as watermark:
            form_renderer.render(form_input(elements=self.PAGES, **kwargs))
        return [call.args[1] for call in watermark.call_args_list]

    def test_an_obsolete_revision_is_marked_on_every_page(self):
        self.assertEqual(self.marks(obsolete=True), ["منسوخ", "منسوخ"])

    def test_a_current_revision_carries_no_mark(self):
        self.assertEqual(self.marks(), [])

    def test_obsolete_wins_over_preview(self):
        with mock.patch.object(form_renderer, "_draw_watermark") as watermark:
            form_renderer.render(form_input(elements=self.PAGES, obsolete=True), preview=True)
        self.assertEqual([call.args[1] for call in watermark.call_args_list], ["منسوخ", "منسوخ"])

    def test_a_preview_keeps_its_own_mark(self):
        with mock.patch.object(form_renderer, "_draw_watermark") as watermark:
            form_renderer.render(form_input(elements=self.PAGES), preview=True)
        self.assertEqual([call.args[1] for call in watermark.call_args_list], ["پیش نمایش", "پیش نمایش"])
