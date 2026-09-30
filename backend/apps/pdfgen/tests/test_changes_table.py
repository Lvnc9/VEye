"""جدول تغییرات (owner's request, 2026-09-30): the table uses the whole text width, the
description column takes what the number and date columns leave and wraps, rows grow with
their text, a table that runs past a page repeats its header. Drawn through a real
PDFMaker with a recorder on its canvas (as test_richtext does)."""
from django.test import SimpleTestCase

from apps.pdfgen import renderer, richtext, rtl

from .test_richtext import Drawn

LEFT, RIGHT = 40.0, 595.2755905511812 - 40.0
HEADER = ["شماره ردیف", "تاریخ", "عنوان"]
DESCRIPTION_LEFT = LEFT + richtext.CHANGES_NUMBER_WIDTH + richtext.CHANGES_DATE_WIDTH
DESCRIPTION_RIGHT = RIGHT
SENTENCE = "این تغییر شامل اصلاح چند بند و افزودن توضیحات تکمیلی است "


def draw(rows):
    maker = renderer.PDFMaker(whole_code="PR-01-02", title="ت", date="1405/07/07")
    maker.draw_header()
    maker.c.showPage()
    maker._header_drawn = True
    maker.first_page_initialized = True
    maker.current_y = maker.page_height - maker.margin - maker.header_gap
    with Drawn(maker) as drawn:
        maker.add_table([HEADER] + [list(row) for row in rows], [50, 100, 200], row_height=30)
    return maker, drawn


def description(drawn):
    """The strings inside the description column (right of the date and number columns)."""
    apart = {rtl.shape(h) for h in HEADER} | {rtl.shape("جدول تغییرات:")}  # the labels and the heading
    return [s for s in drawn.body() if s[0] >= DESCRIPTION_LEFT - 0.01 and s[2] not in apart]


def cells(drawn):
    """The table's cell rectangles (not the page's footer logo or header box)."""
    widths = {richtext.CHANGES_NUMBER_WIDTH, richtext.CHANGES_DATE_WIDTH, DESCRIPTION_RIGHT - DESCRIPTION_LEFT}
    return [a for a, _ in drawn.rects if any(abs(a[2] - w) < 0.01 for w in widths)]


class WidthTests(SimpleTestCase):
    def test_the_table_spans_the_whole_text_width(self):
        _, drawn = draw([["1", "1405/01/01", "اصلاح بند"]])
        left = min(a[0] for a in cells(drawn))
        right = max(a[0] + a[2] for a in cells(drawn))
        self.assertAlmostEqual(left, LEFT, places=2)
        self.assertAlmostEqual(right, RIGHT, places=2)

    def test_the_columns_are_description_date_number_from_the_right(self):
        _, drawn = draw([["1", "1405/01/01", "اصلاح بند"]])
        widths = [a[2] for a in cells(drawn)[:3]]  # the header row, drawn right to left
        self.assertAlmostEqual(widths[1], richtext.CHANGES_DATE_WIDTH, places=2)
        self.assertAlmostEqual(widths[2], richtext.CHANGES_NUMBER_WIDTH, places=2)
        self.assertAlmostEqual(sum(widths), RIGHT - LEFT, places=2)
        self.assertGreater(widths[0], 300)

    def test_the_header_label_fits_its_cell(self):
        _, drawn = draw([["1", "1405/01/01", "اصلاح بند"]])
        [label] = drawn.find("شماره ردیف")
        self.assertLessEqual(drawn.width(label), richtext.CHANGES_NUMBER_WIDTH - 2 * richtext.CELL_PAD)


class WrappingTests(SimpleTestCase):
    def test_a_long_description_wraps_inside_its_cell_and_the_row_grows(self):
        long_text = SENTENCE * 12  # ~ 700 characters
        maker, drawn = draw([["1", "1405/01/01", "کوتاه"], ["2", "1405/01/02", long_text]])
        lines = description(drawn)
        ys = sorted({round(s[1], 1) for s in lines if s[2] != rtl.shape("کوتاه")}, reverse=True)
        self.assertGreater(len(ys), 4, "several lines")
        for entry in lines:
            self.assertGreaterEqual(entry[0], DESCRIPTION_LEFT + richtext.CELL_PAD - 0.01)
            self.assertLessEqual(entry[0] + drawn.width(entry), RIGHT - richtext.CELL_PAD + 0.01)
        # the second row is taller than the first (which is the minimum height)
        heights = sorted({round(a[3], 1) for a in cells(drawn)})
        self.assertGreater(max(heights), 4 * 16)
        self.assertLess(min(heights), 30)

    def test_no_words_are_lost(self):
        text = " ".join(f"واژه{n}" for n in range(1, 121))
        _, drawn = draw([["1", "1405/01/01", text]])
        words = " ".join(s[2] for s in description(drawn))
        for n in (1, 60, 120):
            self.assertIn(rtl.shape(f"واژه{n}").replace(" ", ""), words.replace(" ", ""))
        self.assertEqual(len(words.split()), 120)

    def test_a_hard_line_break_starts_a_new_line(self):
        _, drawn = draw([["1", "1405/01/01", "بند اول\nبند دوم"]])
        first, second = drawn.find("بند اول"), drawn.find("بند دوم")
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertGreater(first[0][1], second[0][1])

    def test_the_description_is_flush_right_and_number_and_date_are_centred(self):
        _, drawn = draw([["1", "1405/01/01", "اصلاح بند"]])
        [text] = drawn.find("اصلاح بند")
        self.assertAlmostEqual(text[0] + drawn.width(text), RIGHT - richtext.CELL_PAD, places=1)
        [date] = drawn.find("1405/01/01")
        centre = LEFT + richtext.CHANGES_NUMBER_WIDTH + richtext.CHANGES_DATE_WIDTH / 2
        self.assertAlmostEqual(date[0] + drawn.width(date) / 2, centre, delta=1.5)


class PagingTests(SimpleTestCase):
    def test_a_long_table_repeats_its_header_on_every_page(self):
        rows = [[str(n), "1405/01/01", SENTENCE * 3] for n in range(1, 41)]
        maker, drawn = draw(rows)
        self.assertGreater(drawn.pages, 1)
        self.assertEqual(len(drawn.find("شماره ردیف")), drawn.pages)

    def test_no_row_is_drawn_below_the_footer_line(self):
        rows = [[str(n), "1405/01/01", SENTENCE * 3] for n in range(1, 41)]
        _, drawn = draw(rows)
        self.assertGreaterEqual(min(a[1] for a in cells(drawn)), richtext.BOTTOM - 0.01)

    def test_a_row_taller_than_a_page_continues_on_the_next_page(self):
        text = " ".join(["کلمه"] * 2500)
        maker, drawn = draw([["1", "1405/01/01", text]])
        self.assertGreaterEqual(drawn.pages, 3)
        words = sum(len(s[2].split()) for s in description(drawn))
        self.assertEqual(words, 2500)
        for entry in description(drawn):
            self.assertGreaterEqual(entry[0], DESCRIPTION_LEFT + richtext.CELL_PAD - 0.01)

    def test_the_header_is_never_left_alone_at_the_foot_of_a_page(self):
        rows = [[str(n), "1405/01/01", "کوتاه"] for n in range(1, 4)]
        maker, drawn = draw(rows)
        maker2 = renderer.PDFMaker(whole_code="PR-01-02", title="ت", date="1405/07/07")
        maker2.draw_header()
        maker2.c.showPage()
        maker2._header_drawn = True
        maker2.first_page_initialized = True
        maker2.current_y = richtext.BOTTOM + 60  # room for the heading and the header row only
        with Drawn(maker2) as low:
            maker2.add_table([HEADER] + [list(r) for r in rows])
        self.assertEqual(low.pages, 2)
        [label] = low.find("شماره ردیف")
        self.assertGreater(label[1], 600, "the header moved to the new page with its first row")

    def test_the_cursor_ends_below_the_table(self):
        maker, drawn = draw([["1", "1405/01/01", "اصلاح بند"]])
        bottom = min(a[1] for a in cells(drawn))
        self.assertLess(maker.current_y, bottom)
