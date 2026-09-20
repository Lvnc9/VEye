"""The importer against Postgres: dry run, commit, collisions, atomicity, the task and the command."""
import io
import json
import os
import shutil
import tempfile
from datetime import date
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.core.constants import DocumentCategory, DocumentEventKind, DocumentGroup, DocumentStatus, SectionType
from apps.documents.models import (
    AttachmentReference, ChangeTableRow, Document, DocumentEvent, DocumentSequence, ResponsibilityRow, Section, SignOff)
from apps.importer import loader, tasks
from apps.importer.files import V1Files
from apps.importer.models import ImportRun, ImportStatus
from apps.pdfgen import adapter, provider

from . import v1data

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "veye-import-tests"}}


@override_settings(CACHES=LOCMEM, FRONTEND_BASE_URL="https://veye.test")
class ImportBase(TestCase):
    def setUp(self):
        cache.clear()
        # A media root of its own per test: stored files must not leak between tests.
        self.media = tempfile.mkdtemp(prefix="veye-import-media-")
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.enterContext(override_settings(MEDIA_ROOT=self.media))
        self.dir = tempfile.mkdtemp(prefix="veye-v1-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        from pathlib import Path
        self.rows = v1data.build(Path(self.dir))
        self.files = V1Files(self.dir)

    def run_import(self, rows=None, dry_run=False):
        return loader.run_import(self.rows if rows is None else rows, self.files, dry_run=dry_run)

    def entry(self, result, code, position=None):
        found = [e for e in result.entries if e.code == code and (position is None or e.position == position)]
        self.assertEqual(len(found), 1, f"{code}: {[e.position for e in found]}")
        return found[0]

    def codes(self, entry):
        return [n.code for n in entry.notes]

    def doc(self, code):
        prefix, number, revision = code.split("-")
        group = {v: k for k, v in __import__("apps.core.constants", fromlist=["GROUP_CODE_PREFIX"]).GROUP_CODE_PREFIX.items()}[prefix]
        return Document.objects.get(group=group, number=int(number), revision=int(revision))


class DryRunTests(ImportBase):
    def test_a_dry_run_reports_everything_and_writes_nothing(self):
        result = self.run_import(dry_run=True)
        self.assertEqual(Document.objects.count(), 0)
        self.assertEqual((DocumentSequence.objects.count(), DocumentEvent.objects.count(), SignOff.objects.count()), (0, 0, 0))
        self.assertFalse(User.objects.filter(national_code=loader.IMPORT_USER_CODE).exists())  # not even the owner account
        self.assertEqual(_stored_files(self.media), [])  # no logo or signature written either
        c = result.counts
        self.assertEqual((c["total"], c["would_create"], c["created"], c["skipped"], c["errors"]), (10, 8, 0, 0, 2))
        self.assertEqual(self.entry(result, "PR-01-01", 1).action, "would_create")

    def test_a_dry_run_shows_the_same_problems_a_real_run_would(self):
        dry = self.run_import(dry_run=True)
        real = self.run_import(dry_run=False)
        for position in range(1, 11):
            a = [e for e in dry.entries if e.position == position][0]
            b = [e for e in real.entries if e.position == position][0]
            self.assertEqual(sorted(self.codes(a)), sorted(self.codes(b)), f"row {position}")


class CommitTests(ImportBase):
    def setUp(self):
        super().setUp()
        self.result = self.run_import()

    def test_counts_and_what_was_created(self):
        c = self.result.counts
        self.assertEqual((c["created"], c["skipped"], c["errors"], c["superseded"]), (8, 0, 2, 1))
        self.assertEqual(Document.objects.count(), 8)
        self.assertEqual(self.entry(self.result, "PO-02").action, "error")           # bad review
        self.assertIn("duplicate_in_source", self.codes(self.entry(self.result, "PR-01-01", 8)))

    def test_number_revision_group_category_and_title(self):
        d = self.doc("PR-01-02")
        self.assertEqual((d.group, d.number, d.revision, d.title), (DocumentGroup.PROCEDURE, 1, 2, "روش الف"))
        self.assertEqual(self.doc("PO-01-01").category, DocumentCategory.OUTSIDE)
        self.assertEqual(self.doc("WI-02-01").revision, 1)  # "0-0" is revision 1, not 0

    def test_status_comes_from_valid_and_a_superseded_revision_becomes_obsolete(self):
        self.assertEqual(self.doc("PR-01-02").status, DocumentStatus.UNDER_CONTROL)
        self.assertEqual(self.doc("PR-01-01").status, DocumentStatus.OBSOLETE)  # V_1.0 said "vali"; V_2's approval would have obsoleted it
        self.assertIn("superseded_on_import", self.codes(self.entry(self.result, "PR-01-01", 1)))
        self.assertEqual(self.doc("PO-01-01").status, DocumentStatus.OBSOLETE)   # "outdated"
        self.assertEqual(self.doc("WI-01-01").status, DocumentStatus.UNDER_CONTROL)
        self.assertEqual(self.doc("WI-02-01").status, DocumentStatus.DRAFT)      # "unknown"
        self.assertEqual(self.doc("FR-01-01").status, DocumentStatus.DRAFT)

    def test_the_revision_chain_is_linked(self):
        self.assertEqual(self.doc("PR-01-02").previous_revision, self.doc("PR-01-01"))
        self.assertIsNone(self.doc("PR-01-01").previous_revision)

    def test_the_document_date_is_the_saved_date_in_tehran_time(self):
        saved = timezone.localtime(self.doc("PR-01-01").content_saved_at)
        self.assertEqual(saved.date(), date(2025, 4, 8))  # 1404/01/19, like the archived sample
        self.assertEqual(self.doc("PR-01-01").created_at.date(), date(2025, 4, 8))
        self.assertIsNone(self.doc("WI-02-01").content_saved_at)  # a never-saved draft has none

    def test_sections_keep_page_order_and_content(self):
        sections = list(self.doc("PR-01-01").sections.all())
        self.assertEqual([s.type for s in sections], [SectionType.SHORT_EXPLANATION, SectionType.LONG_EXPLANATION,
                                                       SectionType.RESPONSIBILITIES, SectionType.CHANGES_TABLE, SectionType.ATTACHMENT])
        self.assertEqual(sections[0].content, {"lines": ["1-هدف", "این یک نمونه است."]})
        self.assertEqual(sections[1].content, {"heading": "2-شرح", "body": "متن بلند **مهم**", "extra_boxes": ["جعبهٔ اضافه"]})

    def test_responsibilities_rows_placeholders_and_notes(self):
        rows = list(ResponsibilityRow.objects.filter(section__document=self.doc("PR-01-01")).order_by("position"))
        self.assertEqual([(r.role, r.post, r.supervisor, r.text) for r in rows[:4]], [
            ("responder", "مدیر برنامه", "ناظر کیفی", "شرح الف"), ("receiver", "", "", "شرح ب"),
            ("cash_account", "کارشناس", "", "شرح ج"), ("supervisor", "", "", "شرح د")])
        self.assertEqual([(r.role, r.text) for r in rows[4:]], [("", "یادداشت")])

    def test_only_this_revisions_own_change_rows_are_imported_and_history_is_derived(self):
        own = list(ChangeTableRow.objects.filter(section__document=self.doc("PR-01-01")))
        self.assertEqual([(r.text, r.date) for r in own], [("تغییر تازه", date(2025, 4, 8))])  # the frozen «label» row was skipped
        # Revision 2 has no change table of its own; revision 1's rows still reach it through the chain.
        self.assertEqual([r.text for r in self.doc("PR-01-02").previous_change_rows()], ["تغییر تازه"])

    def test_attachments_resolve_to_imported_documents_and_report_the_rest(self):
        refs = list(AttachmentReference.objects.filter(section__document=self.doc("PR-01-01")))
        self.assertEqual([(r.caption, r.target.full_code) for r in refs], [("فرم پیوست", "WI-01-01")])
        self.assertIn("attachment_unresolved", self.codes(self.entry(self.result, "PR-01-01", 1)))  # PO-09-01 doesn't exist

    def test_signers_have_their_own_images_and_transparency_is_flattened(self):
        signoffs = {s.role: s for s in self.doc("PR-01-01").signoffs.all()}
        self.assertEqual(set(signoffs), {"creater", "confirmer", "approver"})
        self.assertEqual((signoffs["creater"].name, signoffs["creater"].position), ("نویسندهٔ نمونه", "کارشناس"))
        self.assertEqual(signoffs["creater"].signed_date, date(2025, 4, 8))
        self.assertIsNone(signoffs["creater"].signed_by)  # V_1.0 has no accounts to link
        for signoff in signoffs.values():
            with signoff.signature.open("rb") as handle:
                image = Image.open(io.BytesIO(handle.read()))
            self.assertEqual((image.format, image.mode), ("PNG", "RGB"))  # opaque, as the PDF renderer needs
        self.assertNotIn("signature_missing", self.codes(self.entry(self.result, "PR-01-01", 1)))

    def test_unreadable_or_missing_images_are_reported_but_never_stop_the_document(self):
        entry = self.entry(self.result, "PR-01-02")
        self.assertIn("signature_unreadable", self.codes(entry))       # PR-01-01creater.png is not an image
        self.assertTrue(self.doc("PR-01-02").signoffs.filter(role="creater").exists())  # the sign-off (name/post) still exists
        self.assertFalse(self.doc("PR-01-02").signoffs.get(role="creater").signature)

    def test_logo_is_normalised_to_png_and_only_when_present(self):
        self.assertTrue(self.doc("PR-01-01").logo.name.endswith(".png"))
        self.assertFalse(self.doc("WI-01-01").logo)

    def test_drafts_get_no_signoffs_and_say_so(self):
        self.assertEqual(self.doc("FR-01-01").signoffs.count(), 0)
        self.assertIn("signers_ignored_on_draft", self.codes(self.entry(self.result, "FR-01-01")))
        self.assertEqual(self.doc("FR-01-01").sections.count(), 1)  # …but its body was kept, and it stays editable
        self.assertTrue(self.doc("FR-01-01").is_editable)

    def test_content_problems_leave_a_document_without_a_body_but_reported(self):
        self.assertIn("content_missing", self.codes(self.entry(self.result, "PO-05-01")))
        self.assertEqual(self.doc("PO-05-01").sections.count(), 0)
        self.assertIn("content_mismatch", self.codes(self.entry(self.result, "PO-03-01")))   # another document's file
        self.assertEqual(self.doc("PO-03-01").sections.count(), 0)
        self.assertIn("no_content", self.codes(self.entry(self.result, "WI-02-01")))

    def test_a_revision_1_file_stamped_00_is_accepted(self):
        self.assertNotIn("content_mismatch", self.codes(self.entry(self.result, "FR-01-01")))  # its file says FR-01-00

    def test_the_sequence_is_raised_to_the_highest_imported_number(self):
        seq = dict(DocumentSequence.objects.values_list("group", "last_number"))
        self.assertEqual(seq["PROCEDURE"], 1)
        self.assertEqual(seq["POSTER"], 5)      # PO-05 was the highest
        self.assertEqual(seq["INSTRUCTION"], 2)

    def test_the_next_new_document_gets_the_next_number(self):
        from apps.documents import services
        author = User.objects.create_user(national_code="8500000001", password="pw-for-tests-123", full_name="ن",
                                          access_roll=AccessRoll.GUILD, access_level=AccessLevel.LEVEL_2)
        fresh = services.create_document(user=author, category=DocumentCategory.INSIDE, title="مستند تازه", group=DocumentGroup.POSTER)
        self.assertEqual(fresh.full_code, "PO-06-01")

    def test_every_imported_document_has_an_import_event_and_the_owner_cannot_sign_in(self):
        self.assertEqual(DocumentEvent.objects.filter(kind=DocumentEventKind.IMPORTED).count(), 8)
        event = DocumentEvent.objects.filter(document=self.doc("PR-01-01")).get()
        self.assertEqual((event.actor, event.actor_name), (None, loader.IMPORT_USER_NAME))
        owner = User.objects.get(national_code=loader.IMPORT_USER_CODE)
        self.assertFalse(owner.is_active)
        self.assertFalse(owner.has_usable_password())
        self.assertEqual({d.created_by for d in Document.objects.all()}, {owner})

    def test_imported_documents_work_in_the_rest_of_the_system(self):
        # The PDF engine renders them (signatures, logo, sections and all)…
        pdf = provider.deliver_to_pdf(adapter.load(self.doc("PR-01-01").pk))
        self.assertTrue(pdf.startswith(b"%PDF-"))
        client = APIClient()
        # …the public verify page knows them…
        self.assertEqual(client.get(reverse("verify", args=["PR-01-02"])).json()["state"], "valid")
        self.assertEqual(client.get(reverse("verify", args=["PR-01-01"])).json()["state"], "obsolete")
        self.assertEqual(client.get(reverse("verify", args=["PR-01-01"])).json()["current_revision"]["full_code"], "PR-01-02")
        # …and the history screen lists them and their import events.
        reader = User.objects.create_user(national_code="8500000002", password="pw-for-tests-123", full_name="خواننده",
                                          access_roll=AccessRoll.GUILD, access_level=AccessLevel.LEVEL_3)
        client.force_authenticate(reader)
        self.assertEqual(client.get(reverse("history-revisions")).data["count"], 8)
        self.assertEqual(client.get(reverse("history-activity"), {"kind": "imported"}).data["count"], 8)


class CollisionAndIdempotencyTests(ImportBase):
    def test_running_twice_creates_nothing_new(self):
        self.run_import()
        before = (Document.objects.count(), SignOff.objects.count(), DocumentEvent.objects.count(), AttachmentReference.objects.count())
        second = self.run_import()
        self.assertEqual((Document.objects.count(), SignOff.objects.count(), DocumentEvent.objects.count(), AttachmentReference.objects.count()), before)
        self.assertEqual((second.counts["created"], second.counts["skipped"]), (0, 8))
        self.assertEqual(self.codes(self.entry(second, "PR-01-01", 1)).count("exists"), 1)

    def test_an_existing_document_is_never_touched(self):
        author = User.objects.create_user(national_code="8500000003", password="pw-for-tests-123", full_name="ن",
                                          access_roll=AccessRoll.GUILD, access_level=AccessLevel.LEVEL_2)
        mine = Document.objects.create(category=DocumentCategory.OUTSIDE, title="عنوان من", group=DocumentGroup.PROCEDURE,
                                       number=1, revision=1, status=DocumentStatus.DRAFT, created_by=author)
        result = self.run_import()
        mine.refresh_from_db()
        self.assertEqual((mine.title, mine.status, mine.category, mine.sections.count()), ("عنوان من", DocumentStatus.DRAFT, DocumentCategory.OUTSIDE, 0))
        self.assertEqual(self.entry(result, "PR-01-01", 1).action, "skipped")
        self.assertEqual(self.entry(result, "PR-01-02").action, "created")   # a *different* revision of the same document is fine
        self.assertEqual(self.doc("PR-01-02").previous_revision, mine)        # and links to the existing one

    def test_a_title_already_used_in_the_group_is_skipped_not_overwritten(self):
        author = User.objects.create_user(national_code="8500000004", password="pw-for-tests-123", full_name="ن",
                                          access_roll=AccessRoll.GUILD, access_level=AccessLevel.LEVEL_2)
        Document.objects.create(category=DocumentCategory.INSIDE, title="دستور ب", group=DocumentGroup.INSTRUCTION,
                                number=9, revision=1, status=DocumentStatus.DRAFT, created_by=author)
        result = self.run_import()
        entry = self.entry(result, "WI-01-01")
        self.assertEqual((entry.action, self.codes(entry)), ("skipped", ["title_conflict"]))
        self.assertFalse(Document.objects.filter(group=DocumentGroup.INSTRUCTION, number=1).exists())

    def test_the_sequence_is_never_lowered(self):
        DocumentSequence.objects.create(group=DocumentGroup.POSTER, last_number=40)
        self.run_import()
        self.assertEqual(DocumentSequence.objects.get(group=DocumentGroup.POSTER).last_number, 40)

    def test_a_partial_source_can_be_completed_by_a_second_run(self):
        self.run_import(self.rows[:1])
        result = self.run_import(self.rows[:3])
        self.assertEqual((result.counts["created"], result.counts["skipped"]), (2, 1))
        # …and the attachment that pointed at a document imported *later* is linked in the run that creates the pointer's target.
        self.assertEqual(self.doc("WI-01-01").status, DocumentStatus.UNDER_CONTROL)


class AtomicityTests(ImportBase):
    def test_one_failing_document_does_not_stop_the_others_and_leaves_no_trace(self):
        real = loader._write_sections

        def flaky(document, content):
            if document.full_code == "WI-01-01":
                raise RuntimeError("boom")
            return real(document, content)

        with mock.patch.object(loader, "_write_sections", flaky):
            result = self.run_import()
        entry = self.entry(result, "WI-01-01")
        self.assertEqual((entry.action, self.codes(entry)), ("error", ["import_failed"]))
        self.assertNotIn("boom", entry.notes[0].message)                      # the cause goes to the log, not the report
        self.assertFalse(Document.objects.filter(group=DocumentGroup.INSTRUCTION, number=1).exists())
        self.assertEqual(Document.objects.count(), 7)
        self.assertEqual(result.counts["errors"], 3)
        # The failed document's stored files were removed too (it had signatures).
        stored = [p for _, _, names in os.walk(os.path.join(self.media, "signatures")) for p in names]
        self.assertEqual(len(stored), SignOff.objects.exclude(signature="").count())

    def test_a_failure_of_the_run_itself_rolls_everything_back_and_removes_the_files(self):
        before = _stored_files(self.media)
        with mock.patch.object(loader, "_raise_sequences", side_effect=RuntimeError("db went away")):
            with self.assertRaises(RuntimeError):
                self.run_import()
        self.assertEqual((Document.objects.count(), SignOff.objects.count(), DocumentSequence.objects.count()), (0, 0, 0))
        self.assertEqual(_stored_files(self.media), before)  # no orphaned logos or signatures


def _stored_files(media):
    return sorted(os.path.join(root, name) for root, _, names in os.walk(media) for name in names)


class TaskTests(ImportBase):
    def make_run(self, **over):
        options = {"index_file": os.path.join(self.dir, "rows.json"), "v1_dir": self.dir}
        options.update(over.pop("options", {}))
        return ImportRun.objects.create(dry_run=over.pop("dry_run", True), options=options)

    def setUp(self):
        super().setUp()
        with open(os.path.join(self.dir, "rows.json"), "w", encoding="utf-8") as handle:
            json.dump(self.rows, handle, ensure_ascii=False)

    def test_a_run_goes_queued_running_succeeded_and_stores_the_report(self):
        run = self.make_run()
        self.assertEqual(tasks.import_v1.apply(args=(run.pk,)).get(), "succeeded")
        run.refresh_from_db()
        self.assertEqual((run.status, run.total, run.processed), (ImportStatus.SUCCEEDED, 10, 10))
        self.assertEqual(run.counts["would_create"], 8)
        self.assertEqual(len(run.report), 10)
        self.assertTrue(all({"position", "code", "title", "action", "notes"} <= set(e) for e in run.report))
        self.assertIsNotNone(run.started_at)
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(Document.objects.count(), 0)  # dry run

    def test_a_commit_run_writes(self):
        run = self.make_run(dry_run=False)
        tasks.import_v1.apply(args=(run.pk,))
        run.refresh_from_db()
        self.assertEqual((run.status, run.counts["created"]), (ImportStatus.SUCCEEDED, 8))
        event = DocumentEvent.objects.filter(kind=DocumentEventKind.IMPORTED).first()
        self.assertIn(f"شمارهٔ {run.pk}", event.reason)  # every imported document points back at its run

    def test_a_redelivered_or_unknown_run_is_a_no_op(self):
        run = self.make_run()
        tasks.import_v1.apply(args=(run.pk,))
        self.assertEqual(tasks.import_v1.apply(args=(run.pk,)).get(), "skipped")
        self.assertEqual(tasks.import_v1.apply(args=(999999,)).get(), "skipped")

    def test_failures_end_as_a_failed_run_with_a_persian_message(self):
        run = self.make_run(options={"v1_dir": "/nonexistent-dir"})
        self.assertEqual(tasks.import_v1.apply(args=(run.pk,)).get(), "failed")
        run.refresh_from_db()
        self.assertEqual(run.status, ImportStatus.FAILED)
        self.assertEqual(run.error, tasks.FAILED_NO_DATA_DIR)

        run = self.make_run(options={"index_file": "/nonexistent.json"})
        tasks.import_v1.apply(args=(run.pk,))
        run.refresh_from_db()
        self.assertIn("یافت نشد", run.error)

        run = self.make_run()
        with mock.patch.object(loader, "run_import", side_effect=RuntimeError("secret-internal-detail")):
            tasks.import_v1.apply(args=(run.pk,))
        run.refresh_from_db()
        self.assertEqual(run.error, tasks.FAILED_UNEXPECTED)
        self.assertNotIn("secret-internal-detail", run.error)

    def test_no_secret_reaches_the_run_record(self):
        uri = "mongo" + "db://user:TOPSECRETPASSWORD@db.example.invalid:27017/"

        class Boom(Exception):
            pass

        fake = mock.MagicMock()
        fake.MongoClient.side_effect = Boom("cannot reach " + uri)
        run = ImportRun.objects.create(dry_run=True, options={"mongo_uri_env": "V1_TEST_URI", "v1_dir": self.dir})
        with mock.patch.dict(os.environ, {"V1_TEST_URI": uri}), mock.patch.dict("sys.modules", {"pymongo": fake}):
            tasks.import_v1.apply(args=(run.pk,))
        run.refresh_from_db()
        dump = json.dumps([run.options, run.error, run.counts, run.report], ensure_ascii=False)
        self.assertEqual(run.status, ImportStatus.FAILED)
        self.assertNotIn("TOPSECRETPASSWORD", dump)
        self.assertNotIn("db.example.invalid", dump)
        self.assertIn("V1_TEST_URI", dump)  # only the variable's *name* is recorded


class CommandTests(ImportBase):
    def setUp(self):
        super().setUp()
        self.index = os.path.join(self.dir, "rows.json")
        with open(self.index, "w", encoding="utf-8") as handle:
            json.dump(self.rows, handle, ensure_ascii=False)

    def call(self, *args):
        out = io.StringIO()
        call_command("import_v1", *args, stdout=out)
        return out.getvalue()

    def test_default_is_a_dry_run_that_says_so_and_writes_nothing(self):
        text = self.call("--index-file", self.index, "--v1-dir", self.dir, "--sync")
        self.assertIn("آزمایشی", text)
        self.assertIn("--commit", text)
        self.assertIn("ایجاد می‌شد: 8", text)
        self.assertEqual(Document.objects.count(), 0)
        self.assertTrue(ImportRun.objects.get().dry_run)

    def test_commit_writes_and_prints_the_notable_lines_in_persian(self):
        text = self.call("--index-file", self.index, "--v1-dir", self.dir, "--sync", "--commit")
        self.assertEqual(Document.objects.count(), 8)
        self.assertIn("ایجاد‌شده: 8", text)
        self.assertIn("شمارهٔ بازنگری نامعتبر است", text)   # the bad row is printed
        self.assertNotIn("--commit", text)                    # no "use --commit" hint after a real run

    def test_report_file_and_status(self):
        report = os.path.join(self.dir, "report.json")
        self.call("--index-file", self.index, "--v1-dir", self.dir, "--sync", "--report-file", report)
        data = json.load(open(report, encoding="utf-8"))
        self.assertEqual((data["dry_run"], len(data["report"])), (True, 10))
        run = ImportRun.objects.get()
        self.assertIn("ایجاد می‌شد: 8", self.call("--status", str(run.pk)))
        with self.assertRaises(CommandError):
            self.call("--status", "999")

    def test_exactly_one_source_is_required(self):
        with self.assertRaises(CommandError):
            self.call("--v1-dir", self.dir)
        with self.assertRaises(CommandError):
            self.call("--index-file", self.index, "--mongo-uri-env", "X", "--v1-dir", self.dir)

    def test_a_failed_run_is_a_command_error(self):
        with self.assertRaises(CommandError) as ctx:
            self.call("--index-file", "/nonexistent.json", "--v1-dir", self.dir, "--sync")
        self.assertIn("ناموفق", str(ctx.exception))

    def test_refuses_to_start_while_another_import_is_running(self):
        ImportRun.objects.create(status=ImportStatus.RUNNING, started_at=timezone.now(), options={})
        with self.assertRaises(CommandError):
            self.call("--index-file", self.index, "--v1-dir", self.dir, "--sync")
        # …but a run that died long ago doesn't block forever.
        ImportRun.objects.update(started_at=timezone.now() - timezone.timedelta(hours=3))
        self.call("--index-file", self.index, "--v1-dir", self.dir, "--sync")

    def test_the_mongo_uri_value_is_never_stored(self):
        uri = "mongo" + "db://user:HUNTER2@host.invalid/"
        fake = mock.MagicMock()
        fake.MongoClient.return_value.__getitem__.return_value.__getitem__.return_value.find.return_value = self.rows
        with mock.patch.dict(os.environ, {"V1_TEST_URI": uri}), mock.patch.dict("sys.modules", {"pymongo": fake}):
            self.call("--mongo-uri-env", "V1_TEST_URI", "--v1-dir", self.dir, "--sync")
        run = ImportRun.objects.get()
        self.assertEqual(run.status, ImportStatus.SUCCEEDED)
        self.assertEqual(run.options["mongo_uri_env"], "V1_TEST_URI")
        self.assertNotIn("HUNTER2", json.dumps([run.options, run.report]))
        fake.MongoClient.assert_called_once()
