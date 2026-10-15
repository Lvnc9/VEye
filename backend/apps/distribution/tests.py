import shutil
import tempfile
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll
from apps.core.constants import DocumentStatus, SectionType
from apps.documents import test_support
from apps.documents.models import Document, ResponsibilityRow, Section
from apps.documents.test_workflow import WorkflowBase, make_user
from apps.notifications.models import Notification, NotificationKind

from .models import ReadAcknowledgment

MEDIA = tempfile.mkdtemp(prefix="veye-distribution-media-")


def tearDownModule():
    shutil.rmtree(MEDIA, ignore_errors=True)


@override_settings(MEDIA_ROOT=MEDIA)
class DistributionBase(WorkflowBase):
    """The document belongs to بخش RAG (under واحد هوش مصنوعی); its مسئولیت ها block names واحد توسعه."""

    def setUp(self):
        super().setUp()
        self.rag_member = make_user("8300000001", AccessRoll.GUILD)
        test_support.member_of(self.rag_member, self.org.rag)
        self.dev_member = make_user("8300000002", AccessRoll.GUILD)
        test_support.member_of(self.dev_member, self.org.backend)  # بخش Backend, beneath واحد توسعه
        self.outsider = make_user("8300000003", AccessRoll.GUILD)
        test_support.member_of(self.outsider, self.org.cash)
        self.retired = make_user("8300000004", AccessRoll.GUILD)
        test_support.member_of(self.retired, self.org.rag)
        type(self.retired).objects.filter(pk=self.retired.pk).update(is_active=False)  # placed, then deactivated
        section = Section.objects.create(document=self.doc, type=SectionType.RESPONSIBILITIES, position=0, content={})
        ResponsibilityRow.objects.create(section=section, position=0, unit=self.org.dev, unit_name="توسعه", text="اجرا")

    def approve(self, doc=None):
        return self.run_chain(doc)

    def readers(self, doc=None):
        return {
            row.user_id: row.acknowledged_at is not None
            for row in ReadAcknowledgment.objects.filter(document=doc or self.doc)
        }

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client


class DistributeTests(DistributionBase):
    def test_approval_asks_the_owner_node_and_the_responsible_units(self):
        self.approve()
        readers = self.readers()
        self.assertIn(self.rag_member.pk, readers)
        self.assertIn(self.dev_member.pk, readers)  # beneath the واحد named in مسئولیت ها
        self.assertIn(self.author.pk, readers)  # the RAG lead
        self.assertNotIn(self.outsider.pk, readers)
        self.assertNotIn(self.retired.pk, readers)
        self.assertFalse(readers[self.rag_member.pk])

    def test_the_signers_count_as_having_read_it(self):
        self.approve()
        self.assertTrue(self.readers()[self.author.pk])  # signed as تهیه‌کننده

    def test_the_readers_are_told_but_not_the_signers(self):
        self.approve()
        told = set(Notification.objects.filter(kind=NotificationKind.DOCUMENT_TO_READ).values_list("recipient_id", flat=True))
        self.assertIn(self.rag_member.pk, told)
        self.assertIn(self.dev_member.pk, told)
        self.assertNotIn(self.author.pk, told)
        self.assertNotIn(self.outsider.pk, told)

    def test_distributing_twice_asks_nobody_twice(self):
        from . import services

        self.approve()
        before = ReadAcknowledgment.objects.count()
        self.assertEqual(services.distribute(Document.objects.get(pk=self.doc.pk)), 0)
        self.assertEqual(ReadAcknowledgment.objects.count(), before)

    def test_the_developer_account_is_never_asked(self):
        developer = make_user("8300000009", AccessRoll.GUILD, AccessLevel.LEVEL_3, is_developer=True)
        test_support.member_of(developer, self.org.rag)
        self.approve()
        self.assertNotIn(developer.pk, self.readers())

    def test_a_new_revision_asks_again(self):
        first = self.approve()
        response = self.client_for(self.author).post(reverse("document-revise", args=[first.pk]))
        second = Document.objects.get(pk=response.data["id"])
        Document.objects.filter(pk=second.pk).update(content_saved_at=first.content_saved_at)
        self.approve(second)
        self.assertIn(self.rag_member.pk, self.readers(second))
        self.assertFalse(self.readers(second)[self.rag_member.pk])


class AcknowledgeTests(DistributionBase):
    def setUp(self):
        super().setUp()
        self.approve()

    def ack(self, user, doc=None):
        return self.client_for(user).post(reverse("distribution-acknowledge", args=[(doc or self.doc).pk]))

    def pending_ids(self, user):
        return [r["document"]["id"] for r in self.client_for(user).get(reverse("distribution-pending")).data["results"]]

    def test_a_reader_acknowledges_once(self):
        self.assertEqual(self.pending_ids(self.rag_member), [self.doc.pk])
        first = self.ack(self.rag_member)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.ack(self.rag_member).data["acknowledged_at"], first.data["acknowledged_at"])
        self.assertTrue(self.readers()[self.rag_member.pk])
        self.assertEqual(self.pending_ids(self.rag_member), [])

    def test_someone_not_asked_cannot_acknowledge(self):
        self.assertEqual(self.ack(self.outsider).status_code, 404)
        self.assertFalse(ReadAcknowledgment.objects.filter(user=self.outsider).exists())

    def test_a_superseded_revision_drops_out_and_cannot_be_acknowledged(self):
        Document.objects.filter(pk=self.doc.pk).update(status=DocumentStatus.OBSOLETE)
        self.assertEqual(self.pending_ids(self.rag_member), [])
        response = self.ack(self.rag_member)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "not_in_force")

    def test_the_kartable_counts_what_is_left_to_read(self):
        summary = self.client_for(self.rag_member).get(reverse("dashboard-inbox")).data
        self.assertEqual(summary["to_read"], 1)
        self.assertEqual(
            summary["total"],
            summary["unread_messages"] + summary["awaiting_documents"] + summary["due_objectives"]
            + summary["unread_notifications"] + summary["to_read"],
        )
        self.ack(self.rag_member)
        self.assertEqual(self.client_for(self.rag_member).get(reverse("dashboard-inbox")).data["to_read"], 0)


class CoverageTests(DistributionBase):
    def setUp(self):
        super().setUp()
        self.approve()

    def coverage(self, user):
        return self.client_for(user).get(reverse("distribution-coverage", args=[self.doc.pk]))

    def test_authors_see_who_has_read_it(self):
        self.client_for(self.rag_member).post(reverse("distribution-acknowledge", args=[self.doc.pk]))
        body = self.coverage(self.author).data
        self.assertEqual(body["total"], len(self.readers()))
        self.assertEqual(body["acknowledged"], sum(self.readers().values()))
        names = {group["node_name"] for group in body["groups"]}
        self.assertIn("RAG", names)
        self.assertIn("Backend", names)

    def test_reports_holders_see_it_and_others_do_not(self):
        board = make_user("8300000010", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)  # کارفرمایی: view_reports
        self.assertEqual(self.coverage(board).status_code, 200)
        self.assertEqual(self.coverage(self.rag_member).status_code, 403)
        self.assertEqual(self.coverage(self.outsider).status_code, 403)

    def test_the_reading_status_for_the_designer(self):
        body = self.client_for(self.rag_member).get(reverse("distribution-document", args=[self.doc.pk])).data
        self.assertEqual(body["mine"], {"acknowledged_at": None})
        self.assertFalse(body["can_view_coverage"])
        self.assertIsNone(body["total"])
        body = self.client_for(self.outsider).get(reverse("distribution-document", args=[self.doc.pk])).data
        self.assertIsNone(body["mine"])
        body = self.client_for(self.author).get(reverse("distribution-document", args=[self.doc.pk])).data
        self.assertTrue(body["can_view_coverage"])
        self.assertEqual(body["total"], len(self.readers()))


class BackfillCommandTests(DistributionBase):
    def test_dry_run_then_apply(self):
        Document.objects.filter(pk=self.doc.pk).update(status=DocumentStatus.UNDER_CONTROL)
        out = StringIO()
        call_command("distribute_documents", stdout=out)
        self.assertIn("dry run", out.getvalue())
        self.assertFalse(ReadAcknowledgment.objects.exists())
        call_command("distribute_documents", "--apply", stdout=StringIO())
        self.assertIn(self.rag_member.pk, self.readers())
        out = StringIO()
        call_command("distribute_documents", "--apply", stdout=out)  # nothing left to distribute
        self.assertIn("0 reader", out.getvalue())
