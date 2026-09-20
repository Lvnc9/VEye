"""The PDF renderer — a port of V_1.0's other_folder/to_make_pdf.py.

The layout algorithm is the product owner's and is reproduced as written, quirks
included (see .claude/docs/08-pdf-engine.md for the list). What changed:

  * images (logo, QR codes, signatures) arrive as PNG *bytes* instead of paths on
    the author's machine / S3 URLs, and the PDF is built in memory and returned
    as bytes;
  * fonts are registered once at startup (apps.pdfgen.apps.PdfgenConfig.ready)
    rather than by every PDFMaker, and the module keeps no mutable global state;
  * the crash-level bugs are fixed (each is marked "V_1.0 crashed" below).

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
        Draws the small header on pages >=2 in #6c7482:
          - Logo on left
          - title_text in #6c7482
          - Bold code_text on the right
          - A horizontal separator
        Then resets fill color to black.
        """
        self.setFillColorRGB(108/255.0, 116/255.0, 130/255.0)

        margin_top = 20
        margin_left = 40
        margin_right = 40

        logo_width = 40
        logo_height = 40
        logo_x = margin_left
        logo_y = self._pagesize[1] - margin_top - logo_height

        if self.logo is not None:
            self.drawImage(
                self.logo,
                logo_x,
                logo_y,
                width=logo_width,
                height=logo_height,
                mask="auto"
            )
        else:
            self.rect(logo_x, logo_y, logo_width, logo_height, fill=1)

        text_x = logo_x + logo_width + 10
        text_y = logo_y + (logo_height / 2) - 5
        #self.setFont(self.font_name, 12)

        # V_1.0 crashed here (KeyError) if the bold font was not registered; every
        # other bold use is guarded like this.
        if (self.font_name + "-Bold") in pdfmetrics.getRegisteredFontNames():
            self.setFont(self.font_name + "-Bold", 14)
        else:
            self.setFont(self.font_name, 14)
        reshaped_title = arabic_reshaper.reshape(self.title_text)
        bidi_title = get_display(reshaped_title)
        self.drawString(text_x, text_y, bidi_title)

        # Bold code text on right
        if (self.font_name + "-Bold") in pdfmetrics.getRegisteredFontNames():
            self.setFont(self.font_name + "-Bold", 12)
        code_text_str = self.code_text
        reshaped_code = arabic_reshaper.reshape(code_text_str)
        bidi_code = get_display(reshaped_code)
        code_text_width = self.stringWidth(bidi_code, self.font_name + "-Bold", 12) \
            if (self.font_name + "-Bold") in pdfmetrics.getRegisteredFontNames() \
            else self.stringWidth(bidi_code, self.font_name, 12)

        code_x = self._pagesize[0] - margin_right - code_text_width
        code_y = text_y
        self.drawString(code_x, code_y, bidi_code)

        sep_y = logo_y - 5
        self.line(margin_left, sep_y, self._pagesize[0] - margin_right, sep_y)

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
        header_gap=50,
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
        A large initial header drawn on the first page in black text.
        """
        header_total_height = top_details_height + bottom_header_height + 30
        header_top = self.page_height - self.margin
        self._check_page_break(header_total_height)

        self.c.setFillColorRGB(*header_bg_color)
        self.c.rect(
            self.margin,
            header_top - header_total_height,
            self.page_width - 2 * self.margin,
            header_total_height,
            fill=1,
            stroke=0
        )
        # black text for big header
        self.c.setFillColorRGB(0, 0, 0)
        if details is None:
            # V_1.0 split the code *before* this guard, so a caller that passed
            # `details` still crashed on a code without three parts.
            third = self.whole_code.split('-')[2]
            details = [f"کد: {self.whole_code}", f"شماره بازنگری: {third}", f"تاریخ: {self.date}"]

        self.c.setFont(self.font_name, code_font_size)
        detail_y = header_top - 15
        for detail in details:
            detail_rtl = self.prepare_rtl(detail)
            self.c.drawString(self.margin + 5, detail_y, detail_rtl)
            detail_y -= 16

        sep_y = header_top - top_details_height - 15
        self.c.setLineWidth(1)
        self.c.line(self.margin, sep_y, self.page_width - self.margin, sep_y)

        # Title
        title_rtl = self.prepare_rtl(self.title)
        self.c.setFont(self.font_name, title_font_size)
        bottom_center_y = sep_y - (bottom_header_height / 2) + 8
        self.c.drawCentredString(self.page_width / 2, bottom_center_y, title_rtl)

        # Logo on the right
        logo_width = 60
        logo_height = 60
        logo_x = self.page_width - self.margin - logo_width
        logo_y = sep_y - logo_height - 10
        if self.c.logo is not None:
            self.c.drawImage(
                self.c.logo,
                logo_x,
                logo_y,
                width=logo_width,
                height=logo_height,
                mask="auto"
            )
        else:
            self.c.rect(logo_x, logo_y, logo_width, logo_height, fill=1)

        self.current_y = header_top - header_total_height - 40
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
        wrapped_lines = []

        # For each line, break it into sub-lines of up to 70 characters, 
        # preserving empty lines to maintain paragraph breaks.
        for line in raw_lines:
            if not line:  
                # Preserve empty line to create a paragraph break
                wrapped_lines.append("")
            elif len(line) <= 170:
                wrapped_lines.append(line)
            else:
                start_idx = 0
                while start_idx < len(line):
                    wrapped_lines.append(line[start_idx:start_idx+70])
                    start_idx += 70

        # Now process these wrapped lines
        for idx, line in enumerate(wrapped_lines):
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
            elif not_body and idx == 0:
                bold_font = (self.font_name + "-Bold" if (self.font_name + "-Bold")
                             in pdfmetrics.getRegisteredFontNames()
                             else self.font_name)
                self.c.setFont(bold_font, font_size + 2)
                line_rtl = self.prepare_rtl(line)
                self.c.drawRightString(x_right, self.current_y, line_rtl)
            elif not_body and idx == 1:
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
        """
        length = ""
        big = []
        group = text.split(" ")
        for i in group:
            if len(length + " " + i) <= limit:
                length = length + " " + i
                if i is group[-1]:
                    big.append(length)
            else:
                big.append(length)
                length = i
        return big

    def attachments(self, element, x_offset=30, font_size=12):
        """
        Draw a “ضمائم:” label, then place a QR at the extreme right
        and the text (with optional inline styling) to the left, right-aligned.
        
        This version properly measures the text width so that the next text
        appears exactly 30 points to the left of the previous text.
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
    
        # Prepare fixed space for QR
        qr_width = 50
        qr_height = 50
        qr_x = self.page_width - self.margin - qr_width
        qr_y = self.current_y - (qr_height - font_size)  # Align roughly to baseline

        for el in element:
            self._check_page_break(50)
            text, thin, qr = el
            # Draw the QR image
            
            qr_x = self.page_width - self.margin - qr_width
            qr_y = self.current_y - (qr_height - font_size)
            
            qr_img = _image(qr)
            if qr_img is not None:
                self.c.drawImage(qr_img, qr_x, qr_y, width=qr_width, height=qr_height, mask="auto")
            else:
                # Fallback if QR path not found
                self.c.rect(qr_x, qr_y, qr_width, qr_height, fill=1)
    
            # The main text is drawn first in one line, right-aligned starting at text_right_edge
            text_right_edge = qr_x - x_offset + 20
    
            # Draw the main text
            self.draw_rtl_styled_line(text_right_edge, self.current_y - 30, text, 10)
    
            # Measure how wide that text was (in points)
            text_rtl = self.prepare_rtl(text)
            main_text_width = self.c.stringWidth(text_rtl, self.font_name, 10)
    
            # Now place the 'thin' text 30 points to the left of where the previous text ended
            # Because the drawn text is right-aligned within draw_rtl_styled_line,
            # the "starting X" actually accounts for the total width inside that method.
            # So we subtract the measured width + 30 more points to place it further to the left.
            next_text_right_edge = text_right_edge - main_text_width - 5
            self.draw_rtl_styled_line(
            next_text_right_edge,
            self.current_y - 30,
            "کد " +  thin,  # Make text italic
            8,
        )
    
            # Adjust the vertical position
            self.current_y -= (qr_height - 30)
            self.c.setFont(self.font_name, 12)
            self.current_y -= 40

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
