"""A document belongs to an org-chart node (Phase 14, owner's decision 2026-09-30).

`owner_node` decides who may write, confirm and approve it. Existing documents get one so nothing is
stranded when the rules switch: the author's *primary* placement (if it is still an active node),
else the company (the root node) — so only the مدیر عامل and whoever leads the whole company act on
it until someone with a node picks a better one. Documents made before a company exists stay NULL;
imported documents (written by the importer's inactive account) get the company like the rest.
"""
import django.db.models.deletion
from django.db import migrations, models


def give_existing_documents_a_node(apps, schema_editor):
    Document = apps.get_model("documents", "Document")
    Company = apps.get_model("organization", "Company")
    Membership = apps.get_model("organization", "Membership")
    root_id = Company.objects.filter(pk=1).values_list("root_id", flat=True).first()
    primary = dict(
        Membership.objects.filter(is_primary=True, node__is_active=True).values_list("user_id", "node_id")
    )
    for document in Document.objects.filter(owner_node__isnull=True).only("id", "created_by_id"):
        node_id = primary.get(document.created_by_id, root_id)
        if node_id:
            Document.objects.filter(pk=document.pk).update(owner_node_id=node_id)


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0008_responsibility_rows_by_unit"),
        ("organization", "0003_document_defaults"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="owner_node",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="documents", to="organization.orgnode",
            ),
        ),
        migrations.RunPython(give_existing_documents_a_node, migrations.RunPython.noop),
    ]
