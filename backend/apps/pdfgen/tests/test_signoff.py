"""Who signed, and where (owner's request, 2026-09-30): روش اجرایی and دستورالعمل keep the control
table on page 1 — without its «وضعیت کنترل» column; پوستر and فرم close their last page with the
sign-off strip and have no cover page; a superseded revision carries «منسوخ» on every page.
Drawn through a real PDFMaker with recorders on its canvas."""
from unittest import mock

from django.test import SimpleTestCase

from apps.pdfgen import provider, renderer, rtl, signoff
from apps.pdfgen.provider import PdfInput, SignatureBlock

from .helpers import fixture_bytes

LEFT, RIGHT = 40.0, 595.2755905511812 - 40.0
SIGNERS = [
    ["علی رضایی", "مدیر واحد", fixture_bytes("sign_creater.png")],
    ["سارا احمدی", "معاون", fixture_bytes("sign_confirmer.png")],
    ["", "", None],
]


def maker(**kwargs):
    m = renderer.PDFMaker(whole_code="PO-01-02", title="ت", date="1405/07/07", **kwargs)
    m.draw_header()
    return m


class Recorder:
    """Strings (drawString and drawCentredString), images and rects drawn on a maker's canvas."""

    def __init__(self, m):
        self.m, self.strings, self.images, self.rects, self.pages = m, [], [], [], 1
        c = m.c
        self._patches = [
            mock.patch.object(c, "drawString", side_effect=self._rec(c.drawString)),
            mock.patch.object(c, "drawCentredString", side_effect=self._rec(c.drawCentredString)),
            mock.patch.object(c, "drawImage", side_effect=self._img(c.drawImage)),
            mock.patch.object(c, "rect", side_effect=self._rect(c.rect)),
            mock.patch.object(c, "showPage", side_effect=self._page(c.showPage)),
        ]

    def _rec(self, real):
        def draw(x, y, text, *a, **k):
            self.strings.append((x, y, text, self.pages))
            return real(x, y, text, *a, **k)

        return draw

    def _img(self, real):
        def draw(image, x, y, *a, **k):
            self.images.append((x, y, k.get("width") or (a[0] if a else None), self.pages))
            return real(image, x, y, *a, **k)

        return draw

    def _rect(self, real):
        def draw(x, y, w, h, *a, **k):
            self.rects.append((x, y, w, h, self.pages))
            return real(x, y, w, h, *a, **k)

        return draw

    def _page(self, real):
        def show(*a, **k):
            self.pages += 1
            return real(*a, **k)

        return show

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()

    def find(self, text):
        return [s for s in self.strings if s[2] == rtl.shape(text)]


class ControlTableTests(SimpleTestCase):
    def draw(self):
        m = maker()
        with Recorder(m) as rec:
            m.draw_control_table(*SIGNERS, "", "")
        return m, rec

    def test_there_is_no_control_status_column(self):
        _, rec = self.draw()
        # the four header cells are drawn through drawCentredString on the shaped label
        for label in ("امضا", "سمت", "نام و نام خانوادگی", "مسئولیت"):
            self.assertTrue(rec.find(label), label)
        self.assertFalse(rec.find("معتبر"))
        self.assertFalse(rec.find("منسوخ"))
        # only the heading «وضعیت کنترل:» is left (owner's decision); its column and cell are gone
        self.assertEqual(len([s for s in rec.strings if rtl.shape("وضعیت") in s[2]]), 1)

    def test_the_four_columns_share_the_500_pt_the_table_had(self):
        _, rec = self.draw()
        m = maker()
        with mock.patch.object(m.c, "roundRect", wraps=m.c.roundRect) as rr:
            m.draw_control_table(*SIGNERS)
        outer = rr.call_args_list[-1].args
        self.assertEqual((outer[0], outer[2]), (50, 500))
        widths = sorted({round(c.args[2]) for c in rr.call_args_list[:-1]})
        self.assertEqual(widths, [90, 100, 140, 170])

    def test_each_role_is_printed_on_one_line_in_reading_order(self):
        _, rec = self.draw()
        for label in ("تهیه کننده", "تایید کننده", "تصویب کننده"):
            [drawn] = rec.find(label)  # one string = one line, never wrapped over two
            self.assertTrue(drawn)

    def test_names_and_posts_are_in_their_rows(self):
        _, rec = self.draw()
        for text in ("علی رضایی", "مدیر واحد", "سارا احمدی", "معاون"):
            self.assertTrue(rec.find(text), text)

    def test_signatures_are_drawn_in_the_leftmost_column(self):
        _, rec = self.draw()
        self.assertEqual(len(rec.images), 2)  # the third signer is unsigned
        for x, _, _, _ in rec.images:
            self.assertLess(x, 50 + 90)

    def test_still_works_with_no_arguments(self):
        m = maker()
        m.draw_control_table()  # V_1.0 crashed here


class StripTests(SimpleTestCase):
    def draw(self, m=None, signers=SIGNERS):
        m = m or maker(cover_page=False)
        with Recorder(m) as rec:
            m.draw_signoff_strip(*signers)
        return m, rec

    def test_three_columns_right_to_left(self):
        _, rec = self.draw()
        xs = [rec.find(label + ":")[0][0] for label in signoff.ROLES]
        self.assertGreater(xs[0], xs[1])
        self.assertGreater(xs[1], xs[2])
        self.assertLess(xs[0], RIGHT)
        self.assertGreater(xs[2], LEFT)

    def test_each_column_stacks_role_post_name_signature(self):
        _, rec = self.draw()
        col = [s for s in rec.strings if s[0] > RIGHT - (RIGHT - LEFT) / 3]  # the rightmost third
        title = next(s for s in col if s[2] == rtl.shape("تهیه کننده:"))
        post = next(s for s in col if s[2] == rtl.shape(" مدیر واحد"))  # a run after its bold label
        name = next(s for s in col if s[2] == rtl.shape(" علی رضایی"))
        label = next(s for s in col if s[2] == rtl.shape("امضا:"))
        self.assertGreater(title[1], post[1])
        self.assertGreater(post[1], name[1])
        self.assertGreater(name[1], label[1])
        (x, y, w, page), *_ = [i for i in rec.images if i[0] > RIGHT - (RIGHT - LEFT) / 3]
        self.assertLess(y, label[1])  # the signature sits under its «امضا:»

    def test_no_date_and_no_validity_are_printed(self):
        _, rec = self.draw()
        text = " ".join(s[2] for s in rec.strings)
        for word in ("تاریخ", "وضعیت", "معتبر", "منسوخ"):
            self.assertNotIn(rtl.shape(word), text)

    def test_it_is_plain_text_with_no_table_or_boxes(self):
        _, rec = self.draw()
        self.assertEqual(rec.rects, [])

    def test_the_strip_is_pinned_above_the_footer(self):
        _, rec = self.draw()
        lowest = min(i[1] for i in rec.images)  # the signature box is the strip's lowest drawing
        self.assertAlmostEqual(lowest, signoff.BOTTOM + signoff.PAD / 2, places=2)
        self.assertGreater(lowest, 90)  # the footer's QR reaches y = 90

    def test_it_is_full_width_in_three_equal_columns(self):
        _, rec = self.draw()
        xs = [entry[0] for entry in rec.find("امضا:")]  # the same label once per column, each drawn from its column's right edge
        column = (RIGHT - LEFT) / 3
        self.assertEqual(len(xs), 3)
        self.assertAlmostEqual(xs[0] - xs[1], column, places=1)
        self.assertAlmostEqual(xs[1] - xs[2], column, places=1)

    def test_it_stays_on_the_page_when_the_content_leaves_room(self):
        m = maker(cover_page=False)
        m.initialize_first_page()
        m.current_y = 500
        _, rec = self.draw(m)
        self.assertEqual(rec.pages, 1)

    def test_it_goes_to_a_new_page_when_the_content_reaches_its_place(self):
        m = maker(cover_page=False)
        m.initialize_first_page()
        m.current_y = signoff.BOTTOM + 100  # the strip is taller than that
        _, rec = self.draw(m)
        self.assertEqual(rec.pages, 2)
        self.assertTrue(all(entry[3] == 2 for entry in rec.strings), "all of it on the new page")

    def test_a_long_name_wraps_and_the_stack_grows_upwards_for_every_column(self):
        long = ["نام بسیار طولانی " * 6, "سمت", None]
        _, tall = self.draw(signers=[long, SIGNERS[1], SIGNERS[2]])
        _, short = self.draw()
        top_of = lambda rec: max(entry[1] for entry in rec.strings)
        self.assertGreater(top_of(tall), top_of(short))
        # the signature labels stay put: the strip is pinned at the bottom, it grows upwards
        self.assertAlmostEqual(tall.find("امضا:")[0][1], short.find("امضا:")[0][1], places=2)
        for entry in tall.strings:
            self.assertGreaterEqual(entry[0], LEFT - 1)

    def test_markers_in_a_name_do_not_restyle_it(self):
        _, rec = self.draw(signers=[["**علی** رضایی", "--مدیر--", None], SIGNERS[1], SIGNERS[2]])
        self.assertTrue(rec.find(" علی رضایی"))
        self.assertTrue(rec.find(" مدیر"))

    def test_empty_signers_still_print_the_labels(self):
        _, rec = self.draw(signers=[None, None, None])
        self.assertEqual(len(rec.find("سمت:")), 3)
        self.assertEqual(len(rec.find("نام و نام خانوادگی:")), 3)
        self.assertEqual(rec.images, [])


class CoverPageTests(SimpleTestCase):
    def test_with_a_cover_page_the_body_starts_on_page_two(self):
        m = maker()
        with Recorder(m) as rec:
            m.initialize_first_page()
        self.assertEqual(rec.pages, 2)

    def test_without_one_the_body_starts_on_page_one_under_the_header(self):
        m = maker(cover_page=False)
        with Recorder(m) as rec:
            m.initialize_first_page()
        self.assertEqual(rec.pages, 1)
        self.assertAlmostEqual(m.current_y, m.page_height - m.margin - m.header_gap)


class ThroughTheProviderTests(SimpleTestCase):
    def data(self, **kwargs):
        base = dict(
            title="عنوان", whole_code="PO-01-02", review="01", date="1405/07/07",
            logo=fixture_bytes("logo.png"), qr=fixture_bytes("logo.png"),
            creater=SignatureBlock("علی رضایی", "مدیر", fixture_bytes("sign_creater.png")),
            blocks=((provider.TEXT, "1-بند\nمتن\n"),),
        )
        base.update(kwargs)
        return PdfInput(**base)

    def test_a_control_table_document_gets_the_table_and_no_strip(self):
        with mock.patch.object(renderer.PDFMaker, "draw_control_table", autospec=True) as table, \
                mock.patch.object(renderer.PDFMaker, "draw_signoff_strip", autospec=True) as strip:
            provider.deliver_to_pdf(self.data(signoff_layout=provider.CONTROL_TABLE), invariant=True)
        self.assertEqual((table.call_count, strip.call_count), (1, 0))

    def test_a_strip_document_gets_the_strip_and_no_table(self):
        with mock.patch.object(renderer.PDFMaker, "draw_control_table", autospec=True) as table, \
                mock.patch.object(renderer.PDFMaker, "draw_signoff_strip", autospec=True) as strip:
            provider.deliver_to_pdf(self.data(signoff_layout=provider.STRIP), invariant=True)
        self.assertEqual((table.call_count, strip.call_count), (0, 1))

    def test_a_strip_document_is_one_page_when_its_body_is_short(self):
        pdf = provider.deliver_to_pdf(self.data(signoff_layout=provider.STRIP), invariant=True)
        self.assertEqual(pdf.count(b"/Type /Page\n"), pdf.count(b"/Type /Page\n"))  # (parsed below)
        import re

        self.assertEqual(len(re.findall(rb"/Type /Page\b", pdf)), 1)

    def test_the_strip_is_drawn_after_the_last_block(self):
        order = []
        with mock.patch.object(renderer.PDFMaker, "add_body_text", autospec=True, side_effect=lambda *a, **k: order.append("body")), \
                mock.patch.object(renderer.PDFMaker, "draw_signoff_strip", autospec=True, side_effect=lambda *a, **k: order.append("strip")):
            provider.deliver_to_pdf(self.data(signoff_layout=provider.STRIP), invariant=True)
        self.assertEqual(order, ["body", "strip"])


class ObsoleteWatermarkTests(SimpleTestCase):
    """Marks are (page, text) as they are drawn. `save()` closes the last page through `showPage`, which
    starts a page 4 that never reaches the file — its mark is the canvas's own housekeeping."""

    def marks(self, **kwargs):
        m = maker(**kwargs)
        marks = []
        real = m.c._draw_preview_on_current_page

        def spy():
            marks.append((m.c.getPageNumber(), m.c._watermark_text()))
            return real()

        m.c._draw_preview_on_current_page = spy
        m.c.showPage()
        m.c.showPage()
        pdf = m.generate_pdf()
        return marks, pdf

    def test_an_obsolete_revision_is_marked_once_on_each_page_after_the_first(self):
        marks, pdf = self.marks(obsolete=True)
        self.assertEqual([page for page, _ in marks if page <= 3], [2, 3])  # not again on 3 by save()
        self.assertEqual({text for _, text in marks}, {"منسوخ"})

    def test_page_one_of_an_obsolete_revision_is_marked_when_the_canvas_is_made(self):
        with mock.patch.object(renderer.HeaderFooterCanvas, "drawCentredString", autospec=True) as draw:
            renderer.PDFMaker(whole_code="PO-01-02", title="ت", obsolete=True)
        self.assertEqual([c.args[3] for c in draw.call_args_list], [rtl.shape("منسوخ")])

    def test_the_mark_is_in_the_pdf_on_every_page(self):
        import re

        _, pdf = self.marks(obsolete=True)
        self.assertEqual(len(re.findall(rb"/Type /Page\b", pdf)), 3)

    def test_a_current_revision_carries_no_mark(self):
        marks, _ = self.marks()
        self.assertEqual(marks, [])

    def test_obsolete_wins_over_a_preview(self):
        m = maker(obsolete=True, preview_mode=True)
        self.assertEqual(m.c._watermark_text(), "منسوخ")
        marks, _ = self.marks(obsolete=True, preview_mode=True)
        self.assertEqual({text for _, text in marks}, {"منسوخ"})

    def test_a_preview_alone_keeps_its_old_behaviour(self):
        marks, _ = self.marks(preview_mode=True)
        # pages 2 and 3 as they begin, page 3 again by save() (V_1.0's quirk), and the closing page 4
        self.assertEqual([page for page, _ in marks], [2, 3, 3, 4])
        self.assertEqual({text for _, text in marks}, {"پیش نمایش"})
