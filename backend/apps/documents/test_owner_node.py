"""A document belongs to an org-chart node (Phase 14, owner's decision 2026-09-30): chosen when the
document is created from the nodes the creator leads (or below), inherited by revisions, changeable
while a draft, protected from deleting its node, and listed in the register."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.core.constants import DocumentGroup, DocumentStatus
from apps.core.exceptions import ConflictError
from apps.organization import tree

from . import authority, services
from .models import Document
from .test_support import lead_of, make_managing_director, make_org, make_person, member_of
from .tests import LOCMEM_CACHE, finalize


class Fixture:
    def setUp(self):
        super().setUp()
        self.org = make_org()
        self.ceo = make_managing_director()
        self.section_lead = make_person()
        lead_of(self.section_lead, self.org.rag)
        self.unit_lead = make_person()
        lead_of(self.unit_lead, self.org.ai)
        self.domain_lead = make_person()
        lead_of(self.domain_lead, self.org.it)
        self.member = make_person()
        member_of(self.member, self.org.rag)
        self.nobody = make_person()
        self.client = APIClient(enforce_csrf_checks=False)

    def as_(self, user):
        self.client.force_authenticate(user)
        return self

    def create(self, user, owner_node="unset", title="سند", **extra):
        payload = {"category": "INSIDE", "title": title, "group": "PROCEDURE", **extra}
        if owner_node != "unset":
            payload["owner_node"] = owner_node.pk if hasattr(owner_node, "pk") else owner_node
        self.as_(user)
        return self.client.post(reverse("document-list"), payload, format="json")

    def names(self, user):
        self.as_(user)
        return [row["name"] for row in self.client.get(reverse("document-owner-nodes")).data]


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class EligibleNodesTests(Fixture, TestCase):
    def test_a_section_lead_may_pick_only_their_section(self):
        self.assertEqual(self.names(self.section_lead), ["RAG"])

    def test_a_unit_lead_may_pick_the_unit_and_its_sections(self):
        self.assertEqual(self.names(self.unit_lead), ["هوش مصنوعی", "RAG", "LLM"])

    def test_a_domain_lead_may_pick_everything_beneath_the_domain(self):
        self.assertEqual(
            self.names(self.domain_lead), ["IT", "هوش مصنوعی", "RAG", "LLM", "توسعه", "Backend"]
        )

    def test_the_managing_director_may_pick_any_active_node_including_the_company(self):
        names = self.names(self.ceo)
        self.assertIn("شرکت", names)
        self.assertEqual(len(names), 12)

    def test_a_plain_member_and_a_person_without_a_placement_may_pick_nothing(self):
        self.assertEqual(self.names(self.member), [])
        self.assertEqual(self.names(self.nobody), [])

    def test_the_developer_account_may_pick_nothing(self):
        developer = make_person(is_developer=True, roll=AccessRoll.GUILD, level=AccessLevel.LEVEL_3)
        self.assertEqual(self.names(developer), [])

    def test_an_archived_node_is_not_offered_and_its_lead_loses_it(self):
        tree.archive_node(self.org.llm)
        self.assertEqual(self.names(self.unit_lead), ["هوش مصنوعی", "RAG"])
        tree.archive_node(self.org.rag)
        tree.archive_node(self.org.ai)
        self.assertEqual(self.names(self.unit_lead), [])

    def test_the_choices_carry_a_readable_label(self):
        self.as_(self.domain_lead)
        rows = {r["name"]: r for r in self.client.get(reverse("document-owner-nodes")).data}
        self.assertEqual(rows["RAG"]["label"], "IT › هوش مصنوعی › RAG")
        self.assertEqual(rows["IT"]["label"], "IT")
        self.assertEqual(rows["RAG"]["kind"], "SECTION")

    def test_it_needs_a_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse("document-owner-nodes")).status_code, 401)

    def test_is_managing_director(self):
        self.assertTrue(authority.is_managing_director(self.ceo))
        self.assertTrue(authority.is_managing_director(make_person(is_superuser=True)))
        for user in (self.unit_lead, self.domain_lead, self.member):
            self.assertFalse(authority.is_managing_director(user))
        self.assertFalse(authority.is_managing_director(make_person(roll=AccessRoll.EMPLOYER, level=AccessLevel.LEVEL_2)))


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class CreateWithOwnerNodeTests(Fixture, TestCase):
    def test_a_lead_creates_a_document_for_a_node_in_their_scope(self):
        response = self.create(self.unit_lead, self.org.llm)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["owner_node"], {"id": self.org.llm.pk, "name": "LLM", "kind": "SECTION", "kind_label": "بخش"})
        self.assertEqual(Document.objects.get(pk=response.data["id"]).owner_node, self.org.llm)

    def test_a_node_outside_their_scope_is_refused_in_persian(self):
        response = self.create(self.unit_lead, self.org.backend)
        self.assertEqual(response.status_code, 400)
        self.assertIn("معتبر نیست", str(response.data["owner_node"]))
        self.assertFalse(Document.objects.exists())

    def test_a_node_above_their_own_is_refused(self):
        self.assertEqual(self.create(self.section_lead, self.org.ai).status_code, 400)
        self.assertEqual(self.create(self.unit_lead, self.org.it).status_code, 400)

    def test_an_unknown_or_archived_node_is_refused(self):
        self.assertEqual(self.create(self.unit_lead, 99999999).status_code, 400)
        tree.archive_node(self.org.llm)
        self.assertEqual(self.create(self.unit_lead, self.org.llm).status_code, 400)

    def test_the_managing_director_may_own_a_document_at_the_company(self):
        self.assertEqual(self.create(self.ceo, self.org.root).status_code, 201)

    def test_the_owner_node_is_optional_for_now(self):
        response = self.create(self.nobody, title="بدون گره")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data["owner_node"])

    def test_a_revision_keeps_the_owner_node(self):
        doc = finalize(services.create_document(user=self.ceo, category="INSIDE", title="ت", group="PROCEDURE", owner_node=self.org.ai))
        revision = services.create_revision(user=self.ceo, document_id=doc.pk)
        self.assertEqual(revision.owner_node, self.org.ai)


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class ChangeOwnerNodeTests(Fixture, TestCase):
    def setUp(self):
        super().setUp()
        self.doc = services.create_document(user=self.domain_lead, category="INSIDE", title="ت", group="PROCEDURE", owner_node=self.org.ai)

    def move(self, user, node, doc=None):
        self.as_(user)
        return self.client.post(reverse("document-owner-node", args=[(doc or self.doc).pk]), {"owner_node": node.pk}, format="json")

    def test_a_draft_can_be_moved_to_another_node_in_scope(self):
        response = self.move(self.domain_lead, self.org.backend)
        self.assertEqual(response.status_code, 200, response.data)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.owner_node, self.org.backend)
        self.assertEqual(response.data["owner_node"]["name"], "Backend")

    def test_not_to_a_node_outside_scope(self):
        self.assertEqual(self.move(self.unit_lead, self.org.deals).status_code, 400)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.owner_node, self.org.ai)

    def test_a_document_with_no_node_can_be_given_one(self):
        orphan = services.create_document(user=self.domain_lead, category="INSIDE", title="یتیم", group="POSTER")
        self.assertIsNone(orphan.owner_node)
        self.assertEqual(self.move(self.domain_lead, self.org.dev, orphan).status_code, 200)

    def test_only_a_draft_can_move(self):
        finalize(self.doc, DocumentStatus.UNDER_CONTROL)
        response = self.move(self.domain_lead, self.org.dev)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "content_locked")

    def test_the_node_id_is_required(self):
        self.as_(self.domain_lead)
        response = self.client.post(reverse("document-owner-node", args=[self.doc.pk]), {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_it_needs_the_authoring_capability(self):
        self.assertEqual(self.move(make_person(roll=AccessRoll.EMPLOYER, level=AccessLevel.LEVEL_2), self.org.dev).status_code, 403)


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class RegisterAndDeletionTests(Fixture, TestCase):
    def test_the_register_lists_each_documents_node_without_extra_queries(self):
        for i in range(6):
            services.create_document(user=self.ceo, category="INSIDE", title=f"سند {i}", group="POSTER", owner_node=self.org.ai)
        self.as_(self.member)
        with self.assertNumQueries(4):  # count + page + sign-offs + responsibility sections
            rows = self.client.get(reverse("document-list")).data["results"]
        self.assertEqual({r["owner_node"]["name"] for r in rows}, {"هوش مصنوعی"})

    def test_a_node_that_owns_a_document_cannot_be_deleted_and_says_how_many(self):
        services.create_document(user=self.ceo, category="INSIDE", title="الف", group="POSTER", owner_node=self.org.llm)
        services.create_document(user=self.ceo, category="INSIDE", title="ب", group="POSTER", owner_node=self.org.llm)
        with self.assertRaises(ConflictError) as raised:
            tree.delete_node(self.org.llm)
        self.assertEqual(raised.exception.payload["code"], "node_not_empty")
        self.assertEqual(raised.exception.payload["documents"], 2)

    def test_the_api_answers_409_with_the_count(self):
        services.create_document(user=self.ceo, category="INSIDE", title="الف", group="POSTER", owner_node=self.org.llm)
        self.as_(self.ceo)
        response = self.client.delete(reverse("org-node-detail", args=[self.org.llm.pk]))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["documents"], 1)

    def test_an_archived_node_keeps_its_documents(self):
        doc = services.create_document(user=self.ceo, category="INSIDE", title="الف", group="POSTER", owner_node=self.org.llm)
        tree.archive_node(self.org.llm)
        doc.refresh_from_db()
        self.assertEqual(doc.owner_node, self.org.llm)


class ExistingDocumentsGetANodeTests(TransactionTestCase):
    """Migration 0009: the author's primary placement, else the company."""

    BEFORE = [("documents", "0008_responsibility_rows_by_unit")]
    AFTER = [("documents", "0009_document_owner_node")]

    def migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def setUp(self):
        self.migrate(self.BEFORE)
        org = make_org()
        placed, unplaced, archived = make_person(), make_person(), make_person()
        member_of(placed, org.dev)
        member_of(archived, org.llm)
        tree.archive_node(org.llm)
        old = self.migrate(self.BEFORE)
        Document = old.get_model("documents", "Document")
        self.ids = {}
        for name, user in (("placed", placed), ("unplaced", unplaced), ("archived", archived)):
            document = Document.objects.create(
                category="INSIDE", title=name, group="PROCEDURE", number=len(self.ids) + 1, revision=1, created_by_id=user.pk
            )
            self.ids[name] = document.pk
        self.org = org
        self.new = self.migrate(self.AFTER)

    def tearDown(self):
        self.migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())

    def owner(self, name):
        return self.new.get_model("documents", "Document").objects.get(pk=self.ids[name]).owner_node_id

    def test_a_placed_author_brings_the_document_to_their_primary_node(self):
        self.assertEqual(self.owner("placed"), self.org.dev.pk)

    def test_everyone_else_gets_the_company(self):
        self.assertEqual(self.owner("unplaced"), self.org.root.pk)
        self.assertEqual(self.owner("archived"), self.org.root.pk, "an archived placement is not a home")
