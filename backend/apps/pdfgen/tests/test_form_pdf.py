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
from reportlab.pdfgen.canvas import Canvas
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
        data = form_input(validation="معتبر", company_name="شرکت نمونه", subtitle="منابع انسانی")
        form_renderer._draw_header(canvas, data, 2, 3)
        texts = canvas.texts()
        for expected in (
            "صفحه 2 از 3",
            "کد: FR-01-01",
            "بازنگری: 01",
            "تاریخ: 1405/07/04",
            "وضعیت: معتبر",
            "فرم درخواست",
            "شرکت نمونه",
            "منابع انسانی",
        ):
            self.assertIn(rtl.shape(expected), texts, expected)

    def test_no_validity_line_before_control(self):
        canvas = RecordingCanvas(pagesize=A4)
        form_renderer._draw_header(canvas, form_input(), 1, 1)
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
        [_, keep] = form_renderer._approval_strip(form_input(signers=signers), 500)
        table = keep._content[0]
        first_row = [cell.text for cell in table._cellvalues[0]]
        self.assertEqual(first_row, ["تصویب کننده", "تایید کننده", "تدوین کننده"])

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
        self.assertEqual([s.role_label for s in data.signers], ["تدوین کننده", "تایید کننده", "تصویب کننده"])
        self.assertEqual(data.signers[0].name, "نویسنده")
        self.assertEqual(data.signers[0].date, "1405/07/04")
        self.assertEqual(data.validation, "")  # a draft claims no validity
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
