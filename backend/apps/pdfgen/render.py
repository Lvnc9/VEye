"""Which renderer builds a document's PDF (Phase 11, ADR-011).

A block body goes through the owner's port (adapter → provider → renderer.py),
unchanged; a form body through the compact form layout (form_adapter →
form_renderer). The Celery task, storage, the API, bulk print and the verify
page don't care which."""
from apps.core.constants import BodyKind
from apps.documents.models import Document

from . import adapter, form_adapter, form_renderer, provider


def render(document_id: int, *, preview: bool) -> bytes:
    body_kind = Document.objects.values_list("body_kind", flat=True).get(pk=document_id)
    if body_kind == BodyKind.FORM:
        return form_renderer.render(form_adapter.load(document_id), preview=preview)
    return provider.deliver_to_pdf(adapter.load(document_id), preview=preview)
