"""The «مسئولیت ها» block as printed (owner's redesign, 2026-09-30): one wrapped line-group per row,
«حوزه X  واحد Y  جهت <text>», from the right margin."""
from unittest import mock

from django.test import SimpleTestCase

from apps.pdfgen import renderer, richtext, rtl

from .test_richtext import Drawn

LEFT, RIGHT = 40.0, 595.2755905511812 - 40.0


def draw(lines, *, start_y=None):
    maker = renderer.PDFMaker(whole_code="PR-01-02", title="ت", date="1405/07/07")
    maker.draw_header()
    maker.c.showPage()
    maker._header_drawn = True
    maker.first_page_initialized = True
    maker.current_y = start_y if start_y is not None else maker.page_height - maker.margin - maker.header_gap
    with Drawn(maker) as drawn:
        maker.responsibilities(lines)
    return maker, drawn


class ResponsibilitiesLayoutTests(SimpleTestCase):
    def test_the_heading_is_numbered_bold_and_at_the_right_margin(self):
        maker = renderer.PDFMaker(whole_code="PR-01-02", title="ت", date="1405/07/07")
        maker.draw_header()
        maker.c.showPage()
        maker._header_drawn = True
        maker.first_page_initialized = True
        maker.current_y = 700
        with mock.patch.object(maker.c, "drawRightString", wraps=maker.c.drawRightString) as heading:
            maker.responsibilities(["واحد X  جهت Y"])
        [call] = heading.call_args_list
        self.assertAlmostEqual(call.args[0], RIGHT, places=2)
        self.assertEqual(call.args[2], maker.prepare_rtl("1)مسئولیت ها:"))

    def test_each_row_is_one_line_from_the_right_margin(self):
        _, drawn = draw(["حوزه IT  واحد هوش مصنوعی  جهت نگهداری", "واحد مستقل  جهت پیگیری"])
        lines = [s for s in drawn.strings if s[4] == 12 and s[3] == "Vazir"]
        ys = sorted({round(s[1], 1) for s in lines}, reverse=True)
        self.assertEqual(len(ys), 2)
        for entry in lines:
            self.assertLessEqual(entry[0] + drawn.width(entry), RIGHT + 0.01)
            self.assertGreaterEqual(entry[0], LEFT)

    def test_the_first_run_of_a_row_is_the_rightmost(self):
        _, drawn = draw(["حوزه IT  واحد هوش مصنوعی  جهت نگهداری"])
        [line] = [s for s in drawn.strings if s[4] == 12 and s[3] == "Vazir"]
        self.assertAlmostEqual(line[0] + drawn.width(line), RIGHT, places=1)

    def test_a_long_text_wraps_by_width_and_loses_no_word(self):
        text = " ".join(f"واژه{n}" for n in range(1, 121))
        _, drawn = draw([f"واحد هوش مصنوعی  جهت {text}"])
        lines = [s for s in drawn.strings if s[4] == 12 and s[3] == "Vazir"]
        self.assertGreater(len({round(s[1], 1) for s in lines}), 3)
        for entry in lines:
            self.assertLessEqual(entry[0] + drawn.width(entry), RIGHT + 0.01)
            self.assertGreaterEqual(entry[0], LEFT - 0.01)
        self.assertEqual(sum(len(s[2].split()) for s in lines), 120 + 4)  # the words + «واحد هوش مصنوعی جهت»

    def test_a_hard_line_break_starts_a_new_line(self):
        _, drawn = draw(["الف:  سمت: مدیر\nشرح قدیمی"])
        ys = {round(s[1], 1) for s in drawn.strings if s[4] == 12 and s[3] == "Vazir"}
        self.assertEqual(len(ys), 2)

    def test_markers_in_the_text_are_honoured(self):
        _, drawn = draw(["واحد X  جهت **مهم** است"])
        bold = [s for s in drawn.strings if s[3] == "Vazir-Bold" and s[4] == 12]
        self.assertEqual(len(bold), 1)

    def test_rows_are_separated_by_a_gap(self):
        _, drawn = draw(["یک", "دو"])
        ys = sorted({round(s[1], 1) for s in drawn.strings if s[4] == 12}, reverse=True)
        self.assertGreater(ys[0] - ys[1], 12 * 1.6 + 5)

    def test_a_long_block_continues_on_the_next_page_above_the_footer(self):
        maker, drawn = draw([f"واحد شماره {n}  جهت " + "کلمه " * 30 for n in range(40)])
        self.assertGreater(drawn.pages, 1)
        self.assertGreaterEqual(min(s[1] for s in drawn.strings if s[4] == 12), richtext.BOTTOM - 1)

    def test_the_cursor_moves_below_the_block_and_the_block_counter_advances(self):
        maker, drawn = draw(["یک"])
        self.assertLess(maker.current_y, maker.page_height - maker.margin - maker.header_gap - 40)
        self.assertEqual(maker.idx_texts, 2)
