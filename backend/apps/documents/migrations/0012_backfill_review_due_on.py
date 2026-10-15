"""Phase 21: give every document already in force a periodic-review date — one interval (12 months by
default) after it came under control: its APPROVED event, else its approver's signature date (documents
imported from V_1.0 have no events), else when its content was last saved, else when it was created."""
import calendar
from datetime import date

from django.db import migrations


def _add_months(start: date, months: int) -> date:
    index = start.month - 1 + months
    year, month = start.year + index // 12, index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def backfill(apps, schema_editor):
    Document = apps.get_model("documents", "Document")
    DocumentEvent = apps.get_model("documents", "DocumentEvent")
    SignOff = apps.get_model("documents", "SignOff")
    for document in Document.objects.filter(status="UNDER_CONTROL", review_due_on__isnull=True):
        if document.review_interval_months <= 0:
            continue
        approved = DocumentEvent.objects.filter(document=document, kind="approved").order_by("-created_at").first()
        signoff = SignOff.objects.filter(document=document, role="approver").first()
        if approved is not None:
            start = approved.created_at.date()
        elif signoff is not None and signoff.signed_date:
            start = signoff.signed_date
        else:
            start = (document.content_saved_at or document.created_at).date()
        document.review_due_on = _add_months(start, document.review_interval_months)
        document.save(update_fields=["review_due_on"])


class Migration(migrations.Migration):
    dependencies = [("documents", "0011_document_review_due_on_and_more")]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
