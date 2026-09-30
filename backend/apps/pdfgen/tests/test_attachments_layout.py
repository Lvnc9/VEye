"""The ضمائم rows (owner's change, 2026-09-29): the QR sits at the far left edge of the
page on the caption's line; the caption stays at the right margin. (2026-09-30: no «کد …»
beside the caption any more.)"""
from io import BytesIO
from unittest import mock

from django.test import SimpleTestCase, override_settings
from PIL import Image

from apps.pdfgen import renderer
from apps.pdfgen.qr import qr_png

from . import cases as C

ROW = ["فرم درخواست", "PR-01-01", qr_png(f"{C.FRONTEND}/verify/PR-01-01")]
LONG = ["یک عنوان بسیار طولانی برای پیوست " * 8, "PR-02-01", qr_png(f"{C.FRONTEND}/verify/PR-02-01")]


def draw(*rows):
    maker = renderer.PDFMaker(whole_code="PR-01-01", title="ت", date="1405/07/07")
    maker.draw_header()
    with mock.patch.object(maker.c, "drawImage", wraps=maker.c.drawImage) as image, \
            mock.patch.object(maker.c, "drawString", wraps=maker.c.drawString) as string:
        maker.attachments([list(r) for r in rows])
    # (x, y, width, height) of each QR; (x, y, text) of each string in the body
    # (the page's header above y = 700 and its footer below y = 100 are not part of the rows).
    images = [(c.args[1], c.args[2], c.kwargs["width"], c.kwargs["height"]) for c in image.call_args_list]
    strings = [c.args for c in string.call_args_list if 100 < c.args[1] < 700]
    return maker, images, strings


@override_settings(FRONTEND_BASE_URL=C.FRONTEND)
class AttachmentRowTests(SimpleTestCase):
    def test_the_qrs_black_modules_touch_the_left_margin(self):
        maker, images, _ = draw(ROW)
        [(x, y, width, height)] = images
        pixels = Image.open(BytesIO(ROW[2])).size[0]
        quiet = width * renderer.QR_QUIET_PX / pixels
        self.assertAlmostEqual(x + quiet, maker.margin, places=3)
        self.assertLess(x, maker.margin)  # only white hangs over the margin

    def test_the_qr_is_vertically_centred_on_the_caption_line(self):
        maker, images, strings = draw(ROW)
        (_, y, _, height), = images
        centre = y + height / 2
        caption_y = strings[0][1]
        self.assertAlmostEqual(caption_y + 3.5, centre, delta=1.0)

    def test_the_caption_is_flush_right_and_nothing_else_is_written_on_the_row(self):
        maker, _, strings = draw(ROW)
        right = maker.page_width - maker.margin
        caption = renderer.PDFMaker.prepare_rtl(maker, ROW[0])
        self.assertEqual(len(strings), 1)  # the caption only — no «کد …» beside it
        self.assertAlmostEqual(strings[0][0] + maker.c.stringWidth(caption, "Vazir", 10), right, places=2)
        self.assertNotIn("PR-01-01", [args[2] for args in strings])

    def test_the_caption_may_use_every_point_left_of_the_qr(self):
        # ~435 pt of text: it wrapped while «کد …» took ~55 pt of the ~455 pt free, and fits now.
        maker, images, strings = draw(["سلام " * 19, "PR-01-01", ROW[2]])
        self.assertEqual(len({args[1] for args in strings}), 1)  # one line

    def test_a_long_caption_wraps_and_never_reaches_the_qr(self):
        maker, images, strings = draw(LONG)
        quiet_free_right = images[0][0] + images[0][2]
        self.assertGreater(len({args[1] for args in strings}), 1)  # several lines
        for args in strings:
            self.assertGreater(args[0], quiet_free_right)

    def test_rows_do_not_overlap_and_all_qrs_share_the_left_edge(self):
        maker, images, _ = draw(ROW, LONG, ROW)
        ys = [image[1] for image in images]
        self.assertEqual(len(ys), 3)
        self.assertGreater(ys[0] - ys[1], 50)
        self.assertGreater(ys[1] - ys[2], 50)
        self.assertEqual(len({image[0] for image in images}), 1)

    def test_a_missing_qr_draws_a_placeholder_at_the_margin(self):
        maker = renderer.PDFMaker(whole_code="PR-01-01", title="ت")
        maker.draw_header()
        with mock.patch.object(maker.c, "rect", wraps=maker.c.rect) as rect:
            maker.attachments([["ب", "PR-01-01", None]])
        self.assertEqual(rect.call_args_list[-1].args[0], maker.margin)
