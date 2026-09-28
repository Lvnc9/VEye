"""An empty فرم draft made before the form designer (Phase 11) becomes a form.

0005 gave every existing document `body_kind = blocks`, so a فرم created on the
old code — even one with nothing in it yet — kept opening the block designer.
A draft that is revision 1 and has no body loses nothing by becoming a form;
فرم documents with content (or later revisions, or anything past draft) keep
their blocks, as ADR-011 decided."""
from django.db import migrations

#: form_schema.default_settings() as of this migration (kept literal: a
#: migration must not change meaning when the schema module does).
DEFAULT_SETTINGS = {
    "v": 1,
    "orientation": "portrait",
    "base_font_size": 10,
    "approval_strip": True,
    "header": {"subtitle": "", "show_company_name": True, "show_letter_box": False},
}


def empty_form_drafts_to_forms(apps, schema_editor):
    Document = apps.get_model("documents", "Document")
    candidates = Document.objects.filter(
        group="FORM", body_kind="blocks", status="DRAFT", revision=1, previous_revision__isnull=True, sections__isnull=True
    )
    for document in candidates:
        document.body_kind = "form"
        document.form_settings = DEFAULT_SETTINGS
        document.save(update_fields=["body_kind", "form_settings"])


class Migration(migrations.Migration):
    dependencies = [("documents", "0005_form_body")]

    operations = [migrations.RunPython(empty_form_drafts_to_forms, migrations.RunPython.noop)]
