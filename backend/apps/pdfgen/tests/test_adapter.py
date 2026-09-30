"""Postgres -> PdfInput: what the database rows turn into before rendering."""
import shutil
import tempfile
from datetime import date, datetime
from datetime import timezone as dt_timezone
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from apps.core.constants import (
    DocumentCategory,
    DocumentStatus,
    SectionType,
    SignOffRole,
)
from apps.documents.models import (
    ChangeTableRow,
    Document,
    ResponsibilityRow,
    Section,
    SignOff,
)
from apps.organization import tree
from apps.organization.models import Company
from apps.pdfgen import adapter, provider
from apps.pdfgen.qr import qr_png, verify_url

from . import cases as C
from .helpers import LOCMEM_CACHE, _saved_at, create_case, fixture_bytes, make_author

MEDIA = tempfile.mkdtemp(prefix="veye-adapter-media-")


def tearDownModule():
    shutil.rmtree(MEDIA, ignore_errors=True)


def make_doc(author, **overrides):
    values = dict(
        category=DocumentCategory.INSIDE, title="سند", group="PROCEDURE", number=1, revision=1,
        status=DocumentStatus.UNDER_CONTROL, created_by=author, content_saved_at=_saved_at(date(2025, 4, 8)),
    )
    values.update(overrides)
    return Document.objects.create(**values)


@override_settings(MEDIA_ROOT=MEDIA, FRONTEND_BASE_URL="https://veye.test/", CACHES=LOCMEM_CACHE)
class AdapterTests(TestCase):
    def setUp(self):
        self.author = make_author()

    def blocks(self, document, tag=None):
        blocks = adapter.load(document.pk).blocks
        return [payload for kind, payload in blocks if tag is None or kind == tag]

    # -- header data --------------------------------------------------------

    def test_header_fields(self):
        doc = make_doc(self.author, footnote1="بالا", footnote2="پایین")
        data = adapter.load(doc.pk)
        self.assertEqual(data.whole_code, "PR-01-01")
        self.assertEqual(data.review, "01")
        self.assertEqual(data.title, "سند")
        self.assertEqual((data.upper_footnote, data.lower_footnote), ("بالا", "پایین"))
        self.assertEqual(data.date, "1404/01/19")  # 2025-04-08, like the archived sample

    def test_the_company_name_is_loaded_only_when_the_document_asks_for_it(self):
        root = tree.create_root(name="شرکت نمونه")
        Company.objects.create(pk=1, root=root)
        doc = make_doc(self.author)
        self.assertEqual(adapter.load(doc.pk).company_name, "", "off by default")
        doc.show_company_name = True
        doc.save()
        self.assertEqual(adapter.load(doc.pk).company_name, "شرکت نمونه")
        root.name = "نام تازه"
        root.save()
        self.assertEqual(adapter.load(doc.pk).company_name, "نام تازه", "the chart and the paper never disagree")

    def test_a_document_that_asks_for_the_name_before_a_company_exists_prints_none(self):
        doc = make_doc(self.author, show_company_name=True)
        self.assertEqual(adapter.load(doc.pk).company_name, "")

    def test_date_is_the_local_date_of_the_last_save(self):
        # 22:00 UTC on 1 Farvardin 1404's eve is already the next day in Tehran (+03:30).
        doc = make_doc(self.author, content_saved_at=datetime(2025, 3, 20, 22, 0, tzinfo=dt_timezone.utc))
        self.assertEqual(adapter.load(doc.pk).date, "1404/01/01")

    def test_date_falls_back_to_today_for_a_document_never_saved(self):
        doc = make_doc(self.author, content_saved_at=None)
        self.assertEqual(adapter.load(doc.pk).date, adapter.jalali(timezone.localdate()))

    def test_only_a_superseded_revision_is_marked_obsolete(self):
        # 2026-09-30: no «معتبر» / «منسوخ» cell any more — a superseded revision gets the watermark.
        expected = {
            DocumentStatus.UNDER_CONTROL: False,
            DocumentStatus.OBSOLETE: True,
            DocumentStatus.DRAFT: False,
            DocumentStatus.AWAITING_CONFIRMATION: False,
            DocumentStatus.AWAITING_APPROVAL: False,
        }
        for number, (status, obsolete) in enumerate(expected.items(), start=1):
            doc = make_doc(self.author, number=number, title=f"t{number}", status=status)
            self.assertIs(adapter.load(doc.pk).obsolete, obsolete, status)

    def test_the_sign_off_layout_follows_the_group(self):
        for number, (group, layout) in enumerate(
            {
                "PROCEDURE": provider.CONTROL_TABLE,
                "INSTRUCTION": provider.CONTROL_TABLE,
                "POSTER": provider.STRIP,
                "FORM": provider.STRIP,
            }.items(),
            start=1,
        ):
            doc = make_doc(self.author, number=number, title=f"g{number}", group=group)
            self.assertEqual(adapter.load(doc.pk).signoff_layout, layout, group)

    def test_qr_encodes_the_verify_url_of_the_printed_code(self):
        doc = make_doc(self.author)
        self.assertEqual(verify_url(doc), "https://veye.test/verify/PR-01-01")  # trailing slash tolerated
        self.assertEqual(adapter.load(doc.pk).qr, qr_png("https://veye.test/verify/PR-01-01"))
        other = make_doc(self.author, number=2, title="دیگر")
        self.assertNotEqual(adapter.load(other.pk).qr, adapter.load(doc.pk).qr)

    # -- blocks -------------------------------------------------------------

    def test_short_block_drops_empty_lines_and_ends_each_line_with_newline(self):
        doc = make_doc(self.author)
        Section.objects.create(
            document=doc, position=0, type=SectionType.SHORT_EXPLANATION,
            content={"lines": ["1-هدف", "", "دوم\r\n", ""]},
        )
        self.assertEqual(self.blocks(doc, provider.TEXT), ["1-هدف\nدوم\n\n"])

    def test_long_block_is_heading_newline_body(self):
        doc = make_doc(self.author)
        Section.objects.create(
            document=doc, position=0, type=SectionType.LONG_EXPLANATION,
            content={"heading": "2-شرح", "body": "خط اول\r\nخط دوم", "extra_boxes": []},
        )
        self.assertEqual(self.blocks(doc, provider.TEXT), ["2-شرح\nخط اول\nخط دوم"])

    def test_long_block_extra_boxes_are_printed_as_paragraphs(self):
        # V_1.0 dropped them (deliver_convert.py:119); the product owner chose to print them.
        doc = make_doc(self.author)
        Section.objects.create(
            document=doc, position=0, type=SectionType.LONG_EXPLANATION,
            content={"heading": "H", "body": "B", "extra_boxes": ["جعبه اول", "", "  ", "جعبه دوم"]},
        )
        self.assertEqual(self.blocks(doc, provider.TEXT), ["H\nB\n\nجعبه اول\n\nجعبه دوم"])

    def test_extra_box_with_an_empty_body_takes_the_body_slot(self):
        doc = make_doc(self.author)
        Section.objects.create(
            document=doc, position=0, type=SectionType.LONG_EXPLANATION,
            content={"heading": "H", "body": "", "extra_boxes": ["فقط جعبه"]},
        )
        self.assertEqual(self.blocks(doc, provider.TEXT), ["H\nفقط جعبه"])

    def test_a_rich_long_block_goes_to_the_rich_layout_with_its_heading(self):
        doc = make_doc(self.author)
        rich = {"v": 1, "doc": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "متن غنی"}]}]}}
        Section.objects.create(
            document=doc, position=0, type=SectionType.LONG_EXPLANATION,
            content={"heading": "2-شرح\r\n", "body": "متن غنی", "extra_boxes": [], "rich": rich},
        )
        Section.objects.create(
            document=doc, position=1, type=SectionType.LONG_EXPLANATION,
            content={"heading": "3-قدیمی", "body": "**متن**", "extra_boxes": []},
        )
        blocks = adapter.load(doc.pk).blocks
        self.assertEqual(blocks[0], (provider.RICH, ("2-شرح\n", rich["doc"])))
        self.assertEqual(blocks[1], (provider.TEXT, "3-قدیمی\n**متن**"), "a block without `rich` prints as before")

    def test_a_rich_block_with_an_empty_document_still_prints_its_heading(self):
        doc = make_doc(self.author)
        Section.objects.create(
            document=doc, position=0, type=SectionType.LONG_EXPLANATION,
            content={"heading": "فقط عنوان", "body": "", "extra_boxes": [], "rich": {"v": 1, "doc": {"type": "doc", "content": []}}},
        )
        [(tag, payload)] = adapter.load(doc.pk).blocks
        self.assertEqual((tag, payload[0]), (provider.RICH, "فقط عنوان"))

    def test_blocks_keep_their_page_order(self):
        doc = make_doc(self.author)
        kinds = [SectionType.CHANGES_TABLE, SectionType.SHORT_EXPLANATION, SectionType.ATTACHMENT]
        for position, kind in enumerate(kinds):
            Section.objects.create(document=doc, position=position, type=kind, content={"lines": ["x"]})
        self.assertEqual(
            [tag for tag, _ in adapter.load(doc.pk).blocks],
            [provider.TABLE, provider.TEXT, provider.ATTACHMENTS],
        )

    def test_a_responsibilities_row_prints_domain_unit_and_purpose(self):
        doc = make_doc(self.author)
        section = Section.objects.create(document=doc, position=0, type=SectionType.RESPONSIBILITIES)
        for i, (domain, unit, text) in enumerate(
            [
                ("IT", "هوش مصنوعی", "نگهداری داده‌ها"),
                ("", "واحد مستقل", "پیگیری"),  # a company without حوزه
                ("IT", "توسعه", ""),  # nothing after the واحد
                ("", "", "الف:  سمت: مدیر\nشرح قدیمی"),  # a converted old row: just its text
                ("", "", ""),  # says nothing: not printed
            ]
        ):
            ResponsibilityRow.objects.create(section=section, position=i, domain_name=domain, unit_name=unit, text=text)
        (lines,) = self.blocks(doc, provider.RESPONSIBILITIES)
        self.assertEqual(
            lines,
            [
                "حوزه IT  واحد هوش مصنوعی  جهت نگهداری داده‌ها",
                "واحد واحد مستقل  جهت پیگیری",
                "حوزه IT  واحد توسعه",
                "الف:  سمت: مدیر\nشرح قدیمی",
            ],
        )

    def test_the_printed_names_are_the_stored_snapshots_not_the_charts_current_names(self):
        root = tree.create_root(name="شرکت")
        Company.objects.create(pk=1, root=root)
        unit = tree.create_node(kind="UNIT", name="نام قدیم", parent=root)
        doc = make_doc(self.author)
        section = Section.objects.create(document=doc, position=0, type=SectionType.RESPONSIBILITIES)
        ResponsibilityRow.objects.create(section=section, position=0, unit=unit, unit_name="نام قدیم", text="کار")
        unit.name = "نام تازه"
        unit.save()
        (lines,) = self.blocks(doc, provider.RESPONSIBILITIES)
        self.assertEqual(lines, ["واحد نام قدیم  جهت کار"])

    def test_markers_in_a_node_name_do_not_restyle_the_line(self):
        doc = make_doc(self.author)
        section = Section.objects.create(document=doc, position=0, type=SectionType.RESPONSIBILITIES)
        ResponsibilityRow.objects.create(section=section, position=0, unit_name="R--D**", text="**مهم** است")
        (lines,) = self.blocks(doc, provider.RESPONSIBILITIES)
        self.assertEqual(lines, ["واحد RD  جهت **مهم** است"])

    def test_a_block_with_no_rows_prints_nothing_at_all(self):
        doc = make_doc(self.author)
        Section.objects.create(document=doc, position=0, type=SectionType.RESPONSIBILITIES)
        self.assertEqual(self.blocks(doc, provider.RESPONSIBILITIES), [])

    def test_attachments_carry_caption_target_code_and_target_qr(self):
        doc = make_doc(self.author)
        target = make_doc(self.author, number=2, title="هدف")
        section = Section.objects.create(document=doc, position=0, type=SectionType.ATTACHMENT)
        section.attachment_items.create(position=0, caption="فرم", target=target)
        (items,) = self.blocks(doc, provider.ATTACHMENTS)
        self.assertEqual(items, [["فرم", "PR-02-01", qr_png("https://veye.test/verify/PR-02-01")]])

    def test_change_history_is_numbered_across_every_earlier_revision(self):
        author = self.author
        revisions = []
        previous = None
        for revision in (1, 2, 3):
            doc = make_doc(author, revision=revision, previous_revision=previous,
                           content_saved_at=_saved_at(date(2025, revision, 1)))
            section = Section.objects.create(document=doc, position=0, type=SectionType.CHANGES_TABLE)
            for i in range(2):
                ChangeTableRow.objects.create(
                    section=section, position=i, date=date(2025, revision, 1 + i), text=f"r{revision}-{i}"
                )
            revisions.append(doc)
            previous = doc
        data = adapter.load(revisions[2].pk)
        # V_1.0 fetched only the immediately previous revision; revision 3 lost revision 1's rows.
        self.assertEqual([row[2] for row in data.previous_changes], ["r1-0", "r1-1", "r2-0", "r2-1"])
        self.assertEqual([row[0] for row in data.previous_changes], ["1", "2", "3", "4"])
        (current,) = self.blocks(revisions[2], provider.TABLE)
        self.assertEqual([row[0] for row in current], ["5", "6"])
        self.assertEqual(current[0][1], adapter.jalali(date(2025, 3, 1)))

    # -- images, on a fresh/empty media root -------------------------------

    def test_sign_offs_map_to_their_rows_and_absent_ones_are_blank(self):
        doc = create_case("sample", {}, self.author)
        data = adapter.load(doc.pk)
        self.assertEqual((data.creater.name, data.creater.position), C.SIGNERS["creater"])
        self.assertEqual((data.approver.name, data.approver.position), C.SIGNERS["approver"])
        self.assertTrue(data.confirmer.image)

        bare = make_doc(self.author, number=9, title="بدون امضا")
        data = adapter.load(bare.pk)
        for block in (data.creater, data.confirmer, data.approver):
            self.assertEqual(block, provider.SignatureBlock())

    def test_missing_files_on_an_empty_media_root_become_placeholders_not_crashes(self):
        with tempfile.TemporaryDirectory() as empty:
            with override_settings(MEDIA_ROOT=empty):
                doc = make_doc(self.author, number=5, title="بی‌فایل")
                # Rows point at files that do not exist on this (fresh) volume.
                Document.objects.filter(pk=doc.pk).update(logo=f"logos/{doc.pk}/gone.png")
                SignOff.objects.create(
                    document=doc, role=SignOffRole.CREATER, name="ن", position="س", signature="signatures/gone.png"
                )
                data = adapter.load(doc.pk)
                self.assertIsNone(data.logo)
                self.assertIsNone(data.creater.image)
                self.assertEqual(data.creater.name, "ن")
                pdf = provider.deliver_to_pdf(data)
                self.assertTrue(pdf.startswith(b"%PDF-"))

    def test_corrupt_image_is_ignored_not_fatal(self):
        doc = make_doc(self.author, number=6, title="خراب")
        doc.logo.save("x.png", ContentFile(b"this is not an image"), save=True)
        self.assertIsNone(adapter.load(doc.pk).logo)

    def test_only_png_logos_are_drawn(self):
        doc = make_doc(self.author, number=7, title="jpg")
        doc.logo.save("x.jpg", ContentFile(fixture_bytes("logo.png")), save=True)
        # Same rule as V_1.0 (`".png" in path`): anything else gets the placeholder.
        Document.objects.filter(pk=doc.pk).update(logo=doc.logo.name.replace(".png", ".jpg"))
        self.assertIsNone(adapter.load(doc.pk).logo)

    def test_transparent_signature_is_flattened_onto_white(self):
        # The renderer draws signatures unmasked, so transparency would print black.
        rgba = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
        rgba.putpixel((5, 5), (0, 0, 200, 255))
        buffer = BytesIO()
        rgba.save(buffer, format="PNG")
        doc = make_doc(self.author, number=8, title="شفاف")
        signoff = SignOff(document=doc, role=SignOffRole.CREATER, name="ن", position="س")
        signoff.signature.save("s.png", ContentFile(buffer.getvalue()), save=True)
        image = Image.open(BytesIO(adapter.load(doc.pk).creater.image))
        self.assertEqual(image.mode, "RGB")
        self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
        self.assertEqual(image.getpixel((5, 5)), (0, 0, 200))

    def test_opaque_signature_passes_through_unchanged(self):
        doc = create_case("sample", {}, self.author)
        self.assertEqual(adapter.load(doc.pk).creater.image, fixture_bytes("sign_creater.png"))
