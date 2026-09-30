"""The layout engine of the rich تشریحی بلند body (richtext.py) — owner's request, 2026-09-29.
Drawn through a real PDFMaker; a recorder wraps its canvas so positions can be asserted."""
from unittest import mock

from django.test import SimpleTestCase

from apps.pdfgen import provider, renderer, richtext, rtl
from apps.pdfgen.provider import PdfInput

from .helpers import fixture_bytes

LEFT, RIGHT = 40.0, 595.2755905511812 - 40.0
LOREM = "این یک متن آزمایشی طولانی است که برای بررسی چیدمان و شکستن خط در چند سطر نوشته شده است. "


def text(value, *marks):
    node = {"type": "text", "text": value}
    if marks:
        node["marks"] = list(marks)
    return node


def para(*content, **attrs):
    node = {"type": "paragraph", "content": list(content)}
    if attrs:
        node["attrs"] = attrs
    return node


def doc(*blocks):
    return {"type": "doc", "content": list(blocks)}


def cell(*content, header=False):
    return {"type": "tableHeader" if header else "tableCell", "content": list(content) or [para()]}


def table(*rows):
    return {"type": "table", "content": [{"type": "tableRow", "content": list(row)} for row in rows]}


def rgb(entry):
    fill = entry[5]
    return tuple(fill) if isinstance(fill, tuple) else (fill.red, fill.green, fill.blue)


def item(*content):
    return {"type": "listItem", "content": list(content)}


class Drawn:
    """What was drawn: strings with their position and font, links, skews, rects, pages."""

    def __init__(self, maker):
        self.maker = maker
        self.strings = []  # (x, y, text, font, size, fill)
        self.links = []
        self.skews = []
        self.rects = []
        self.lines = []
        self.pages = 1
        canvas = maker.c
        self._patches = [
            mock.patch.object(canvas, "drawString", side_effect=self._string(canvas.drawString)),
            mock.patch.object(canvas, "linkURL", side_effect=lambda *a, **k: self.links.append((a, k))),
            mock.patch.object(canvas, "skew", side_effect=lambda *a: self.skews.append(a)),
            mock.patch.object(canvas, "rect", side_effect=lambda *a, **k: self.rects.append((a, k))),
            mock.patch.object(canvas, "line", side_effect=lambda *a, **k: self.lines.append(a)),
            mock.patch.object(canvas, "showPage", side_effect=self._page(canvas.showPage)),
        ]

    def _string(self, real):
        def draw(x, y, value, *a, **k):
            canvas = self.maker.c
            self.strings.append((x, y, value, canvas._fontname, canvas._fontsize, canvas._fillColorObj))
            return real(x, y, value, *a, **k)

        return draw

    def _page(self, real):
        def show(*a, **k):
            self.pages += 1
            return real(*a, **k)

        return show

    def __enter__(self):
        for patch in self._patches:
            patch.start()
        return self

    def __exit__(self, *exc):
        for patch in self._patches:
            patch.stop()

    def width(self, entry):
        return self.maker.c.stringWidth(entry[2], entry[3], entry[4])

    def body(self):
        """Strings inside the text area (not the header box above it or the footer below)."""
        return [s for s in self.strings if 100 < s[1] < 700]

    def find(self, value):
        shaped = rtl.shape(value)
        return [s for s in self.strings if s[2] == shaped]


def render(*blocks, heading="", pages_before=0):
    maker = renderer.PDFMaker(whole_code="PR-01-02", title="ت", date="1405/07/07")
    maker.draw_header()
    maker.c.showPage()
    maker._header_drawn = True
    maker.first_page_initialized = True
    maker.current_y = maker.page_height - maker.margin - maker.header_gap
    with Drawn(maker) as drawn:
        maker.add_rich(heading, doc(*blocks))
    return maker, drawn


class StyleTests(SimpleTestCase):
    def test_font_size_and_colour_per_run(self):
        _, drawn = render(para(text("بزرگ", {"type": "textStyle", "attrs": {"fontSize": 24, "color": "#dc2626"}}), text(" عادی")))
        [big] = drawn.find("بزرگ")
        self.assertEqual((big[3], big[4]), ("Vazir", 24))
        for got, want in zip(rgb(big), (0xDC, 0x26, 0x26)):
            self.assertAlmostEqual(got, want / 255, places=3)
        normal = [s for s in drawn.body() if s is not big]
        self.assertEqual(normal[0][4], 12)
        self.assertEqual(rgb(normal[0]), (0, 0, 0))

    def test_bold_italic_underline_and_strike_stack_on_one_run(self):
        _, drawn = render(para(text("همه", {"type": "bold"}, {"type": "italic"}, {"type": "underline"}, {"type": "strike"})))
        [run] = drawn.find("همه")
        self.assertEqual(run[3], "Vazir-Bold")
        self.assertEqual(drawn.skews, [(0, 12)], "a real 12 degree slant")
        self.assertEqual(len(drawn.lines), 2, "one underline and one strike-through")
        ys = sorted(line[1] for line in drawn.lines)
        self.assertLess(ys[0], ys[1])
        self.assertEqual(run[:2], (0, 0))
        self.assertAlmostEqual(ys[1] - ys[0], 12 * (0.3 + 0.18), places=2)

    def test_underline_and_strike_sit_under_and_through_an_upright_run(self):
        _, drawn = render(para(text("خط", {"type": "underline"}), text(" و "), text("خط", {"type": "strike"})))
        runs = drawn.find("خط")
        self.assertEqual(len(runs), 2)
        under, through = sorted(drawn.lines, key=lambda l: l[1])
        baseline = runs[0][1]
        self.assertLess(under[1], baseline)
        self.assertGreater(through[1], baseline)
        self.assertEqual(drawn.skews, [], "no slant without italic")

    def test_runs_of_a_line_follow_each_other_right_to_left_without_gaps(self):
        _, drawn = render(para(text("اول "), text("دوم ", {"type": "bold"}), text("سوم")))
        first, second, third = sorted(drawn.body(), key=lambda s: -s[0])
        self.assertAlmostEqual(first[0] + drawn.width(first), RIGHT, places=2)
        self.assertAlmostEqual(second[0] + drawn.width(second), first[0], places=2)
        self.assertAlmostEqual(third[0] + drawn.width(third), second[0], places=2)

    def test_a_link_is_clickable_blue_and_underlined(self):
        _, drawn = render(para(text("پیوند", {"type": "link", "attrs": {"href": "https://example.com/a"}})))
        [(args, kwargs)] = drawn.links
        self.assertEqual(args[0], "https://example.com/a")
        x0, y0, x1, y1 = args[1]
        [run] = drawn.find("پیوند")
        self.assertAlmostEqual(x1, RIGHT, places=2)
        self.assertLess(y0, run[1])
        self.assertGreater(y1, run[1])
        self.assertAlmostEqual(rgb(run)[2], 0xED / 255, delta=0.1)
        self.assertTrue(any(l[1] < run[1] for l in drawn.lines), "underlined")

    def test_an_explicit_colour_wins_over_the_link_colour(self):
        marks = ({"type": "link", "attrs": {"href": "https://x.io"}}, {"type": "textStyle", "attrs": {"color": "#16a34a"}})
        _, drawn = render(para(text("سبز", *marks)))
        [run] = drawn.find("سبز")
        self.assertAlmostEqual(rgb(run)[1], 0xA3 / 255, places=2)
        self.assertEqual(len(drawn.links), 1)

    def test_headings_are_bold_and_sized_by_level(self):
        blocks = [{"type": "heading", "attrs": {"level": n}, "content": [text(f"س{n}")]} for n in (1, 2, 3)]
        _, drawn = render(*blocks)
        sizes = {s[2]: (s[3], s[4]) for s in drawn.body()}
        self.assertEqual([sizes[rtl.shape(f"س{n}")] for n in (1, 2, 3)], [("Vazir-Bold", 18), ("Vazir-Bold", 16), ("Vazir-Bold", 14)])

    def test_the_block_heading_is_bold_14(self):
        _, drawn = render(para(text("متن")), heading="۲-شرح")
        [heading] = drawn.find("۲-شرح")
        self.assertEqual((heading[3], heading[4]), ("Vazir-Bold", 14))
        [body] = drawn.find("متن")
        self.assertLess(body[1], heading[1])


class AlignmentTests(SimpleTestCase):
    def extents(self, drawn):
        lines = {}
        for s in drawn.body():
            low, high = lines.get(s[1], (1e9, -1e9))
            lines[s[1]] = (min(low, s[0]), max(high, s[0] + drawn.width(s)))
        return [lines[y] for y in sorted(lines, reverse=True)]

    def test_right_is_the_default_and_ragged_on_the_left(self):
        _, drawn = render(para(text(LOREM * 3 + "پایان")))
        lines = self.extents(drawn)
        self.assertGreater(len(lines), 2)
        for _, high in lines:
            self.assertAlmostEqual(high, RIGHT, places=2)
        self.assertGreater(len({round(low) for low, _ in lines}), 1)

    def test_justify_fills_every_line_but_the_last(self):
        _, drawn = render(para(text(LOREM * 4), textAlign="justify"))
        lines = self.extents(drawn)
        self.assertGreater(len(lines), 3)
        for low, high in lines[:-1]:
            self.assertAlmostEqual(low, LEFT, delta=0.05)
            self.assertAlmostEqual(high, RIGHT, delta=0.05)
        self.assertAlmostEqual(lines[-1][1], RIGHT, places=2)
        self.assertGreater(lines[-1][0], LEFT + 5, "the last line stays ragged")

    def test_a_hard_break_ends_a_justified_line_ragged(self):
        _, drawn = render(para(text("کوتاه"), {"type": "hardBreak"}, text("خط دوم"), textAlign="justify"))
        for _, high in self.extents(drawn):
            self.assertAlmostEqual(high, RIGHT, places=2)

    def test_centre_and_left(self):
        _, drawn = render(para(text("وسط"), textAlign="center"))
        [(low, high)] = self.extents(drawn)
        self.assertAlmostEqual((low + high) / 2, (LEFT + RIGHT) / 2, delta=0.05)
        _, drawn = render(para(text("چپ"), textAlign="left"))
        [(low, _)] = self.extents(drawn)
        self.assertAlmostEqual(low, LEFT, delta=0.05)

    def test_indent_moves_the_right_edge_and_narrows_the_lines(self):
        _, drawn = render(para(text(LOREM * 3), indent=2))
        for _, high in self.extents(drawn):
            self.assertAlmostEqual(high, RIGHT - 2 * richtext.INDENT_STEP, places=2)


class ListTests(SimpleTestCase):
    def test_bullets_and_numbers_sit_at_the_right_edge_and_the_text_is_inset(self):
        _, drawn = render(
            {"type": "bulletList", "content": [item(para(text("اول")), {"type": "bulletList", "content": [item(para(text("زیر")))]}), item(para(text("دوم")))]},
            {"type": "orderedList", "attrs": {"start": 3}, "content": [item(para(text("سه"))), item(para(text("چهار")))]},
        )
        marker = lambda value: [s for s in drawn.body() if s[2] == rtl.shape(value)]
        bullets = marker("•")
        self.assertEqual(len(bullets), 2)
        for bullet in bullets:
            self.assertAlmostEqual(bullet[0] + drawn.width(bullet), RIGHT, places=2)
        [dash] = marker("–")
        self.assertAlmostEqual(dash[0] + drawn.width(dash), RIGHT - richtext.MARKER_GAP, places=2)
        [first] = drawn.find("اول")
        self.assertAlmostEqual(first[0] + drawn.width(first), RIGHT - richtext.MARKER_GAP, places=2)
        [nested] = drawn.find("زیر")
        self.assertAlmostEqual(nested[0] + drawn.width(nested), RIGHT - 2 * richtext.MARKER_GAP, places=2)
        self.assertEqual(len(marker("3.")), 1)
        self.assertEqual(len(marker("4.")), 1)
        [three] = drawn.find("سه")
        self.assertEqual(marker("3.")[0][1], three[1], "the marker shares its item's baseline")

    def test_a_long_item_wraps_inside_its_inset(self):
        _, drawn = render({"type": "bulletList", "content": [item(para(text(LOREM * 2)))]})
        rows = {}
        for s in drawn.body():
            if s[2] != rtl.shape("•"):
                rows.setdefault(s[1], []).append(s[0] + drawn.width(s))
        self.assertGreater(len(rows), 1)
        for highs in rows.values():
            self.assertAlmostEqual(max(highs), RIGHT - richtext.MARKER_GAP, places=2)


class FlowTests(SimpleTestCase):
    def test_a_page_break_starts_a_new_page(self):
        _, drawn = render(para(text("قبل")), {"type": "pageBreak"}, para(text("بعد")))
        self.assertEqual(drawn.pages, 2)
        self.assertGreater(drawn.find("قبل")[0][1], 700 - 60)
        self.assertGreater(drawn.find("بعد")[0][1], 700 - 60)

    def test_long_text_flows_over_pages_and_stays_inside_the_text_area(self):
        _, drawn = render(*[para(text(LOREM * 3)) for _ in range(32)])
        self.assertGreaterEqual(drawn.pages, 3)
        for s in drawn.body():
            self.assertGreaterEqual(s[1], richtext.BOTTOM)
            self.assertGreaterEqual(s[0], LEFT - 0.01)
            self.assertLessEqual(s[0] + drawn.width(s), RIGHT + 0.01)

    def test_a_heading_is_never_the_last_thing_on_a_page(self):
        filler = [para(text(LOREM * 3)) for _ in range(8)]
        for extra in range(0, 6):
            with self.subTest(extra=extra):
                _, drawn = render(*filler, *[para(text("پر")) for _ in range(extra)],
                                  {"type": "heading", "attrs": {"level": 2}, "content": [text("عنوان")]}, para(text("زیر آن")))
                [heading] = drawn.find("عنوان")
                [after] = drawn.find("زیر آن")
                self.assertGreater(heading[1], after[1], "the heading is above its paragraph")
                self.assertGreater(heading[1] - after[1], 0)
                self.assertLess(heading[1] - after[1], 60, "on the same page as it")

    def test_a_rule_is_a_line_across_the_text_area(self):
        _, drawn = render(para(text("بالا")), {"type": "horizontalRule"}, para(text("پایین")))
        rule = [l for l in drawn.lines if l[0] == LEFT and abs(l[2] - RIGHT) < 0.01 and l[1] == l[3]]
        self.assertEqual(len(rule), 1)
        self.assertLess(drawn.find("پایین")[0][1], rule[0][1])
        self.assertGreater(drawn.find("بالا")[0][1], rule[0][1])

    def test_an_empty_document_prints_only_the_heading(self):
        _, drawn = render(heading="فقط عنوان")
        self.assertEqual([s[2] for s in drawn.body()], [rtl.shape("فقط عنوان")])
        _, drawn = render()
        self.assertEqual(drawn.body(), [])

    def test_the_cursor_moves_on_so_the_next_block_does_not_overlap(self):
        maker, drawn = render(para(text("متن")))
        [run] = drawn.find("متن")
        self.assertLess(maker.current_y, run[1])
        self.assertEqual(maker.idx_texts, 2)


class WrapTests(SimpleTestCase):
    def words(self, runs):
        return "".join(t for t, _ in runs).split()

    def test_every_word_survives_in_order(self):
        source = [f"واژه{i}" for i in range(80)]
        atoms = richtext._atoms(para(text(" ".join(source))), richtext.Style())
        lines = richtext._wrap(atoms, 120)
        self.assertGreater(len(lines), 5)
        self.assertEqual([w for runs, _ in lines for w in self.words(runs)], source)
        for runs, _ in lines:
            self.assertLessEqual(sum(richtext._width(t, s) for t, s in runs), 120.01)

    def test_a_word_wider_than_the_line_is_cut(self):
        atoms = richtext._atoms(para(text("ب" * 60)), richtext.Style())
        lines = richtext._wrap(atoms, 50)
        self.assertGreater(len(lines), 1)
        self.assertEqual("".join(t for runs, _ in lines for t, _ in runs), "ب" * 60)

    def test_mixed_sizes_share_a_line_and_the_line_is_as_tall_as_the_largest(self):
        big = {"type": "textStyle", "attrs": {"fontSize": 28}}
        node = para(text("کوچک "), text("بزرگ", big), text(" کوچک"))
        result = richtext._paragraph(node, width=500, right_offset=0, base=richtext.Style())
        self.assertEqual(len(result.lines), 1)
        self.assertAlmostEqual(result.lines[0].height, 28 * richtext.LEADING)

    def test_latin_and_digits_keep_their_order_inside_persian(self):
        _, drawn = render(para(text("کد PR-01-02 در سال 1404")))
        self.assertTrue(any("PR-01-02" in s[2] for s in drawn.body()))


class TableTests(SimpleTestCase):
    def test_cells_are_boxed_in_reading_order_and_the_header_is_shaded(self):
        _, drawn = render(table(
            [cell(para(text("الف")), header=True), cell(para(text("ب")), header=True)],
            [cell(para(text("یک"))), cell(para(text("دو")))],
        ))
        boxes = [r for r in drawn.rects if r[0][2] and r[0][3] and r[0][0] >= LEFT - 0.01 and r[0][2] < 400]
        self.assertEqual(len(boxes), 4)
        shaded = [r for r in boxes if r[1].get("fill") == 1]
        self.assertEqual(len(shaded), 2)
        [alef] = drawn.find("الف")
        [be] = drawn.find("ب")
        self.assertGreater(alef[0], be[0], "the first column is at the right")
        [one] = drawn.find("یک")
        self.assertAlmostEqual(one[0] + drawn.width(one), RIGHT - richtext.CELL_PAD, places=2)

    def test_column_widths_follow_colwidth_when_every_cell_has_one(self):
        first = [{"type": "tableCell", "attrs": {"colwidth": [100]}, "content": [para()]}, {"type": "tableCell", "attrs": {"colwidth": [300]}, "content": [para()]}]
        _, drawn = render({"type": "table", "content": [{"type": "tableRow", "content": first}]})
        widths = sorted(r[0][2] for r in drawn.rects if 0 < r[0][2] < 520)
        self.assertAlmostEqual(widths[1] / widths[0], 3.0, places=2)
        self.assertAlmostEqual(sum(widths), RIGHT - LEFT, places=2)

    def test_a_long_table_continues_on_the_next_page_without_splitting_short_rows(self):
        rows = [[cell(para(text(f"ردیف {i}"))), cell(para(text("x")))] for i in range(60)]
        _, drawn = render(table(*rows))
        self.assertGreaterEqual(drawn.pages, 2)
        for s in drawn.body():
            self.assertGreaterEqual(s[1], richtext.BOTTOM)
        self.assertEqual(len(drawn.find("ردیف 59")), 1)

    def test_a_row_taller_than_a_page_splits_and_loses_no_line(self):
        words = [f"کلمه{i}" for i in range(900)]
        _, drawn = render(table([cell(para(text(" ".join(words)))), cell(para(text("کنار")))]))
        self.assertGreaterEqual(drawn.pages, 2)
        seen = []
        for s in sorted(drawn.body(), key=lambda s: (-drawn.pages, -s[1])):
            seen.append(s)
        self.assertEqual(len(drawn.find("کنار")), 1)
        for s in drawn.body():
            self.assertGreaterEqual(s[1], richtext.BOTTOM)
        drawn_words = sum(len(s[2].split()) for s in drawn.body() if s[2] != rtl.shape("کنار"))
        self.assertGreaterEqual(drawn_words, 900)

    def test_cell_content_stays_inside_its_cell(self):
        _, drawn = render(table([cell(para(text(LOREM * 2))), cell(para(text("کوتاه")))]))
        column = (RIGHT - LEFT) / 2
        for s in drawn.body():
            if s[2] != rtl.shape("کوتاه"):
                self.assertGreaterEqual(s[0], RIGHT - column + richtext.CELL_PAD - 0.01 - column)
                self.assertLessEqual(s[0] + drawn.width(s), RIGHT - richtext.CELL_PAD + 0.01)

    def test_lists_and_headings_work_inside_a_cell(self):
        _, drawn = render(table([cell(
            {"type": "heading", "attrs": {"level": 3}, "content": [text("سرتیتر")]},
            {"type": "bulletList", "content": [item(para(text("مورد")))]},
        )]))
        self.assertEqual(len(drawn.find("سرتیتر")), 1)
        self.assertEqual(len(drawn.find("مورد")), 1)


class ThroughTheProviderTests(SimpleTestCase):
    def pdf(self, blocks):
        data = PdfInput(
            title="عنوان", whole_code="PR-01-02", review="02", date="1405/07/07",
            logo=fixture_bytes("logo.png"), qr=fixture_bytes("logo.png"), blocks=tuple(blocks),
        )
        return provider.deliver_to_pdf(data, invariant=True)

    def test_a_rich_block_makes_a_pdf_with_a_live_link(self):
        pdf = self.pdf([(provider.RICH, ("۱-هدف", doc(para(text("لینک", {"type": "link", "attrs": {"href": "https://example.com/x"}})))))])
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn(b"https://example.com/x", pdf)
        self.assertIn(b"/URI", pdf)

    def test_rich_and_legacy_blocks_can_share_a_document(self):
        pdf = self.pdf([(provider.TEXT, "۱-هدف\nمتن قدیمی\n"), (provider.RICH, ("۲-شرح", doc(para(text("متن جدید")))))])
        self.assertTrue(pdf.startswith(b"%PDF-"))

    def test_rendering_is_deterministic(self):
        blocks = [(provider.RICH, ("ت", doc(para(text(LOREM * 5), textAlign="justify"), table([cell(para(text("x")))]))))]
        self.assertEqual(self.pdf(blocks), self.pdf(blocks))
