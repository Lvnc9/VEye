"""The port against the original.

tests/fixtures/golden/*.pdf were produced by V_1.0's own renderer and Provider
(tools/make_golden_from_v1.py). Each case is loaded into Postgres here, read back
through the adapter, and rendered by the port; the bytes must be identical. That
covers the layout algorithm and its quirks (character-count wrapping, the twice
drawn last-page furniture, footers over content on later pages, text_merge...),
the rich-text markers, Persian shaping/bidi, the change-table history, and the
mapping from database rows to what V_1.0's JSON carried.
"""
import shutil
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from apps.pdfgen import adapter, provider

from . import cases as C
from .helpers import FIXTURES, LOCMEM_CACHE, create_case

GOLDEN = FIXTURES / "golden"
MEDIA = tempfile.mkdtemp(prefix="veye-golden-media-")


def tearDownModule():
    shutil.rmtree(MEDIA, ignore_errors=True)


@override_settings(MEDIA_ROOT=MEDIA, FRONTEND_BASE_URL=C.FRONTEND, CACHES=LOCMEM_CACHE)
class GoldenPdfTests(TestCase):
    def render(self, key):
        document = create_case(key, {})
        data = adapter.load(document.pk)
        return provider.deliver_to_pdf(data, preview=C.CASES[key].get("preview", False), invariant=True)

    def check(self, key):
        expected = (GOLDEN / f"{key}.pdf").read_bytes()
        actual = self.render(key)
        self.assertEqual(len(actual), len(expected), f"{key}: size differs")
        self.assertTrue(actual == expected, f"{key}: bytes differ from V_1.0's output")

    def test_sample_with_three_signatures_and_footnotes(self):
        self.check("sample")

    def test_bare_document_empty_attachment_block_and_placeholders(self):
        self.check("bare")

    def test_every_block_type_history_and_page_overflow(self):
        self.check("full")

    def test_watermarked_preview_of_a_draft(self):
        self.check("draft_preview")
