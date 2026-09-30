"""Document (Postgres) -> `FormPdfInput`: the data of a form body's PDF
(Phase 11, ADR-011). The block-body counterpart is adapter.py; the two share
the image reader, the Jalali date and the «is it superseded?» rule so the documents
they describe agree."""
from django.utils import timezone

from apps.core.constants import SectionType, SignOffRole
from apps.documents import form_schema
from apps.documents.models import Document

from . import signoff
from .adapter import _read_png, company_name as _company_name, is_obsolete, jalali
from .form_renderer import FormPdfInput, Signer
from .qr import qr_png, verify_url

#: The approval strip's columns, right to left.
SIGNER_ORDER = (SignOffRole.CREATER, SignOffRole.CONFIRMER, SignOffRole.APPROVER)
#: What each column is called on paper (owner's request, 2026-09-30) — `SignOffRole.label` says
#: «تدوین کننده» for the first, which is the workflow's word, not the sheet's.
SIGNER_LABELS = dict(zip(SIGNER_ORDER, signoff.ROLES))


def load(document_id: int) -> FormPdfInput:
    document = Document.objects.prefetch_related("signoffs").get(pk=document_id)
    # Settings stored before a field existed read as its default.
    settings = form_schema.clean_settings(document.form_settings or {})
    header = settings["header"]

    elements = tuple(
        form_schema.normalize_stored(section.content)
        for section in document.sections.filter(type=SectionType.FORM_ELEMENT).order_by("position", "id")
    )

    signoffs = {signoff.role: signoff for signoff in document.signoffs.all()}
    signers = []
    for role in SIGNER_ORDER:
        signoff = signoffs.get(role)
        signers.append(
            Signer(
                role_label=SIGNER_LABELS[role],
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
        obsolete=is_obsolete(document.status),
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
