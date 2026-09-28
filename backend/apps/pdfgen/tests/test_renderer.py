"""Properties the port must keep beyond matching the golden files: no shared
state between concurrent renders, the pinned bidi implementation, fonts, and the
crash-level V_1.0 bugs staying fixed."""
import importlib.metadata
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from django.test import SimpleTestCase
from reportlab.pdfbase import pdfmetrics

from apps.pdfgen import provider, renderer
from apps.pdfgen.provider import PdfInput, SignatureBlock

from .helpers import fixture_bytes


def make_input(n: int) -> PdfInput:
    """Inputs that differ in every field, so cross-talk between two renders
    would show up as one PDF containing the other's data."""
    return PdfInput(
        title=f"عنوان شماره {n}",
        whole_code=f"PR-{n:02d}-01",
        review="01",
        date=f"1404/0{n % 9 + 1}/1{n % 9}",
        validation="معتبر" if n % 2 else "منسوخ",
        upper_footnote=f"پاورقی بالا {n}",
        lower_footnote=f"پاورقی پایین {n}",
        logo=fixture_bytes("logo.png") if n % 2 else None,
        qr=fixture_bytes("logo.png"),
        creater=SignatureBlock(f"نام {n}", f"سمت {n}", fixture_bytes("sign_creater.png")),
        blocks=(
            (provider.TEXT, f"{n}-هدف\nمتن کوتاه {n}\n"),
            (provider.TABLE, [[str(n), "1404/01/01", f"تغییر {n}"]]),
        )
        + tuple((provider.TEXT, f"بند {n}.{i} " + "متن " * 20) for i in range(60)),
    )


class NoSharedStateTests(SimpleTestCase):
    """V_1.0 kept the document in a module-level `all_documents` dict; two renders
    at once would have drawn each other's data. Rendering is now a pure function
    of its input."""

    def test_concurrent_renders_equal_sequential_renders(self):
        inputs = [make_input(n) for n in range(1, 9)]
        expected = [provider.deliver_to_pdf(data, invariant=True) for data in inputs]

        barrier = threading.Barrier(len(inputs))

        def render(data):
            barrier.wait()  # start together to maximise overlap
            return provider.deliver_to_pdf(data, invariant=True)

        for _ in range(3):
            with ThreadPoolExecutor(max_workers=len(inputs)) as pool:
                actual = list(pool.map(render, inputs))
            for n, (a, b) in enumerate(zip(actual, expected), start=1):
                self.assertTrue(a == b, f"render {n} differs when run concurrently")

    def test_renders_do_not_carry_over_between_calls(self):
        first = provider.deliver_to_pdf(make_input(1), invariant=True)
        provider.deliver_to_pdf(make_input(2), invariant=True)
        self.assertEqual(first, provider.deliver_to_pdf(make_input(1), invariant=True))

    def test_module_has_no_mutable_global_documents(self):
        # V_1.0's globals: all_documents (dict), SHORT/LONG/RESPONS (buffers), idx_texts.
        for module in (renderer, provider):
            for name in ("all_documents", "SHORT", "LONG", "RESPONS", "idx_texts"):
                self.assertFalse(hasattr(module, name), f"{module.__name__}.{name}")


class PinnedDependencyTests(SimpleTestCase):
    def test_uses_the_legacy_pure_python_bidi(self):
        # `bidi.get_display` (Rust, python-bidi >= 0.5) orders mixed digits/Latin/
        # Persian differently; issued PDFs must keep matching.
        self.assertEqual(renderer.get_display.__module__, "bidi.algorithm")
        self.assertEqual(importlib.metadata.version("python-bidi"), "0.6.11")

    def test_mixed_digits_latin_and_persian_keep_their_runs_and_order(self):
        shaped = renderer.PDFMaker.prepare_rtl(None, "کد PR-01-01 در سال 1404")
        # Latin/digit runs stay intact and left-to-right inside the RTL line, and
        # the *last* logical run (1404) comes first visually.
        self.assertIn("PR-01-01", shaped)
        self.assertTrue(shaped.startswith("1404"))


class FontTests(SimpleTestCase):
    def test_fonts_are_registered_once_at_startup(self):
        names = pdfmetrics.getRegisteredFontNames()
        self.assertIn("Vazir", names)
        self.assertIn("Vazir-Bold", names)
        self.assertFalse(hasattr(renderer.PDFMaker, "_register_fonts"))

    def test_pdf_embeds_both_vazir_faces(self):
        pdf = provider.deliver_to_pdf(make_input(1), invariant=True)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreaterEqual(len(re.findall(rb"/FontFile2", pdf)), 2)
        self.assertIn(b"Vazir", pdf)
        self.assertIn(b"Vazir-Bold", pdf)


class CrashBugRegressionTests(SimpleTestCase):
    """The crash-level V_1.0 bugs from the Phase 4 brief."""

    def maker(self, **kwargs):
        return renderer.PDFMaker(whole_code="PR-01-01", title="عنوان", date="1404/01/01", **kwargs)

    def test_control_table_without_arguments_does_not_share_mutable_defaults(self):
        # V_1.0: `creater=[]` then `creater[1]` -> IndexError.
        maker = self.maker()
        maker.draw_control_table()
        self.assertTrue(maker.generate_pdf().startswith(b"%PDF-"))

    def test_header_with_explicit_details_survives_an_odd_code(self):
        # V_1.0 split the code on "-" before checking whether details were given.
        maker = renderer.PDFMaker(whole_code="NODASHES", title="عنوان")
        maker.draw_header(details=["a", "b", "c"])
        self.assertTrue(maker.generate_pdf().startswith(b"%PDF-"))

    def test_small_header_survives_a_missing_bold_font(self):
        # V_1.0's small header did an unguarded setFont(font + "-Bold").
        maker = self.maker()
        maker.draw_header()
        maker.c.showPage()
        real = pdfmetrics.getRegisteredFontNames
        with mock.patch.object(
            pdfmetrics, "getRegisteredFontNames", lambda: [n for n in real() if not n.endswith("-Bold")]
        ):
            maker.c.showPage()  # draws the small header on the new page
        self.assertTrue(maker.generate_pdf().startswith(b"%PDF-"))

    def test_missing_logo_and_qr_draw_placeholders_not_crash(self):
        pdf = provider.deliver_to_pdf(
            PdfInput(title="ت", whole_code="PR-01-01", review="01", date="1404/01/01", validation="")
        )
        self.assertTrue(pdf.startswith(b"%PDF-"))


class PreservedQuirkTests(SimpleTestCase):
    """The user asked for fidelity: these are V_1.0 behaviours, kept on purpose.
    (The golden files pin them too; these say what each one is.)"""

    def test_text_merge_keeps_every_word_since_2026_09_28(self):
        # V_1.0 dropped the word that forced a wrap ([" aaa bbb ccc"]) and, with
        # an identity test, flushed a repeated short word early.
        self.assertEqual(renderer.PDFMaker.text_merge("aaa bbb ccc ddd", 12), [" aaa bbb ccc", "ddd"])
        self.assertEqual(renderer.PDFMaker.text_merge("x y x y", 180), [" x y x y"])
        self.assertEqual(renderer.PDFMaker.text_merge("کوتاه", 180), [" کوتاه"])

    def test_body_text_wraps_by_width_since_2026_09_28(self):
        # The owner's decision (2026-09-28): no drawn line is wider than the text
        # area. V_1.0 left 90-170 character lines whole (running off the page) and
        # cut longer ones into 70-character chunks mid-word.
        # 160 characters: V_1.0 drew this as one line, far wider than the page.
        for words in (20, 60):
            with self.subTest(characters=len(" ".join(["کلمه‌ای"] * words))):
                maker = renderer.PDFMaker(whole_code="PR-01-01", title="ت")
                maker.draw_header()
                with mock.patch.object(maker.c, "drawRightString", wraps=maker.c.drawRightString) as draw:
                    maker.add_body_text(" ".join(["کلمه‌ای"] * words))
                drawn = [call.args[2] for call in draw.call_args_list]
                self.assertGreater(len(drawn), 1)
                width = maker.page_width - 2 * maker.margin
                for text in drawn:
                    self.assertLessEqual(maker.c.stringWidth(text, "Vazir", 12), width + 0.01)

    def test_preview_watermark_absent_from_page_one(self):
        maker = renderer.PDFMaker(whole_code="PR-01-01", title="ت", preview_mode=True)
        maker.draw_header()
        with mock.patch.object(maker.c, "_draw_preview_on_current_page") as watermark:
            maker.c.showPage()  # end of page 1 draws the *next* page's watermark
            self.assertEqual(watermark.call_count, 1)


class BodyWrapTests(SimpleTestCase):
    """renderer.wrap_body_line — the width wrap (owner's decision, 2026-09-28)."""

    @staticmethod
    def measure(text, style):
        # One point per character, two for bold: easy to reason about.
        return len(text) * (2 if style == "bold" else 1)

    def test_a_line_that_fits_is_returned_unchanged(self):
        line = "کوتاه **پررنگ** است"
        self.assertEqual(renderer.wrap_body_line(line, 100, self.measure), [line])

    def test_words_survive_in_reading_order(self):
        words = [f"واژه{i}" for i in range(30)]
        lines = renderer.wrap_body_line(" ".join(words), 40, self.measure)
        self.assertGreater(len(lines), 1)
        self.assertEqual(" ".join(lines).split(), words)
        for line in lines:
            self.assertLessEqual(self.measure(line, "normal"), 40)
            self.assertEqual(line, line.strip())

    def test_markers_are_closed_and_reopened_across_a_break(self):
        lines = renderer.wrap_body_line("آغاز **این بخش پررنگ طولانی است** پایان", 20, self.measure)
        for line in lines:
            self.assertEqual(line.count("**") % 2, 0, line)
        joined = "".join(text for line in lines for text, _ in renderer.marker_runs(line))
        self.assertEqual(joined.replace(" ", ""), "آغازاینبخشپررنگطولانیاستپایان")
        styles = {style for line in lines for _, style in renderer.marker_runs(line) if "پررنگ" in _}
        self.assertEqual(styles, {"bold"})

    def test_a_word_wider_than_the_line_is_cut(self):
        lines = renderer.wrap_body_line("ب" * 25, 10, self.measure)
        self.assertEqual(lines, ["ب" * 10, "ب" * 10, "ب" * 5])

    def test_the_heading_stays_bold_on_every_piece(self):
        maker = renderer.PDFMaker(whole_code="PR-01-01", title="ت")
        maker.draw_header()
        heading = " ".join(["عنوان"] * 60)
        with mock.patch.object(maker.c, "setFont", wraps=maker.c.setFont) as set_font:
            maker.add_body_text(heading + "\nمتن", not_body=True)
        bold_calls = [c for c in set_font.call_args_list if c.args[0] == "Vazir-Bold" and c.args[1] == 14]
        self.assertGreater(len(bold_calls), 1)
