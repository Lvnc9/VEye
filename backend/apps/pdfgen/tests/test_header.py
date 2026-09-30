"""The boxed page header (header.py) — the owner's redesign of 2026-09-29, drawn
the same on every page. The goldens pin the bytes; these say what it is."""
import re
from io import BytesIO
from unittest import mock

from django.test import SimpleTestCase
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

from apps.pdfgen import header, provider, renderer, rtl
from apps.pdfgen.provider import PdfInput

from .helpers import fixture_bytes
from .test_form_pdf import RecordingCanvas

X0, X1, TOP = 40.0, A4[0] - 40.0, A4[1] - 40.0
ROWS = header.meta_rows("PR-01-02", "02", "1405/07/07")


def draw(canvas=None, *, title="روش اجرایی", rows=ROWS, logo=None, company_name=""):
    canvas = canvas or RecordingCanvas(pagesize=A4)
    header.draw_boxed_header(
        canvas, title=title, rows=rows, logo=logo, font_name="Vazir", x0=X0, x1=X1, top=TOP, company_name=company_name
    )
    return canvas


def pages(pdf: bytes) -> int:
    return len(re.findall(rb"/Type /Page\b", pdf))


class BoxedHeaderTests(SimpleTestCase):
    def test_the_left_cell_has_three_rows_label_then_value(self):
        canvas = draw()
        drawn = {text: (x, y) for x, y, text in canvas.drawn}
        for label, value in (("کد:", " PR-01-02"), ("شماره بازنگری:", " 02"), ("تاریخ:", " 1405/07/07")):
            self.assertIn(rtl.shape(label), drawn, label)
            self.assertIn(rtl.shape(value), drawn, value)
            # RTL: the label is the rightmost run and its value sits to its left.
            self.assertGreater(drawn[rtl.shape(label)][0], drawn[rtl.shape(value)][0])
            self.assertEqual(drawn[rtl.shape(label)][1], drawn[rtl.shape(value)][1])
        ys = [drawn[rtl.shape(label)][1] for label in ("کد:", "شماره بازنگری:", "تاریخ:")]
        self.assertEqual(sorted(ys, reverse=True), ys)  # top to bottom, evenly spaced
        self.assertAlmostEqual(ys[0] - ys[1], ys[1] - ys[2], places=3)
        # Right-aligned inside the left cell.
        self.assertLess(drawn[rtl.shape("کد:")][0], X0 + header.META_CELL)

    def test_the_title_sits_in_the_middle_cell(self):
        canvas = draw(title="عنوان")
        [(x, y, text)] = [d for d in canvas.drawn if d[2] == rtl.shape("عنوان")]
        width = canvas.stringWidth(text, "Vazir-Bold", header._TITLE_SIZES[0])
        left, right = X0 + header.META_CELL, X1 - header.LOGO_CELL
        self.assertGreaterEqual(x, left)
        self.assertLessEqual(x + width, right)
        self.assertAlmostEqual(x + width / 2, (left + right) / 2, delta=0.5)
        self.assertTrue(TOP - header.HEIGHT < y < TOP)

    def test_a_long_title_wraps_to_two_lines_and_keeps_every_word(self):
        title = "روش اجرایی کنترل مستندات و سوابق سازمان و یک عنوان بسیار طولانی برای آزمون"
        canvas = draw(title=title)
        title_lines = [d for d in canvas.drawn if d[0] > X0 + header.META_CELL and d[0] < X1 - header.LOGO_CELL]
        self.assertEqual(len(title_lines), 2)
        for x, _, text in title_lines:
            self.assertGreaterEqual(x, X0 + header.META_CELL)
        first, second = sorted(title_lines, key=lambda d: -d[1])
        self.assertEqual(rtl.shape(first[2]).count(" ") + rtl.shape(second[2]).count(" ") + 2, len(title.split()))

    def test_an_absurd_title_shrinks_and_still_fits_the_cell(self):
        canvas = draw(title=" ".join(["واژه"] * 60))
        left, right = X0 + header.META_CELL, X1 - header.LOGO_CELL
        for x, _, text in canvas.drawn:
            if left <= x <= right:
                self.assertLessEqual(x + canvas.stringWidth(text, "Vazir-Bold", 9.5), right + 0.5)

    def test_markers_in_a_title_are_plain_text(self):
        canvas = draw(title="الف --ب-- ج")
        self.assertTrue(any("--" in text for text in canvas.texts()))

    def test_the_borders_are_drawn_thick_outside_and_thin_inside(self):
        canvas = RecordingCanvas(pagesize=A4)
        widths, rects, lines = [], [], []
        canvas.setLineWidth = lambda w: widths.append(w) or type(canvas).setLineWidth(canvas, w)
        canvas.rect = lambda *a, **k: rects.append(a)
        canvas.line = lambda *a, **k: lines.append(a)
        draw(canvas)
        self.assertEqual(rects, [(X0, TOP - header.HEIGHT, X1 - X0, header.HEIGHT)])
        # two vertical dividers + two horizontal ones between the three rows
        self.assertEqual(len(lines), 4)
        self.assertGreater(header.OUTER_WIDTH, header.INNER_WIDTH)
        self.assertEqual(widths[-1], header.OUTER_WIDTH)

    def test_the_logo_goes_in_the_right_cell_and_no_logo_leaves_it_empty(self):
        canvas = RecordingCanvas(pagesize=A4)
        with mock.patch.object(canvas, "drawImage") as image:
            draw(canvas)
            image.assert_not_called()
            draw(canvas, logo=ImageReader(BytesIO(fixture_bytes("logo.png"))))
        [call] = image.call_args_list
        _, x, y, width, height = call.args
        self.assertGreaterEqual(x, X1 - header.LOGO_CELL)
        self.assertLessEqual(x + width, X1)
        self.assertTrue(call.kwargs["preserveAspectRatio"])
        self.assertLessEqual(y + height, TOP)
        self.assertGreaterEqual(y, TOP - header.HEIGHT)

    def test_survives_a_missing_bold_font_and_a_value_without_a_label(self):
        from reportlab.pdfbase import pdfmetrics

        real = pdfmetrics.getRegisteredFontNames
        with mock.patch.object(pdfmetrics, "getRegisteredFontNames", lambda: [n for n in real() if not n.endswith("-Bold")]):
            canvas = draw(rows=["بدون برچسب", "b", "c"])
        self.assertIn(rtl.shape("بدون برچسب"), canvas.texts())


def long_document() -> PdfInput:
    return PdfInput(
        title="عنوان آزمون", whole_code="PR-01-02", review="02", date="1405/07/07", validation="معتبر",
        logo=fixture_bytes("logo.png"), qr=fixture_bytes("logo.png"),
        blocks=tuple((provider.TEXT, f"{i}-بند\n" + "متن آزمایشی " * 40) for i in range(1, 25)),
    )


class EveryPageTests(SimpleTestCase):
    def test_every_page_carries_the_box_once(self):
        with mock.patch.object(header, "draw_boxed_header", wraps=header.draw_boxed_header) as draw_box:
            pdf = provider.deliver_to_pdf(long_document(), invariant=True)
        self.assertGreaterEqual(pages(pdf), 3)
        # Page 1 once (V_1.0 drew it twice). `save()` ends the last page through
        # showPage, which starts — and draws the box on — a page that is never written.
        self.assertIn(draw_box.call_count, (pages(pdf), pages(pdf) + 1))
        tops = {call.kwargs["top"] for call in draw_box.call_args_list}
        self.assertEqual(tops, {A4[1] - 40})
        for call in draw_box.call_args_list:
            self.assertEqual(call.kwargs["rows"], header.meta_rows("PR-01-02", "02", "1405/07/07"))

    def test_the_body_starts_below_the_box(self):
        maker = renderer.PDFMaker(whole_code="PR-01-02", title="ت", date="1405/07/07")
        maker.draw_header()
        self.assertLess(maker.current_y, A4[1] - 40 - header.HEIGHT - 20)
        maker.c.showPage()
        maker._new_page()
        self.assertLess(maker.current_y, A4[1] - 40 - header.HEIGHT - 20)

    def test_the_header_is_not_drawn_twice_on_page_one(self):
        maker = renderer.PDFMaker(whole_code="PR-01-02", title="ت", date="1405/07/07")
        with mock.patch.object(header, "draw_boxed_header") as draw_box:
            maker.draw_header()
            maker.draw_header()
            self.assertEqual(draw_box.call_count, 1)
            maker.initialize_first_page()  # ends page 1; the next page's box is the canvas's
            self.assertEqual(draw_box.call_count, 2)


class CompanyNameTests(SimpleTestCase):
    """The company's name at the centre of the header (owner's request, 2026-09-30)."""

    LEFT, RIGHT = X0 + header.META_CELL, X1 - header.LOGO_CELL

    def test_without_a_name_the_header_is_what_it_was(self):
        self.assertEqual(draw(company_name="").drawn, draw().drawn)
        self.assertEqual(draw(company_name="   ").drawn, draw().drawn)

    def test_the_name_is_a_small_line_centred_above_the_title(self):
        canvas = draw(title="عنوان", company_name="شرکت نمونه")
        [(nx, ny, name)] = [d for d in canvas.drawn if d[2] == rtl.shape("شرکت نمونه")]
        [(tx, ty, title)] = [d for d in canvas.drawn if d[2] == rtl.shape("عنوان")]
        width = canvas.stringWidth(name, "Vazir", header._COMPANY_SIZES[0])
        self.assertAlmostEqual(nx + width / 2, (self.LEFT + self.RIGHT) / 2, delta=0.5)
        self.assertGreater(ny, ty + 8, "the name is above the title")
        self.assertTrue(TOP - 18 < ny < TOP)
        self.assertLess(ty, TOP - header.HEIGHT / 2 + 4, "and the title moved down to make room")
        self.assertGreater(ty, TOP - header.HEIGHT, "but stays inside the box")

    def test_the_name_is_muted_and_the_callers_ink_is_untouched(self):
        canvas = RecordingCanvas(pagesize=A4)
        canvas.setFillColorRGB(0.1, 0.2, 0.3)
        with mock.patch.object(canvas, "setFillColorRGB", wraps=canvas.setFillColorRGB) as fill:
            draw(canvas, company_name="شرکت")
        colours = [call.args for call in fill.call_args_list]
        self.assertIn(header._COMPANY_COLOUR, colours)
        self.assertEqual(tuple(canvas._fillColorObj), (0.1, 0.2, 0.3), "saveState/restoreState around the header")

    def test_a_long_name_shrinks_and_never_leaves_the_cell(self):
        name = "شرکت توسعه و مدیریت سرمایه‌گذاری صنعتی و معدنی شمال شرق کشور"
        canvas = draw(company_name=name)
        [(x, _, text)] = [d for d in canvas.drawn if rtl.shape(name[:5]) in d[2] or d[2] == rtl.shape(name)]
        self.assertGreaterEqual(x, self.LEFT - 0.5)
        self.assertLessEqual(x + canvas.stringWidth(text, "Vazir", header._COMPANY_SIZES[-1]), self.RIGHT + 0.5)

    def test_an_absurd_name_is_cut_with_an_ellipsis(self):
        canvas = draw(company_name="واژه " * 80)
        [(x, _, text)] = [d for d in canvas.drawn if "…" in d[2]]
        self.assertLessEqual(x + canvas.stringWidth(text, "Vazir", header._COMPANY_SIZES[-1]), self.RIGHT + 0.5)

    def test_two_title_lines_still_fit_below_the_name(self):
        title = "روش اجرایی کنترل مستندات و سوابق سازمان و یک عنوان بسیار طولانی برای آزمون"
        canvas = draw(title=title, company_name="شرکت نمونه")
        lines = [d for d in canvas.drawn if self.LEFT < d[0] < self.RIGHT and d[2] != rtl.shape("شرکت نمونه")]
        self.assertEqual(len(lines), 2)
        for _, y, _ in lines:
            self.assertGreater(y, TOP - header.HEIGHT)
            self.assertLess(y, TOP - header._COMPANY_BAND + 4)


class CompanyNameOnEveryPageTests(SimpleTestCase):
    def test_pages_one_and_two_both_carry_the_name(self):
        maker = renderer.PDFMaker(
            whole_code="PR-01-02", title="ت", date="1405/07/07", company_name="شرکت نمونه"
        )
        with mock.patch.object(maker.c, "drawString", wraps=maker.c.drawString) as string:
            maker.draw_header()
            maker.c.showPage()  # page 2 gets the small header
            maker.c.showPage()  # page 3 too
        names = [call for call in string.call_args_list if call.args[2] == rtl.shape("شرکت نمونه")]
        self.assertEqual(len(names), 3)

    def test_a_document_without_the_option_prints_no_name(self):
        maker = renderer.PDFMaker(whole_code="PR-01-02", title="ت", date="1405/07/07")
        with mock.patch.object(maker.c, "drawString", wraps=maker.c.drawString) as string:
            maker.draw_header()
            maker.c.showPage()
        self.assertFalse([c for c in string.call_args_list if c.args[2] == rtl.shape("شرکت نمونه")])

    def test_deliver_to_pdf_passes_the_name_on(self):
        data = PdfInput(title="ت", whole_code="PR-01-02", review="01", date="1405/07/07", validation="", company_name="شرکت نمونه")
        with mock.patch.object(renderer.PDFMaker, "__init__", autospec=True, side_effect=renderer.PDFMaker.__init__) as init:
            provider.deliver_to_pdf(data, invariant=True)
        self.assertEqual(init.call_args.kwargs["company_name"], "شرکت نمونه")
