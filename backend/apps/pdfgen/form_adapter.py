"""Document (Postgres) -> `FormPdfInput`: the data of a form body's PDF
(Phase 11, ADR-011). The block-body counterpart is adapter.py; the two share
the image reader, the Jalali date and the validity rule so the documents they
describe agree."""
from django.utils import timezone

from apps.core.constants import SectionType, SignOffRole
from apps.documents import form_schema
from apps.documents.models import Document
from apps.organization.models import Company

from .adapter import _read_png, _validation_mark, jalali
from .form_renderer import FormPdfInput, Signer
from .qr import qr_png, verify_url

#: The approval strip's columns, right to left.
SIGNER_ORDER = (SignOffRole.CREATER, SignOffRole.CONFIRMER, SignOffRole.APPROVER)


def _company_name() -> str:
    company = Company.objects.select_related("root").filter(pk=1).first()
    return company.root.name if company else ""


def load(document_id: int) -> FormPdfInput:
    document = Document.objects.prefetch_related("signoffs").get(pk=document_id)
    # Settings stored before a field existed read as its default.
    settings = form_schema.clean_settings(document.form_settings or {})
    header = settings["header"]

    elements = tuple(
        section.content
        for section in document.sections.filter(type=SectionType.FORM_ELEMENT).order_by("position", "id")
    )

    signoffs = {signoff.role: signoff for signoff in document.signoffs.all()}
    signers = []
    for role in SIGNER_ORDER:
        signoff = signoffs.get(role)
        signers.append(
            Signer(
                role_label=SignOffRole(role).label,
                name=signoff.name if signoff else "",
                position=signoff.position if signoff else "",
                date=jalali(signoff.signed_date) if signoff and signoff.signed_date else "",
                image=_read_png(signoff.signature, flatten=True) if signoff else None,
            )
        )

    saved_at = document.content_saved_at
    day = timezone.localtime(saved_at).date() if saved_at else timezone.localdate()

    return FormPdfInput(
        title=document.title,
        full_code=document.full_code,
        revision=document.revision_display,
        date=jalali(day),
        validation=_validation_mark(document.status),
        company_name=_company_name() if header["show_company_name"] else "",
        subtitle=header["subtitle"],
        show_letter_box=header["show_letter_box"],
        footnote1=document.footnote1,
        footnote2=document.footnote2,
        logo=_read_png(document.logo),
        qr=qr_png(verify_url(document)),
        orientation=settings["orientation"],
        base_font_size=settings["base_font_size"],
        approval_strip=settings["approval_strip"],
        signers=tuple(signers),
        elements=elements,
    )
