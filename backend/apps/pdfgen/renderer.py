"""The PDF renderer — a port of V_1.0's other_folder/to_make_pdf.py.

The layout algorithm is the product owner's and is reproduced as written, quirks
included (see .claude/docs/08-pdf-engine.md for the list). What changed:

  * images (logo, QR codes, signatures) arrive as PNG *bytes* instead of paths on
    the author's machine / S3 URLs, and the PDF is built in memory and returned
    as bytes;
  * fonts are registered once at startup (apps.pdfgen.apps.PdfgenConfig.ready)
    rather than by every PDFMaker, and the module keeps no mutable global state;
  * the crash-level bugs are fixed (each is marked "V_1.0 crashed" below);
  * two text-losing quirks are fixed — decided by the owner on 2026-09-28, once the
    designer's live paper made them visible: body lines wrap by their real width
    (`wrap_body_line`, V_1.0 wrapped by character count so 90-170 character lines
    ran off the page), and `text_merge` keeps every word (`merge_words`, V_1.0
    dropped the word that forced a wrap and duplicated chunks of repeated words).
    Both are marked "Fixed 2026-09-28" below.

`get_display` MUST come from bidi.algorithm (python-bidi==0.6.11): the Rust
`bidi.get_display` shipped alongside it orders mixed digits/Latin/Persian
differently, which would silently change every issued PDF.
"""
import re
from io import BytesIO

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from . import header, richtext

#: Boxed page header (owner's request, 2026-09-29; see header.py). The box hangs
#: from `HEADER_MARGIN` below the top edge; text on pages >= 2 starts `HEADER_GAP`
#: below `margin` (V_1.0: a 50 pt gap under a small header).
HEADER_MARGIN = 40
HEADER_GAP = 98

#: Width in pixels of the white border of a QR PNG (qr.py: border=4 boxes x box_size=10).
QR_QUIET_PX = 40


# --------------------------------------------------------------------------
# Fixed 2026-09-28 (owner's decision): the two text-losing quirks. Pure functions,
# so the golden-file tool can put exactly these into V_1.0's code for the oracle.
# --------------------------------------------------------------------------

_MARKER_SPLIT = re.compile(r"(\*\*.*?\*\*|~~.*?~~|--.*?--)")
_MARKER_OF = {"bold": "**", "italic": "~~", "underline": "--"}
_SPACES = re.compile(r"(\s+)")


def marker_runs(line):
    """(text, style) runs of one line, split the way draw_rtl_styled_line splits it."""
    runs = []
    for fragment in _MARKER_SPLIT.split(line):
        if not fragment:
            continue
        if fragment.startswith("**") and fragment.endswith("**") and len(fragment) >= 4:
            runs.append((fragment[2:-2], "bold"))
        elif fragment.startswith("~~") and fragment.endswith("~~") and len(fragment) >= 4:
            runs.append((fragment[2:-2], "italic"))
        elif fragment.startswith("--") and fragment.endswith("--") and len(fragment) >= 4:
            runs.append((fragment[2:-2], "underline"))
        else:
            runs.append((fragment, "normal"))
    return runs


def wrap_body_line(line, width, measure):
    """Break one body line into lines no wider than `width` points.

    `measure(text, style)` is the drawn width of a fragment in that style. A line
    that fits is returned as it is — so a document without long lines prints
    exactly as before. Otherwise the logical text is broken between words (a word
    wider than the line is cut between characters) *before* it is shaped and
    reordered; a style marker that spans a break is closed and reopened, so every
    line keeps its pairs.
    """
    runs = marker_runs(line)
    if sum(measure(text, style) for text, style in runs) <= width:
        return [line]

    atoms = []  # (text, style), words and the spaces between them
    for text, style in runs:
        atoms.extend((piece, style) for piece in _SPACES.split(text) if piece)

    lines, current, used = [], [], 0.0
    for text, style in atoms:
        size = measure(text, style)
        if text.isspace():
            if current and used + size <= width:
                current.append((text, style))
                used += size
            elif current:
                lines.append(current)
                current, used = [], 0.0
            continue
        if used + size <= width:
            current.append((text, style))
            used += size
            continue
        if current:
            lines.append(current)
            current, used = [], 0.0
        if size <= width:
            current, used = [(text, style)], size
            continue
        piece = ""
        for char in text:  # one word wider than the line
            if piece and measure(piece + char, style) > width:
                lines.append([(piece, style)])
                piece = ""
            piece += char
        current, used = [(piece, style)], measure(piece, style)
    if current:
        lines.append(current)

    out = []
    for atoms_of_line in lines:
        while atoms_of_line and atoms_of_line[-1][0].isspace():
            atoms_of_line = atoms_of_line[:-1]
        merged = []
        for text, style in atoms_of_line:
            if merged and merged[-1][1] == style:
                merged[-1] = (merged[-1][0] + text, style)
            else:
                merged.append((text, style))
        out.append("".join(
            f"{_MARKER_OF[style]}{text}{_MARKER_OF[style]}" if style in _MARKER_OF else text
            for text, style in merged
        ))
    return out


def merge_words(text, limit=180):
    """V_1.0's `text_merge`, keeping every word: chunks of at most `limit`
    characters, each starting with the space V_1.0 put there. V_1.0 compared with
    `i is group[-1]` (identity, so a repeated short word flushed early and was
    printed twice) and never flushed the last chunk when its word forced a wrap
    (so that word was lost)."""
    length = ""
    big = []
    for word in text.split(" "):
        if len(length + " " + word) <= limit:
            length = length + " " + word
        else:
            big.append(length)
            length = word
    big.append(length)
    return big


def _image(data):
    """An ImageReader over PNG bytes, or None when there is no image. V_1.0 tested
    `os.path.exists(path) and ".png" in path` at every draw site; that check now
    lives where the bytes are loaded (adapter.py), so None means "draw the black
    placeholder box", exactly as a missing/non-PNG file did."""
    if not data:
        return None
    return ImageReader(BytesIO(data))


class HeaderFooterCanvas(canvas.Canvas):
    """
    A custom Canvas that automatically:
      1) Draws a footnote on every page (logo, footnote texts, page number).
      2) Draws a small header from page 2 onward.
      3) Optionally draws a “پیش نمایش” watermark if preview_mode=True.
    """

    def __init__(
        self, *args,
        logo=None,
        font_name="Vazir",
        title_text="بیانیه خط مشی سیستم مدیریت یکپارچه (IMS)",
        code_text="ST-03-06",
        qr=None,
        up_foot="معاونت برنامه ریزی و توسعه اقتصادی",
        low_foot="با احترام نظیر کارکنان مورد نظر",
        preview_mode=False,
        **kwargs
    ):
        """
        Args:
            logo (bytes | None): PNG bytes of the main logo.
            font_name (str): Main Persian font name (e.g. “Vazir”).
            title_text (str): The text for the small header on pages >= 2.
            code_text (str): Bold code text on the right of the small header.
            qr (bytes | None): PNG bytes of the QR code for the footnote.
            up_foot (str): Upper footnote text.
            low_foot (str): Lower footnote text.
            preview_mode (bool): If True, draws “پیش نمایش” watermark behind every page.
        """
        super().__init__(*args, **kwargs)
        # Decoded once: the footnote and small header repeat on every page.
        self.logo = _image(logo)
        self.font_name = font_name
        self.title_text = title_text
        self.code_text = code_text
        self.qr = _image(qr)
        self.up_foot = up_foot
        self.low_foot = low_foot

        # New attribute for watermark previews
        self.preview_mode = preview_mode

    def showPage(self):
        """
        On each page “showPage” event:
          1) Draw the footnote on the current page (always).
          2) Advance to the next page.
          3) If preview_mode=True, draw the watermark on every page.
          4) If the new page is >=2, draw the small header in #6c7482.
        """
        # Draw footnote on the current page
        self._draw_footnote_current_page()
        super().showPage()

        # After page number increments:
        if self.preview_mode:
            # Draw watermark behind everything on this new page
            self._draw_preview_on_current_page()

        if self.getPageNumber() >= 2:
            # Draw the small header in #6c7482
            self._draw_small_header()
            self.setFillColorRGB(0, 0, 0)

    def save(self):
        """
        On final save call:
         1) If preview_mode=True, draw the watermark on the final page behind content.
         2) Draw footnote on the final page.
         3) Save.
        """
        if self.preview_mode:
            self._draw_preview_on_current_page()
        self._draw_footnote_current_page()
        super().save()

    def _draw_preview_on_current_page(self):
        """
        Draws “پیش نمایش” watermark on every page (if preview_mode=True),
        using a more visible gray color so it is easier to see.
        """
        if not self.preview_mode:
            return

        self.saveState()
        # Slightly darker gray
        self.setFillColorRGB(0.8, 0.8, 0.8)
        page_width, page_height = self._pagesize
        # Place watermark in the center and rotate
        self.translate(page_width / 2, page_height / 2)
        self.rotate(45)

        # Prepare RTL text
        preview_str = "پیش نمایش"
        reshaped_preview = arabic_reshaper.reshape(preview_str)
        bidi_preview = get_display(reshaped_preview)

        # Attempt bold if available
        if (self.font_name + "-Bold") in pdfmetrics.getRegisteredFontNames():
            self.setFont(self.font_name + "-Bold", 60)
        else:
            self.setFont(self.font_name, 60)

        self.drawCentredString(0, 0, bidi_preview)
        self.restoreState()

    def _draw_footnote_current_page(self):
        """
        Draws the footnote:
          - Left logo in #6c7482,
          - up_foot and low_foot text lines,
          - A page counter (“صفحه X”),
          - And the QR code on the right side.
        Then resets color to black.
        """
        self.setFillColorRGB(108/255.0, 116/255.0, 130/255.0)

        margin_left = 40
        margin_bottom = 20
        margin_right = 40

        footer_y = margin_bottom
        footer_x = margin_left
        logo_width = 50
        logo_height = 50

        # Draw the left logo
        if self.logo is not None:
            self.drawImage(
                self.logo,
                footer_x,
                footer_y,
                width=logo_width,
                height=logo_height,
                mask="auto"
            )
        else:
            # Placeholder if logo not found
            self.rect(footer_x, footer_y, logo_width, logo_height, fill=1)

        text_x = footer_x + logo_width + 8
        text_y = footer_y + (logo_height / 3) + 25
        self.setFont(self.font_name, 10)

        # Upper foot
        reshaped_text = arabic_reshaper.reshape(self.up_foot)
        bidi_text = get_display(reshaped_text)
        self.drawString(text_x, text_y, bidi_text)

        # Lower foot
        another_reshaped_text = arabic_reshaper.reshape(self.low_foot)
        another_bidi_text = get_display(another_reshaped_text)
        self.drawString(text_x, text_y - 15, another_bidi_text)

        # Page counter
        page_number = self.getPageNumber()
        page_counter_str = f"صفحه {page_number}"
        reshaped_pc = arabic_reshaper.reshape(page_counter_str)
        bidi_pc = get_display(reshaped_pc)
        self.drawString(text_x, text_y - 38, bidi_pc)

        # QR code on the right
        qr_width = 70
        qr_height = 70
        qr_x = self._pagesize[0] - margin_right - qr_width
        qr_y = footer_y
        if self.qr is not None:
            self.drawImage(
            self.qr,
            qr_x,
            qr_y,
            width=qr_width,
            height=qr_height,
            mask="auto"
        )
        else:
            # Placeholder if QR not found
            self.rect(qr_x, qr_y, qr_width, qr_height, fill=1)

        self.setFillColorRGB(0, 0, 0)

    def _draw_small_header(self):
        """
        Draws the boxed header (header.py) on pages >= 2 — the same box as page 1
        (owner's request, 2026-09-29; V_1.0 drew a small unboxed strip here).
        Then resets the fill colour to black.
        """
        rows = getattr(self, "header_rows", None) or header.meta_rows(self.code_text, "", "")
        width = self._pagesize[0]
        header.draw_boxed_header(
            self,
            title=self.title_text,
            rows=rows,
            logo=self.logo,
            font_name=self.font_name,
            x0=HEADER_MARGIN,
            x1=width - HEADER_MARGIN,
            top=self._pagesize[1] - HEADER_MARGIN,
        )
        self.setFillColorRGB(0, 0, 0)


class PDFMaker:
    """
    - Adds large header on first page (in black).
    - Adds smaller header + footnotes on subsequent pages (#6c7482).
    - Page-breaking logic for text and tables.
    - Optional “پیش نمایش” watermark behind all pages if preview_mode=True.
    """

    def __init__(
        self,
        font_name="Vazir",
        logo=None,
        header_gap=HEADER_GAP,
        qr=None,
        title="بیانیه خط مشی سیستم مدیریت یکپارچه (IMS)",
        date="",
        whole_code="",
        upper_foot="",
        lower_foot="",
        preview_mode=False,
        invariant=False,
    ):
        """
        Args:
            font_name (str): Base name for the registered Persian font ("Vazir";
                "Vazir-Bold" is derived from it). Registered at startup.
            logo (bytes | None): PNG bytes of the primary logo, used in footnotes/headers.
            header_gap (int): Gap below small header on subsequent pages.
            qr (bytes | None): PNG bytes of the document's QR code (footnote).
            preview_mode (bool): If True, draws a watermark “پیش نمایش” behind each page.
            invariant (bool): Reproducible output (fixed dates/ids) — tests only.
        """
        self.font_name = font_name
        self.logo = logo
        self.header_gap = header_gap
        self.qr = qr
        self.title = title
        self.date = date
        self.whole_code = whole_code
        self.upper_foot = upper_foot
        self.lower_foot = lower_foot
        self.preview_mode = preview_mode

        self.page_width, self.page_height = A4
        self.margin = 40

        self.idx_texts = 1

        # Instantiate our custom Canvas, writing into memory.
        self._buffer = BytesIO()
        self.c = HeaderFooterCanvas(
            self._buffer,
            pagesize=A4,
            invariant=1 if invariant else 0,
            logo=self.logo,
            font_name=self.font_name,
            title_text=self.title,
            code_text=self.whole_code,
            qr=self.qr,
            up_foot=self.upper_foot,
            low_foot=self.lower_foot,
            preview_mode=self.preview_mode  # pass it down
        )

        self.current_y = self.page_height - self.margin

        self.c.setFillColorRGB(0, 0, 0)
        self.c.setStrokeColorRGB(0, 0, 0)
        self.page_break_threshold = 60

        # Flag to track if we've placed the header & table on page 1
        self.first_page_initialized = False

    def set_preview_mode(self, enable_preview: bool):
        """
        Toggle the preview watermark for subsequent pages.
        """
        self.preview_mode = enable_preview
        # Reflect the change in the underlying Canvas
        self.c.preview_mode = enable_preview

    def initialize_first_page(self):
        """Set up the first page with the large header & control table, once."""
        if not self.first_page_initialized:
            self.draw_header()
            #self.draw_control_table()
            self.c.showPage()
            self.current_y = self.page_height - self.margin - self.header_gap
            self.first_page_initialized = True

    def prepare_rtl(self, text):
        """Perform Arabic reshaping and bidi for Persian RTL output."""
        text_str = str(text)
        reshaped_text = arabic_reshaper.reshape(text_str)
        return get_display(reshaped_text)

    def _check_page_break(self, needed_space):
        """Check if we have enough space for 'needed_space'; if not, we do a new page."""
        if self.current_y - needed_space < self.page_break_threshold:
            self._new_page()

    def _new_page(self):
        """Force new page, place the small header, reset current_y."""
        self.c.showPage()
        self.current_y = self.page_height - self.margin - self.header_gap
        self.c.setFillColorRGB(0, 0, 0)

    def draw_header(
        self,
        details=None,
        top_details_height=40,
        bottom_header_height=60,
        header_bg_color=(0.95, 0.95, 0.95),
        code_font_size=10,
        title_font_size=16,
        title_text="بیانیه خط مشی سیستم مدیریت یکپارچه (IMS)"
    ):
        """
        The boxed header on page 1 (header.py; owner's request, 2026-09-29). The
        styling arguments are V_1.0's and no longer used. V_1.0 drew the header a
        second time from `initialize_first_page`; once is enough.
        """
        if not getattr(self, "_header_drawn", False):
            if details is None:
                # V_1.0 split the code *before* this guard, so a caller that passed
                # `details` still crashed on a code without three parts.
                third = self.whole_code.split('-')[2]
                details = header.meta_rows(self.whole_code, third, self.date)
            self.c.header_rows = list(details)
            header.draw_boxed_header(
                self.c,
                title=self.title,
                rows=details,
                logo=self.c.logo,
                font_name=self.font_name,
                x0=self.margin,
                x1=self.page_width - self.margin,
                top=self.page_height - self.margin,
            )
            self._header_drawn = True

        self.current_y = self.page_height - self.margin - self.header_gap
        return self.current_y

    def draw_rtl_styled_line(self, x_right, y, text, font_size):
        """
        Draw a single line of RTL text supporting inline markers:
        **bold** => bold
        ~~italic~~ => italic
        --underline-- => underline
    
        If an italic font is not available, we simulate italic by applying a skew transform.
        We've increased the skew angle to 15 degrees for a more noticeable effect.
        """
        import re
    
        # Matches **something**, ~~something~~, or --something--
        pattern = r'(\*\*.*?\*\*|~~.*?~~|--.*?--)'
        fragments = re.split(pattern, text)
        fragments_info = []
        total_width = 0
    
        for frag in fragments:
            if frag.startswith('**') and frag.endswith('**'):
                content = frag[2:-2]
                style = "bold"
                # Use bold font if available; else fallback to normal
                font_to_use = (
                    self.font_name + "-Bold"
                    if (self.font_name + "-Bold") in pdfmetrics.getRegisteredFontNames()
                    else self.font_name
                )
            elif frag.startswith('~~') and frag.endswith('~~'):
                content = frag[2:-2]
                style = "italic"
                # If an italic variant is registered, use it;
                # otherwise, we'll do a skew transform below.
                font_to_use = (
                    self.font_name + "-Italic"
                    if (self.font_name + "-Italic") in pdfmetrics.getRegisteredFontNames()
                    else self.font_name
                )
            elif frag.startswith('--') and frag.endswith('--'):
                content = frag[2:-2]
                style = "underline"
                font_to_use = self.font_name
            else:
                content = frag
                style = "normal"
                font_to_use = self.font_name
    
            # Reshape for RTL
            content_rtl = self.prepare_rtl(content)
            # Measure width of this fragment
            frag_width = self.c.stringWidth(content_rtl, font_to_use, font_size)
            total_width += frag_width
    
            fragments_info.append({
                "text": content_rtl,
                "style": style,
                "font": font_to_use,
                "width": frag_width
            })
    
        # Right-align the entire line
        x_start = x_right - total_width
    
        for frag in fragments_info:
            style_type = frag["style"]
            text_width = frag["width"]
            font_name_here = frag["font"]
            text_here = frag["text"]
    
            # Push a new graphics state on the canvas.
            self.c.saveState()
    
            # If italic style is needed but no italic font was found, apply a 15-degree skew
            if style_type == "italic" and font_name_here == self.font_name:
                # 15 degrees in radians => tan(15°) ~ 0.2679
                self.c.skew(0.2679, 0)
    
            self.c.setFont(font_name_here, font_size)
            self.c.drawString(x_start, y, text_here)
    
            # For underline, draw a line below after rendering text
            if style_type == "underline":
                underline_y = y - 2
                self.c.line(x_start, underline_y, x_start + text_width, underline_y)
    
            self.c.restoreState()
            x_start += text_width
    def add_body_text(self, body_text, line_height=20, font_size=12, not_body=False):
        """
        Add multiline RTL text, wrapping lines at 70 characters, with optional style markers (**bold**, etc.).
        New paragraphs are preserved when multiple newlines (e.g. "\n\n") are encountered.
        Will initialize the first page if not done, and break pages as needed.
        """
        self.initialize_first_page()
        self._check_page_break(60)
        
        # Split the input text by newlines without filtering out empty lines to preserve paragraphs
        raw_lines = body_text.split("\n")
        # Fixed 2026-09-28: wrapped by width (V_1.0: 70-character chunks past 170).
        wrapped_lines = self._wrap_body(raw_lines, not_body, font_size)

        # Now process these wrapped lines
        for idx, (source, piece, line) in enumerate(wrapped_lines):
            self._check_page_break(60)
            x_right = self.page_width - self.margin
            
            if line == "":
                # If the line is empty, simply decrease the y position for vertical spacing
                self.current_y -= line_height
                continue

            # See if this line contains style markers
            if "**" in line or "~~" in line or "--" in line:
                self.draw_rtl_styled_line(x_right, self.current_y, line, font_size)
            # Apply special handling for first or second line if not_body is True
            elif not_body and source == 0:
                bold_font = (self.font_name + "-Bold" if (self.font_name + "-Bold")
                             in pdfmetrics.getRegisteredFontNames()
                             else self.font_name)
                self.c.setFont(bold_font, font_size + 2)
                line_rtl = self.prepare_rtl(line)
                self.c.drawRightString(x_right, self.current_y, line_rtl)
            elif not_body and source == 1 and piece == 0:
                self.c.setFont(self.font_name, font_size)
                line_rtl = self.prepare_rtl(line)
                self.c.drawRightString(x_right, self.current_y, "\t\t\t" + line_rtl)
            else:
                self.c.setFont(self.font_name, font_size)
                line_rtl = self.prepare_rtl(line)
                self.c.drawRightString(x_right, self.current_y, line_rtl)

            self.current_y -= line_height - 5

        self.current_y -= 30
        self.idx_texts += 1
        return self.current_y

    def add_rich(self, heading, doc):
        """A تشریحی بلند block written in the designer's rich editor (owner's request,
        2026-09-29): its heading, then a Word-like body — see richtext.py. Blocks with the
        old marker text still go through `add_body_text`."""
        richtext.render(self, heading, doc)

    def add_table(self, data, col_widths, row_height=30, font_size=10):
        """
        Render a table-like structure in black text, with potential page breaks.
        """
        self._check_page_break(100)
        self.initialize_first_page()
        if not data:
            return self.current_y

        line_rtl = self.prepare_rtl("جدول تغییرات:")
        x_right = self.page_width - self.margin
        bold_font = (self.font_name + "-Bold" if (self.font_name + "-Bold")
                     in pdfmetrics.getRegisteredFontNames()
                     else self.font_name)
        self.c.setFont(bold_font, 14)
        self.c.drawRightString(x_right, self.current_y, line_rtl)
        self.current_y -= 10

        self.c.setFont(self.font_name, font_size)
        total_width = sum(col_widths)
        start_x = self.page_width - self.margin - total_width

        for row_index, row in enumerate(data):
            self._check_page_break(row_height)
            # Light gray for first row
            if row_index == 0:
                self.c.setFillColorRGB(0.9, 0.9, 0.9)
                self.c.rect(start_x, self.current_y - row_height, total_width, row_height, fill=1, stroke=0)
            self.c.setFillColorRGB(0, 0, 0)

            self.c.line(start_x, self.current_y, start_x + total_width, self.current_y)
            x = start_x
            for width, value in zip(col_widths, row):
                self.c.line(x, self.current_y, x, self.current_y - row_height)
                text = self.prepare_rtl(value)
                text_width = self.c.stringWidth(text, self.font_name, font_size)
                text_x = x + (width - text_width) / 2
                text_y = self.current_y - (row_height / 2) - (font_size / 2)
                self.c.drawString(text_x, text_y, text)
                x += width

            self.c.line(x, self.current_y, x, self.current_y - row_height)
            self.current_y -= row_height

        self.c.line(start_x, self.current_y, start_x + total_width, self.current_y)
        self.current_y -= 50
        self.idx_texts += 1

        return self.current_y


    @staticmethod
    def text_merge(text, limit=180):
        """
        Utility that wraps text in 90-character chunks. 
        This can help in splitting text for multiline.
        Fixed 2026-09-28: keeps every word (see merge_words).
        """
        return merge_words(text, limit)

    def _body_width(self, text, style, font_size, heading):
        """Drawn width of a fragment of a body line, as add_body_text draws it."""
        bold = self.font_name + "-Bold"
        has_bold = bold in pdfmetrics.getRegisteredFontNames()
        if heading:
            return self.c.stringWidth(self.prepare_rtl(text), bold if has_bold else self.font_name, font_size + 2)
        face = bold if style == "bold" and has_bold else self.font_name
        return self.c.stringWidth(self.prepare_rtl(text), face, font_size)

    def _wrap_body(self, raw_lines, not_body, font_size):
        """[(source line, piece, text)] — every source line wrapped to the page's
        text width. Fixed 2026-09-28 (see wrap_body_line)."""
        width = self.page_width - 2 * self.margin
        wrapped = []
        for source, line in enumerate(raw_lines):
            if not line:
                # Preserve empty line to create a paragraph break
                wrapped.append((source, 0, ""))
                continue
            # The heading line (not_body, first line, no markers) is drawn bold and larger.
            heading = not_body and source == 0 and not ("**" in line or "~~" in line or "--" in line)
            pieces = wrap_body_line(line, width, lambda text, style: self._body_width(text, style, font_size, heading))
            wrapped.extend((source, piece, text) for piece, text in enumerate(pieces))
        return wrapped

    def attachments(self, element, x_offset=30, font_size=12):
        """
        Draw a “ضمائم:” label, then one line per attachment: the caption (with
        optional inline styling) right-aligned at the right margin and the
        document's QR at the far left of the page. (Changed 2026-09-29 at the
        owner's request: V_1.0 put the QR at the right. Changed 2026-09-30: the
        «کد …» that used to sit left of the caption is no longer printed — the
        QR identifies the document.)
        """
        self.initialize_first_page()
        self._check_page_break(200)
    
        # Label "ضمائم:"
        line_rtl = self.prepare_rtl("ضمائم:")
        x_right = self.page_width - self.margin
        bold_font = (self.font_name + "-Bold" if (self.font_name + "-Bold")
                    in pdfmetrics.getRegisteredFontNames()
                    else self.font_name)
        self.c.setFont(bold_font, 14)
        self.c.drawRightString(x_right, self.current_y, line_rtl)
        self.current_y -= 30
    
        # Set normal font for subsequent lines
        self.c.setFont(self.font_name, font_size)
        self.c.setFillColorRGB(0, 0, 0)
    
        # Changed 2026-09-29 (the owner's request): one line per attachment — the
        # caption at the right margin and the QR code at the far left edge of the
        # page on the same line. V_1.0 put the QR at the right, the text to its
        # left and a caption longer than the row ran off the page. The caption
        # takes every point of width left of the QR (2026-09-30: no «کد …»).
        qr_size = 50
        qr_gap = 14
        text_right = self.page_width - self.margin
        lead = 13

        for el in element:
            text, _code, qr = el
            qr_img = _image(qr)
            # The PNG has a white quiet zone (qr.py: 4 boxes of 10 px) that would
            # look like a gap; hang it off the margin so the black modules touch it.
            quiet = 0.0
            if qr_img is not None:
                quiet = qr_size * QR_QUIET_PX / qr_img.getSize()[0]
            qr_x = self.margin - quiet
            text_left = self.margin + qr_size - 2 * quiet + qr_gap

            width = text_right - text_left
            lines = wrap_body_line(text, width, lambda t, style: self._body_width(t, style, 10, False)) or [""]
            pitch = max(60, len(lines) * lead + 20)
            self._check_page_break(pitch - 10)

            centre = self.current_y - 13
            if qr_img is not None:
                self.c.drawImage(qr_img, qr_x, centre - qr_size / 2, width=qr_size, height=qr_size, mask="auto")
            else:
                # Fallback if QR path not found
                self.c.rect(self.margin, centre - qr_size / 2, qr_size, qr_size, fill=1)

            y = centre + (len(lines) - 1) * lead / 2 - 3.5
            for line in lines:
                self.draw_rtl_styled_line(text_right, y, line, 10)
                y -= lead

            self.c.setFont(self.font_name, 12)
            self.current_y -= pitch

        self.current_y -= 20

        self.idx_texts += 1


    def responsibilities(self, element:dict, x_offset=30, font_size=12):
        """
        Draw a “ضمائم:” label, then place a QR at the extreme right
        and the text (with optional inline styling) to the left, right-aligned.
        
        This version properly measures the text width so that the next text
        appears exactly 30 points to the left of the previous text.
        """

        self.initialize_first_page()
        self._check_page_break(200)
    
        # Label "ضمائم:"
        line_rtl = self.prepare_rtl(f"{self.idx_texts})" +"مسئولیت ها:")
        x_right = self.page_width - self.margin
        bold_font = (self.font_name + "-Bold" if (self.font_name + "-Bold")
                    in pdfmetrics.getRegisteredFontNames()
                    else self.font_name)
        self.c.setFont(bold_font, 14)
        self.c.drawRightString(x_right, self.current_y, line_rtl)
        self.current_y -= 10
    
        # Set normal font for subsequent lines
        self.c.setFont(self.font_name, font_size)
        self.c.setFillColorRGB(0, 0, 0)
    
        # Prepare fixed space for QR
        qr_width = 50
        qr_height = 50
        qr_x = self.page_width - self.margin
        qr_y = self.current_y 

        for el in element:
            self._check_page_break(120)
            key, value = el
            # Draw the QR image
            
            qr_x = self.page_width
            qr_y = self.current_y
            
    
            # The main text is drawn first in one line, right-aligned starting at text_right_edge
            text_right_edge = qr_x - x_offset - 10
    
            # Draw the main text
            self.draw_rtl_styled_line(text_right_edge, self.current_y - 30, key, 12)
    
            # Measure how wide that text was (in points)
            text_rtl = self.prepare_rtl(key)
            main_text_width = self.c.stringWidth(text_rtl, self.font_name, 12)
    
            # Now place the 'thin' text 30 points to the left of where the previous text ended
            # Because the drawn text is right-aligned within draw_rtl_styled_line,
            # the "starting X" actually accounts for the total width inside that method.
            # So we subtract the measured width + 30 more points to place it further to the left.
            self.current_y -= 20

            next_text_right_edge = text_right_edge - main_text_width - 5
            value = self.text_merge(value, 100)
            
            i = 0
            if len(value) > 1:
                ext = ""
                for txt in value:
                    if i == 0:
                        ext = "توضیحات: "
                    self.draw_rtl_styled_line(
                        text_right_edge,
                        self.current_y - 30,
                        ext + txt,  # Make text italic
                        12,
                    )
                    self.current_y -= 20
                    i += 1
            else:
                self.draw_rtl_styled_line(
                    text_right_edge,
                    self.current_y - 30,
                    "توضیحات: " + value[0],  # Make text italic
                    12,
                )
                    
            # Adjust the vertical position
            self.current_y -= (qr_height - 30)
            self.c.setFont(self.font_name, 12)
            self.current_y -= 20

        self.current_y -= 60

        self.idx_texts += 1

    def draw_wrapped_centred_text(self, c, x, y, width, height, text, font_name, font_size):
        """
        Used for cell alignment, splitting text into lines that fit inside a given width,
        then drawing them centered vertically/horizontally.
        """
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            new_line = word if current_line == "" else current_line + " " + word
            if stringWidth(new_line, font_name, font_size) <= (width - 4):
                current_line = new_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        total_text_height = len(lines) * font_size
        start_y = y + (height - total_text_height) / 2
        for line in lines:
            rtl_line = self.prepare_rtl(line)
            c.drawCentredString(x + width/2, start_y, rtl_line)
            start_y += font_size

    def draw_header_cell(self, c, x, y, width, height, text, radius=8):
        c.setFillColor(HexColor("#0D47A1"))
        c.setStrokeColor(black)
        c.setLineWidth(1)
        c.roundRect(x, y, width, height, radius, fill=1, stroke=1)
        c.setFillColor(white)
        c.setFont(self.font_name, 10)
        rtl_text = self.prepare_rtl(text)
        c.drawCentredString(x + width/2, y + (height - 10)/2, rtl_text)

    def draw_data_cell(self, c, x, y, width, height, text, wrap=False, radius=8):
        c.setFillColor(white)
        c.setStrokeColor(HexColor("#0D47A1"))
        c.setLineWidth(1)
        c.roundRect(x, y, width, height, radius, fill=1, stroke=1)
        c.setFillColor(black)
        c.setFont(self.font_name, 10)
        if wrap:
            self.draw_wrapped_centred_text(c, x, y, width, height, text, self.font_name, 10)
        else:
            rtl_text = self.prepare_rtl(text)
            c.drawCentredString(x + width/2, y + (height - 10)/2, rtl_text)



    def draw_control_table(self, creater=None, confirmer=None, approver=None, validation="", extra_header=""):
        """`creater` / `confirmer` / `approver` are [name, post, signature PNG bytes]
        — V_1.0's [name, post, signature URL]. V_1.0 defaulted them to shared
        mutable `[]` and then indexed `[0]` (IndexError when omitted)."""
        empty = ["", "", ""]
        creater = creater or empty
        confirmer = confirmer or empty
        approver = approver or empty
        page_width, page_height = A4
        table_left = 50
        header_height = 80
        data_height = 75
        total_data_height = data_height * 3
        total_table_height = header_height + total_data_height - 80
        usable_height = page_height - (2 * self.margin)
        table_top = (page_height + total_table_height) / 2

        x_right = self.page_width - self.margin
        # If extra header text is provided, draw it above the table
        text = "**وضعیت کنترل:**"
        #prepared_text = self.prepare_rtl(text)
        self.draw_rtl_styled_line(
            x_right,
            table_top + header_height + 10,
            text,  # Make text italic
            16,
        )
        table_top -= 40
        extra_header = "\t\t\t" + extra_header
        value = PDFMaker.text_merge(extra_header, 110)
        if len(value) > 1:
            for txt in value:
                self.draw_rtl_styled_line(
                    x_right,
                    table_top + header_height + 10,
                    txt,  # Make text italic
                    14,
                )
                table_top -= 23
        else:
            self.draw_rtl_styled_line(
                x_right,
                table_top + header_height + 10,
                value[0],  # Make text italic
                12,
            )
        self.c.setFont(self.font_name, 12)
        col_widths = [80, 80, 190, 80, 70]
    
        headers = ["وضعیت کنترل", "امضا", "سمت", "نام و نام خانوادگی", "مسئولیت"]
        current_x = table_left
        for i, text in enumerate(headers):
            self.draw_header_cell(self.c, current_x, table_top, col_widths[i], header_height, text, radius=8)
            current_x += col_widths[i]
    
        # Merge cell for “وضعیت کنترل”
        self.draw_data_cell(
            self.c,
            table_left,
            table_top - total_data_height,
            col_widths[0],
            total_data_height,
            validation,
            wrap=False,
            radius=8
        )
    
        # Fill data for each column
        # col0 is merged (above), so we start from col1 onward.
        col1_data = ["", "", ""]
        col2_data = [
            creater[1],
            confirmer[1],
            approver[1],
            
        ]
        col3_data = [creater[0], confirmer[0], approver[0],]
        col4_data = ["تهیه کننده", "تایید کننده", "کننده تصویب"]
    
        for row in range(3):
            cell_y = table_top - header_height - row * data_height + 80
            # Column 1: امضا (where sign will be displayed)
            x1 = table_left + col_widths[0]
            self.draw_data_cell(self.c, x1, cell_y - data_height, col_widths[1], data_height, col1_data[row],
                                wrap=False, radius=8)
    
            # Place the sign if we have an image (the cells in col1_data are empty on purpose)
            signature = _image((creater[2], confirmer[2], approver[2])[row])
            if signature is not None:
                # Calculate a smaller width/height for the image
                sign_width = col_widths[1] - 15
                sign_height = data_height - 15
                # Center the image in the cell
                sign_x = x1 + (col_widths[1] - sign_width) / 2
                sign_y = (cell_y - data_height) + (data_height - sign_height) / 2

                self.c.drawImage(
                    signature,
                    sign_x,
                    sign_y,
                    width=sign_width,
                    height=sign_height,
                    preserveAspectRatio=True,
                    anchor='c'
                )
    
            # Column 2: سمت
            x2 = x1 + col_widths[1]
            self.draw_data_cell(self.c, x2, cell_y - data_height, col_widths[2], data_height, col2_data[row],
                                wrap=False, radius=8)
    
            # Column 3: نام و نام خانوادگی
            x3 = x2 + col_widths[2]
            self.draw_data_cell(self.c, x3, cell_y - data_height, col_widths[3], data_height, col3_data[row],
                                wrap=True, radius=8)
    
            # Column 4: مسئولیت
            x4 = x3 + col_widths[3]
            self.draw_data_cell(self.c, x4, cell_y - data_height, col_widths[4], data_height, col4_data[row],
                                wrap=True, radius=8)
    
        table_width = sum(col_widths)
        self.c.roundRect(
            table_left,
            table_top - total_table_height,
            table_width,
            total_table_height,
            8,
            fill=0,
            stroke=1
        )

    def generate_pdf(self):
        """
        Saves the canvas and returns the PDF as bytes.
        """
        self.c.save()
        return self._buffer.getvalue()
