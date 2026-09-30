"""V_1.0's `Provider.deliver_to_pdf` (deliver_convert.py:138-278), minus the data
gathering (now adapter.py) and the viewer launch (`os.startfile` / `open` /
`xdg-open` / `sys.exit`, which have no place in a Celery worker).

Everything here is a pure function of a `PdfInput`. V_1.0 shared its state
through a module-level `all_documents` dict (plus a module-level `SHORT`
buffer) that every Provider() reset and every render read back, so two
renders running at once would have drawn each other's data. Nothing is global
here: the input is a parameter, the renderer is built per call.
"""
from dataclasses import dataclass, field

from . import header
from .renderer import HEADER_GAP, PDFMaker

#: Block tags of `PdfInput.blocks`. V_1.0 told them apart with `type(el) is
#: list / dict` and a magic key; a tag says the same thing without guessing.
TEXT = "text"
RESPONSIBILITIES = "responsibilities"
TABLE = "table"
ATTACHMENTS = "attachments"
#: A تشریحی بلند block written in the rich editor: (heading, ProseMirror doc) — richtext.py.
RICH = "rich"

TABLE_HEADER = ["شماره ردیف", "تاریخ", "عنوان"]
# (V_1.0's fixed column widths [50, 100, 200] are gone: the جدول تغییرات fills the text width — richtext.render_changes.)


@dataclass(frozen=True)
class SignatureBlock:
    """One row of the control table: V_1.0's [name, post, signature]."""

    name: str = ""
    position: str = ""
    image: bytes | None = None

    def as_list(self) -> list:
        return [self.name, self.position, self.image]


@dataclass(frozen=True)
class PdfInput:
    title: str
    whole_code: str
    review: str
    date: str
    validation: str
    upper_footnote: str = ""
    lower_footnote: str = ""
    extra_header: str = ""
    logo: bytes | None = None
    #: Shown at the centre of the page header when the document asks for it (2026-09-30).
    company_name: str = ""
    qr: bytes | None = None
    creater: SignatureBlock = field(default_factory=SignatureBlock)
    confirmer: SignatureBlock = field(default_factory=SignatureBlock)
    approver: SignatureBlock = field(default_factory=SignatureBlock)
    #: Change-table rows from earlier revisions, oldest first: [number, date, text].
    previous_changes: tuple = ()
    #: (tag, payload) in page order — V_1.0's `all_documents['rest']`.
    blocks: tuple = ()


def deliver_to_pdf(data: PdfInput, *, preview: bool = False, invariant: bool = False) -> bytes:
    details = header.meta_rows(data.whole_code, data.review, data.date)

    pdf_maker = PDFMaker(
        header_gap=HEADER_GAP,
        qr=data.qr,
        date=data.date,
        title=data.title,
        whole_code=data.whole_code,
        logo=data.logo,
        company_name=data.company_name,
        upper_foot=data.upper_footnote,
        lower_foot=data.lower_footnote,
        preview_mode=preview,
        invariant=invariant,
    )

    pdf_maker.draw_header(title_text=data.title, details=details)

    pdf_maker.draw_control_table(
        data.creater.as_list(),
        data.confirmer.as_list(),
        data.approver.as_list(),
        data.validation,
        data.extra_header,
    )
    for tag, payload in data.blocks:
        if tag == ATTACHMENTS:
            pdf_maker.attachments(payload)
        elif tag == RICH:
            pdf_maker.add_rich(*payload)
        elif tag == RESPONSIBILITIES:
            pdf_maker.responsibilities(payload)
        elif tag == TABLE:
            # Earlier revisions' rows first (V_1.0 fetched them over HTTP).
            table = [TABLE_HEADER] + [list(row) for row in data.previous_changes] + [list(row) for row in payload]
            pdf_maker.add_table(table)
        else:
            pdf_maker.add_body_text(payload, not_body=True)

    return pdf_maker.generate_pdf()
