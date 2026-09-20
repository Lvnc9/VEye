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

    def test_text_merge_is_the_original(self):
        # Wraps on character count, and drops the last word when it is the one
        # that forces a wrap.
        self.assertEqual(renderer.PDFMaker.text_merge("aaa bbb ccc ddd", 12), [" aaa bbb ccc"])

    def test_body_text_wraps_on_character_count_not_width(self):
        maker = renderer.PDFMaker(whole_code="PR-01-01", title="ت")
        maker.draw_header()
        long_line = "ب" * 171
        with mock.patch.object(maker.c, "drawRightString") as draw:
            maker.add_body_text(long_line)
        # 171 characters > 170 -> chunks of 70: 70 + 70 + 31.
        self.assertEqual(draw.call_count, 3)

    def test_preview_watermark_absent_from_page_one(self):
        maker = renderer.PDFMaker(whole_code="PR-01-01", title="ت", preview_mode=True)
        maker.draw_header()
        with mock.patch.object(maker.c, "_draw_preview_on_current_page") as watermark:
            maker.c.showPage()  # end of page 1 draws the *next* page's watermark
            self.assertEqual(watermark.call_count, 1)
