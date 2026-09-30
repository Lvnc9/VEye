"""The Responsibilities block's rows change shape (owner's redesign, 2026-09-30).

Before: four fixed rows (role, سمت, ناظر, description) plus free description-only notes.
After: any number of rows, each a حوزه (optional), a واحد and a description — `domain` / `unit`
point at the org chart, `domain_name` / `unit_name` are the snapshots that print.

Nothing an issued document printed is lost: every old row that said anything becomes a row with
no واحد whose `text` is the old line written out — «الف:  سمت: X    ناظر: Y» and, on the next
line, its description (notes stay as they were) — and it prints as that text. Empty rows are
dropped. The rule is `documents.responsibility_nodes.legacy_text`; it is copied here on
purpose, so this migration never changes when that module does.

Reversing restores the columns but not the old data (a row's text stays where it is).
"""
import django.db.models.deletion
from django.db import migrations, models

ORDER = ("responder", "receiver", "cash_account", "supervisor")  # V_1.0's row order
LETTERS = {"responder": "الف", "receiver": "ب", "cash_account": "ج", "supervisor": "د"}


def legacy_text(role: str, post: str, supervisor: str, text: str) -> str:
    post, supervisor, text = (post or "").strip(), (supervisor or "").strip(), (text or "").strip()
    if not (post or supervisor or text):
        return ""
    letter = LETTERS.get(role, "")
    parts = ([f"سمت: {post}"] if post else []) + ([f"ناظر: {supervisor}"] if supervisor else [])
    head = (f"{letter}:  " if letter else "") + "    ".join(parts)
    if not parts:
        return f"{head}{text}"
    return f"{head}\n{text}" if text else head


def old_rows_to_free_text(apps, schema_editor):
    ResponsibilityRow = apps.get_model("documents", "ResponsibilityRow")
    for row in ResponsibilityRow.objects.all().order_by("section_id", "position", "id"):
        if row.role:
            new_text = legacy_text(row.role, row.post, row.supervisor, row.text)
        else:  # a description-only note: as it was
            new_text = (row.text or "").strip()
        if not new_text:
            row.delete()
        elif new_text != row.text:
            row.text = new_text
            row.save(update_fields=["text"])


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0007_document_show_company_name"),
        ("organization", "0003_document_defaults"),
    ]

    operations = [
        migrations.AddField(
            model_name="responsibilityrow",
            name="domain",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to="organization.orgnode",
            ),
        ),
        migrations.AddField(
            model_name="responsibilityrow",
            name="unit",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to="organization.orgnode",
            ),
        ),
        migrations.AddField(
            model_name="responsibilityrow",
            name="domain_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="responsibilityrow",
            name="unit_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.RunPython(old_rows_to_free_text, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="responsibilityrow",
            name="uniq_responsibility_role_per_section",
        ),
        migrations.RemoveField(model_name="responsibilityrow", name="role"),
        migrations.RemoveField(model_name="responsibilityrow", name="post"),
        migrations.RemoveField(model_name="responsibilityrow", name="supervisor"),
    ]
