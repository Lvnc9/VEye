"""Migration 0008: the Responsibilities block's old rows (four fixed roles with a سمت and a
ناظر, plus notes) become free-text rows — nothing an issued document printed is lost."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.accounts.models import User

BEFORE = [("documents", "0007_document_show_company_name")]
AFTER = [("documents", "0008_responsibility_rows_by_unit")]


class OldRowsBecomeFreeTextTests(TransactionTestCase):
    def migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def setUp(self):
        old = self.migrate(BEFORE)
        Document = old.get_model("documents", "Document")
        Section = old.get_model("documents", "Section")
        Row = old.get_model("documents", "ResponsibilityRow")
        # The real User: the historical one lacks columns later migrations of accounts added.
        user = User.objects.create(national_code="9990000001", full_name="نویسنده")
        document = Document.objects.create(
            category="INSIDE", title="سند", group="PROCEDURE", number=1, revision=1, created_by_id=user.pk
        )
        section = Section.objects.create(document=document, position=0, type="Responsibilities")
        rows = [
            ("responder", "مدیر", "ناظر کیفی", "شرح الف"),
            ("receiver", "", "", "فقط شرح"),
            ("cash_account", "حسابدار", "", ""),
            ("supervisor", "", "", ""),  # says nothing: dropped
            ("", "", "", "یادداشت آزاد"),
            ("", "", "", "   "),  # a blank note: dropped
        ]
        for position, (role, post, supervisor, text) in enumerate(rows):
            Row.objects.create(section=section, position=position, role=role, post=post, supervisor=supervisor, text=text)
        self.section_id = section.pk
        self.new = self.migrate(AFTER)

    def tearDown(self):
        self.migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())

    def test_each_old_row_becomes_one_line_of_text(self):
        Row = self.new.get_model("documents", "ResponsibilityRow")
        rows = list(Row.objects.filter(section_id=self.section_id).order_by("position"))
        self.assertEqual(
            [r.text for r in rows],
            [
                "الف:  سمت: مدیر    ناظر: ناظر کیفی\nشرح الف",
                "ب:  فقط شرح",
                "ج:  سمت: حسابدار",
                "یادداشت آزاد",
            ],
        )

    def test_they_name_no_unit_and_no_domain(self):
        Row = self.new.get_model("documents", "ResponsibilityRow")
        for row in Row.objects.filter(section_id=self.section_id):
            self.assertEqual((row.unit_id, row.domain_id, row.unit_name, row.domain_name), (None, None, "", ""))

    def test_the_old_columns_and_constraint_are_gone(self):
        Row = self.new.get_model("documents", "ResponsibilityRow")
        names = {field.name for field in Row._meta.get_fields()}
        self.assertTrue({"domain", "unit", "domain_name", "unit_name", "text"} <= names)
        self.assertFalse({"role", "post", "supervisor"} & names)
        self.assertEqual(Row._meta.constraints, [])
