"""The company's document defaults (Phase 11, ADR-011) applied to a new document.

Registered into `apps.documents.services.NEW_DOCUMENT_HOOKS` by this app's
AppConfig.ready(): the documents app never reads the organisation's tables, so the
organisation hands its defaults over instead."""
import logging

from apps.core.constants import BodyKind
from apps.documents import content

from .models import Company

logger = logging.getLogger("veye")


def apply_to_new_document(document) -> None:
    """Start a new document from the company's defaults, set in «تنظیمات»: its logo,
    footnotes and, for a form, the header subtitle and letter box. They are copied,
    not referenced, so later changes to the defaults leave this document alone."""
    company = Company.objects.filter(pk=1).first()
    if company is None:
        return
    document.footnote1 = company.doc_footnote1
    document.footnote2 = company.doc_footnote2
    fields = ["footnote1", "footnote2", "updated_at"]
    if document.body_kind == BodyKind.FORM:
        header = document.form_settings["header"]
        header["subtitle"] = company.form_subtitle
        header["show_letter_box"] = company.form_show_letter_box
        fields.append("form_settings")
    if company.logo:
        try:
            content._copy_stored_file(company.logo, document.logo, "logo.png")
            fields.append("logo")
        except FileNotFoundError:
            logger.warning("Company logo %r is missing; new document %s starts without one", company.logo.name, document.pk)
    document.save(update_fields=fields)
