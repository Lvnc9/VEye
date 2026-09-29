"""The whitelist for the rich body of a تشریحی بلند block (rich_content.py) and how it
travels through the designer's API (2026-09-29)."""
import copy

from django.test import SimpleTestCase

from apps.core.constants import DocumentGroup

from . import content, rich_content
from .models import Document
from .test_designer import LONG, DesignerTestCase, long_block

Refused = rich_content.RichContentError


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


def rich(*blocks):
    return {"v": 1, "doc": {"type": "doc", "content": list(blocks)}}


def cell(kind="tableCell", *content, **attrs):
    node = {"type": kind, "content": list(content) or [para()]}
    if attrs:
        node["attrs"] = attrs
    return node


def table(*rows):
    return {"type": "table", "content": [{"type": "tableRow", "content": list(row)} for row in rows]}


class AcceptTests(SimpleTestCase):
    def test_every_supported_thing_is_kept(self):
        doc = rich(
            {"type": "heading", "attrs": {"level": 2, "textAlign": "center"}, "content": [text("عنوان")]},
            para(
                text("پررنگ", {"type": "bold"}, {"type": "italic"}, {"type": "underline"}, {"type": "strike"}),
                text("بزرگ", {"type": "textStyle", "attrs": {"fontSize": 20, "color": "#DC2626"}}),
                text("پیوند", {"type": "link", "attrs": {"href": "https://example.com/x?y=1"}}),
                {"type": "hardBreak"},
                textAlign="justify",
                indent=2,
            ),
            {"type": "bulletList", "content": [{"type": "listItem", "content": [para(text("الف")), {
                "type": "orderedList", "attrs": {"start": 3}, "content": [{"type": "listItem", "content": [para(text("ب"))]}]}]}]},
            table([cell("tableHeader", para(text("ستون")), colwidth=[120]), cell("tableHeader")], [cell(), cell()]),
            {"type": "horizontalRule"},
            {"type": "pageBreak"},
        )
        cleaned = rich_content.clean(doc)["doc"]["content"]
        self.assertEqual([n["type"] for n in cleaned], ["heading", "paragraph", "bulletList", "table", "horizontalRule", "pageBreak"])
        self.assertEqual(cleaned[0]["attrs"], {"textAlign": "center", "level": 2})
        marks = cleaned[1]["content"][1]["marks"]
        self.assertEqual(marks, [{"type": "textStyle", "attrs": {"fontSize": 20, "color": "#dc2626"}}], "colour is lower-cased")
        self.assertEqual(cleaned[1]["attrs"], {"textAlign": "justify", "indent": 2})
        self.assertEqual(cleaned[2]["content"][0]["content"][1]["attrs"], {"start": 3})
        self.assertEqual(cleaned[3]["content"][0]["content"][0]["attrs"], {"colwidth": [120]})

    def test_defaults_and_unknown_attributes_are_dropped(self):
        cleaned = rich_content.clean(rich(para(text("x"), textAlign="right", indent=0, class_="evil", id="a")))
        self.assertEqual(cleaned["doc"]["content"], [{"type": "paragraph", "content": [{"type": "text", "text": "x"}]}])

    def test_an_empty_document_and_empty_text_are_fine(self):
        self.assertEqual(rich_content.clean(rich())["doc"]["content"], [])
        self.assertEqual(rich_content.clean(rich(para(text(""))))["doc"]["content"], [{"type": "paragraph"}])

    def test_a_table_cell_without_content_gets_an_empty_paragraph(self):
        node = {"type": "tableCell"}
        cleaned = rich_content.clean(rich(table([node])))
        self.assertEqual(cleaned["doc"]["content"][0]["content"][0]["content"][0]["content"], [{"type": "paragraph"}])


class RefuseTests(SimpleTestCase):
    def refuses(self, doc, fragment=None):
        with self.assertRaises(Refused) as caught:
            rich_content.clean(doc)
        self.assertRegex(str(caught.exception), r"[؀-ۿ]")  # Persian
        return str(caught.exception)

    def test_wrong_envelope(self):
        for bad in (None, [], {"v": 2, "doc": {"type": "doc"}}, {"v": 1}, {"v": 1, "doc": {"type": "page"}}, {"v": 1, "doc": []}):
            with self.subTest(bad=bad):
                self.refuses(bad)

    def test_unknown_nodes_are_refused_not_dropped(self):
        for node in ({"type": "image", "attrs": {"src": "x"}}, {"type": "codeBlock"}, {"type": "blockquote", "content": []},
                     {"type": "taskList"}, {"type": "script"}, "text", None, 5):
            with self.subTest(node=node):
                self.refuses(rich(node))

    def test_unknown_marks_are_refused(self):
        for mark in ({"type": "highlight"}, {"type": "code"}, {"type": "subscript"}, "bold", {"type": "bold", "attrs": {"x": 1}}):
            with self.subTest(mark=mark):
                self.refuses(rich(para(text("x", mark))))

    def test_a_repeated_mark_is_refused(self):
        self.refuses(rich(para(text("x", {"type": "bold"}, {"type": "bold"}))))

    def test_links_must_be_http_https_or_mailto(self):
        for href in ("javascript:alert(1)", "data:text/html,x", "ftp://x", "//evil", "http://a b", "https://x\"onclick", "", None, 5):
            with self.subTest(href=href):
                self.refuses(rich(para(text("x", {"type": "link", "attrs": {"href": href}}))))
        for href in ("http://a.b", "HTTPS://a.b/c?d=e#f", "mailto:a@b.co"):
            rich_content.clean(rich(para(text("x", {"type": "link", "attrs": {"href": href}}))))

    def test_font_size_and_colour_ranges(self):
        def styled(**attrs):
            return rich(para(text("x", {"type": "textStyle", "attrs": attrs})))

        for attrs in ({"fontSize": 7}, {"fontSize": 33}, {"fontSize": "12"}, {"fontSize": True}, {"color": "#123456"},
                      {"color": "red"}, {"color": "javascript:1"}, {"color": 5}):
            with self.subTest(attrs=attrs):
                self.refuses(styled(**attrs))
        rich_content.clean(styled(fontSize=8))
        rich_content.clean(styled(fontSize=32, color="#000000"))

    def test_alignment_indent_and_heading_level(self):
        for attrs in ({"textAlign": "top"}, {"indent": 7}, {"indent": -1}, {"indent": "2"}, {"indent": True}):
            with self.subTest(attrs=attrs):
                self.refuses(rich(para(**attrs)))
        for level in (0, 4, "1", None):
            with self.subTest(level=level):
                self.refuses(rich({"type": "heading", "attrs": {"level": level}}))
        self.refuses(rich({"type": "heading"}))

    def test_lists_are_bounded_and_well_formed(self):
        deep = {"type": "bulletList", "content": [{"type": "listItem", "content": [para(), {"type": "bulletList", "content": [{
            "type": "listItem", "content": [para(), {"type": "bulletList", "content": [{"type": "listItem", "content": [para(), {
                "type": "bulletList", "content": [{"type": "listItem", "content": [para()]}]}]}]}]}]}]}]}
        self.refuses(rich(deep))
        self.refuses(rich({"type": "bulletList", "content": []}))
        self.refuses(rich({"type": "bulletList", "content": [para(text("not an item"))]}))
        self.refuses(rich({"type": "orderedList", "attrs": {"start": 0}, "content": [{"type": "listItem", "content": [para()]}]}))

    def test_tables_are_bounded_and_rectangular(self):
        self.refuses(rich({"type": "table", "content": []}))
        self.refuses(rich(table([cell(), cell()], [cell()])), "columns")
        self.refuses(rich(table([cell() for _ in range(rich_content.MAX_COLUMNS + 1)])))
        self.refuses(rich(table(*[[cell()] for _ in range(rich_content.MAX_ROWS + 1)])))
        self.refuses(rich(table([cell(colspan=2)])))
        self.refuses(rich(table([cell(rowspan=2)])))
        self.refuses(rich(table([cell(colwidth=[5])])))
        self.refuses(rich(table([cell(colwidth=[100, 100])])))
        self.refuses(rich({"type": "table", "content": [{"type": "tableRow", "content": []}]}))
        self.refuses(rich({"type": "table", "content": [para()]}))
        # a table can't hold a table, a rule or a page break
        self.refuses(rich(table([cell("tableCell", table([cell()]))])))
        self.refuses(rich(table([cell("tableCell", {"type": "horizontalRule"})])))

    def test_size_limits(self):
        self.refuses(rich(para(text("ا" * (rich_content.MAX_TEXT + 1)))))
        many = [para(text("x")) for _ in range(rich_content.MAX_NODES)]
        self.refuses(rich(*many))

    def test_nesting_depth(self):
        node = para(text("x"))
        for _ in range(rich_content.MAX_DEPTH + 2):
            node = {"type": "table", "content": [{"type": "tableRow", "content": [cell("tableCell", node)]}]}
        self.refuses(rich(node))

    def test_input_is_not_mutated(self):
        doc = rich(para(text("x", {"type": "textStyle", "attrs": {"color": "#DC2626"}}), textAlign="right"))
        before = copy.deepcopy(doc)
        rich_content.clean(doc)
        self.assertEqual(doc, before)


class TextTests(SimpleTestCase):
    def test_plain_text_keeps_paragraphs_lists_and_cells_apart(self):
        doc = rich_content.clean(rich(
            para(text("یک"), {"type": "hardBreak"}, text("دو")),
            {"type": "bulletList", "content": [{"type": "listItem", "content": [para(text("الف"))]}, {"type": "listItem", "content": [para(text("ب"))]}]},
            table([cell("tableCell", para(text("x"))), cell("tableCell", para(text("y")))]),
        ))
        self.assertEqual(rich_content.plain_text(doc), "یک\nدو\nالف\nب\nx\ty")

    def test_is_blank(self):
        self.assertTrue(rich_content.is_blank(None))
        self.assertTrue(rich_content.is_blank(rich(para(), para(text("  ")))))
        self.assertFalse(rich_content.is_blank(rich(para(text("x")))))
        self.assertFalse(rich_content.is_blank(rich({"type": "horizontalRule"})))
        self.assertFalse(rich_content.is_blank(rich(table([cell()]))))


class RichThroughTheApiTests(DesignerTestCase):
    def rich_block(self, doc, **extra):
        return long_block("۲-شرح", "ignored", ["ignored too"], rich=doc, **extra)

    def test_it_round_trips_and_body_mirrors_the_text(self):
        doc = rich(para(text("متن غنی", {"type": "bold"})), para(text("خط دوم")))
        saved = self.save([self.rich_block(doc)])
        block = saved["sections"][0]
        self.assertEqual(block["rich"], doc)
        self.assertEqual(block["body"], "متن غنی\nخط دوم", "body mirrors the rich text; the marker body is replaced")
        self.assertEqual(block["extra_boxes"], [])
        self.assertEqual(self.get_content()["sections"][0]["rich"], doc)

    def test_a_block_without_rich_stays_marker_text_and_reports_none(self):
        saved = self.save([long_block("ت", "**متن**", ["کادر"])])
        self.assertIsNone(saved["sections"][0]["rich"])
        self.assertEqual(saved["sections"][0]["body"], "**متن**")

    def test_null_rich_means_legacy(self):
        saved = self.save([self.rich_block(None)])
        self.assertIsNone(saved["sections"][0]["rich"])
        self.assertEqual(saved["sections"][0]["body"], "ignored")

    def test_the_server_stores_the_cleaned_document(self):
        saved = self.save([self.rich_block(rich(para(text("x", {"type": "textStyle", "attrs": {"color": "#DC2626"}}), textAlign="right")))])
        self.assertEqual(
            saved["sections"][0]["rich"]["doc"]["content"],
            [{"type": "paragraph", "content": [{"type": "text", "text": "x", "marks": [{"type": "textStyle", "attrs": {"color": "#dc2626"}}]}]}],
        )

    def test_a_document_outside_the_whitelist_is_refused_with_a_persian_message(self):
        response = self.put([self.rich_block(rich({"type": "image", "attrs": {"src": "x"}}))])
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("پشتیبانی نمی", str(response.data))
        self.assertEqual(self.get_content()["sections"], [], "nothing was saved")

    def test_oversized_json_is_refused(self):
        huge = rich(*[para(text("ا" * 2000)) for _ in range(300)])
        response = self.put([self.rich_block(huge)])
        self.assertEqual(response.status_code, 400)

    def test_a_new_revision_copies_the_rich_body(self):
        doc = rich(para(text("متن غنی")), table([cell(), cell()]))
        self.save([self.rich_block(doc)])
        self.doc.refresh_from_db()
        # A draft can't be revised, so copy directly, as create_revision does.
        target = Document.objects.create(
            group=DocumentGroup.INSTRUCTION, category=self.doc.category, title=self.doc.title,
            number=99, revision=2, created_by=self.author,
        )
        content.copy_content(self.doc, target)
        copied = target.sections.get(type=LONG)
        self.assertEqual(copied.content["rich"]["doc"]["content"][0]["content"][0]["text"], "متن غنی")
