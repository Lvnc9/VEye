"""Who may write, confirm and approve a document — the org chart's answer (Phase 14, the owner's rules of
2026-09-30). Table-driven: every kind of person against every owner-node position, checked against an
independent walk up the parents (the implementation uses path prefixes)."""
from django.test import TestCase

from apps.accounts.models import AccessLevel, AccessRoll, Capability
from apps.core.constants import DocumentCategory, DocumentGroup
from apps.organization import tree
from apps.organization.models import Membership, OrgNode, OrgNodeKind

from . import authority, services
from .models import Document
from .test_support import lead_of, make_managing_director, make_org, make_person, member_of

CONFIRMING = {OrgNodeKind.UNIT, OrgNodeKind.DOMAIN, OrgNodeKind.COMPANY}


def chain(node):
    """`node` and every node above it, by walking the parents."""
    while node is not None:
        yield node
        node = node.parent


class People:
    def build_people(self):
        self.org = make_org()
        o = self.org
        self.people = {
            "ceo": make_managing_director(),
            "superuser": make_person(is_superuser=True),
            "company lead": make_person(),
            "domain lead (IT)": make_person(),
            "unit lead (ai)": make_person(),
            "unit lead (qms, under the company)": make_person(),
            "section lead (rag)": make_person(),
            "section lead (llm)": make_person(),
            "lead of two": make_person(),
            "member of rag": make_person(),
            "no placement": make_person(),
            "board member (کارفرمایی ۲)": make_person(roll=AccessRoll.EMPLOYER, level=AccessLevel.LEVEL_2),
            "senior staff (ستادی ۱)": make_person(roll=AccessRoll.HEADQUARTERS, level=AccessLevel.LEVEL_1),
            "developer": make_person(is_developer=True),
            "inactive lead": make_person(is_active=False),
        }
        p = self.people
        lead_of(p["company lead"], o.root)
        lead_of(p["domain lead (IT)"], o.it)
        lead_of(p["unit lead (ai)"], o.ai)
        lead_of(p["unit lead (qms, under the company)"], o.qms)
        lead_of(p["section lead (rag)"], o.rag)
        lead_of(p["section lead (llm)"], o.llm)
        lead_of(p["lead of two"], o.rag)
        lead_of(p["lead of two"], o.deals)
        member_of(p["member of rag"], o.rag)
        # The inactive person leads the company on paper; an inactive account acts on nothing.
        Membership.objects.create(user=p["inactive lead"], node=o.root, is_lead=True, is_primary=True)
        Membership.objects.create(user=p["developer"], node=o.root, is_lead=True, is_primary=True)
        self.nodes = [o.root, o.it, o.sales, o.ai, o.dev, o.deals, o.qms, o.rag, o.llm, o.backend, o.cash, o.quality]
        self.docs = {
            node.pk: services.create_document(
                user=p["ceo"], category=DocumentCategory.INSIDE, title=f"سند {node.name}", group=DocumentGroup.POSTER,
                owner_node=node,
            )
            for node in self.nodes
        }

    def expected(self, name, node):
        """(author, confirm, approve) for `name` on a document owned by `node`, worked out by walking up."""
        user = self.people[name]
        if not user.is_active or user.is_developer:
            return (False, False, False)
        if name in ("ceo", "superuser"):
            return (True, True, True)
        led = [m.node for m in Membership.objects.filter(user=user, is_lead=True, node__is_active=True).select_related("node")]
        above = list(chain(node))
        author = any(n in above for n in led)
        confirm = any(n in above and n.kind in CONFIRMING for n in led)
        return (author, confirm, False)


class DocumentAuthorityTableTests(People, TestCase):
    def setUp(self):
        self.build_people()

    def test_every_person_against_every_owner_node(self):
        for name in self.people:
            authority_for = authority.DocumentAuthority(self.people[name])
            for node in self.nodes:
                doc = Document.objects.select_related("owner_node").get(pk=self.docs[node.pk].pk)
                got = (authority_for.can_author(doc), authority_for.can_confirm(doc), authority_for.can_approve(doc))
                with self.subTest(person=name, node=node.name):
                    self.assertEqual(got, self.expected(name, node))

    def test_the_rules_in_words(self):
        o = self.org
        doc = lambda node: Document.objects.select_related("owner_node").get(pk=self.docs[node.pk].pk)
        rag_lead = authority.DocumentAuthority(self.people["section lead (rag)"])
        self.assertTrue(rag_lead.can_author(doc(o.rag)))
        self.assertFalse(rag_lead.can_author(doc(o.llm)), "not a sibling بخش")
        self.assertFalse(rag_lead.can_author(doc(o.ai)), "not the واحد above")
        self.assertFalse(rag_lead.can_confirm(doc(o.rag)), "a بخش's lead never confirms")
        unit = authority.DocumentAuthority(self.people["unit lead (ai)"])
        self.assertTrue(unit.can_author(doc(o.ai)) and unit.can_confirm(doc(o.ai)), "a واحد's lead writes and confirms its own")
        self.assertTrue(unit.can_author(doc(o.rag)) and unit.can_confirm(doc(o.rag)), "…and its بخش‌ها'")
        self.assertFalse(unit.can_author(doc(o.it)), "not the حوزه above")
        domain = authority.DocumentAuthority(self.people["domain lead (IT)"])
        for node in (o.it, o.ai, o.dev, o.rag, o.llm, o.backend):
            self.assertTrue(domain.can_author(doc(node)) and domain.can_confirm(doc(node)), node.name)
        for node in (o.sales, o.deals, o.qms, o.root):
            self.assertFalse(domain.can_author(doc(node)), node.name)
        self.assertFalse(any(authority.DocumentAuthority(user).can_approve(doc(o.rag)) for name, user in self.people.items() if name not in ("ceo", "superuser")))

    def test_the_company_lead_who_is_not_the_managing_director_does_not_approve(self):
        lead = authority.DocumentAuthority(self.people["company lead"])
        self.assertTrue(all(lead.can_author(d) and lead.can_confirm(d) for d in Document.objects.select_related("owner_node")))
        self.assertFalse(lead.can_approve())

    def test_a_document_with_no_owner_node_is_acted_on_by_the_managing_director_only(self):
        orphan = services.create_document(user=self.people["ceo"], category="INSIDE", title="یتیم", group="POSTER")
        for name, user in self.people.items():
            acts = authority.DocumentAuthority(user)
            self.assertEqual(
                (acts.can_author(orphan), acts.can_confirm(orphan)), (name in ("ceo", "superuser"),) * 2, name
            )

    def test_an_archived_nodes_lead_loses_what_they_led(self):
        unit_lead = self.people["unit lead (ai)"]
        rag_doc = Document.objects.select_related("owner_node").get(pk=self.docs[self.org.rag.pk].pk)
        self.assertTrue(authority.DocumentAuthority(unit_lead).can_author(rag_doc))
        tree.archive_node(self.org.rag)
        tree.archive_node(self.org.llm)
        tree.archive_node(self.org.ai)
        self.assertFalse(authority.DocumentAuthority(unit_lead).can_author(rag_doc))

    def test_what_the_anywhere_flags_say(self):
        for name, user in self.people.items():
            acts = authority.DocumentAuthority(user)
            author_anywhere = any(self.expected(name, n)[0] for n in self.nodes)
            confirm_anywhere = any(self.expected(name, n)[1] for n in self.nodes)
            with self.subTest(person=name):
                self.assertEqual((acts.can_author_anywhere, acts.can_confirm_anywhere), (author_anywhere, confirm_anywhere))

    def test_the_querysets_agree_with_the_per_document_answers(self):
        """The dashboard filters in SQL; the register asks per document. They must never disagree."""
        everything = list(Document.objects.select_related("owner_node"))
        for name, user in self.people.items():
            acts = authority.DocumentAuthority(user)
            by_query_author = set(Document.objects.filter(acts.authoring_q()).values_list("pk", flat=True))
            by_query_confirm = set(Document.objects.filter(acts.confirming_q()).values_list("pk", flat=True))
            with self.subTest(person=name):
                self.assertEqual(by_query_author, {d.pk for d in everything if acts.can_author(d)})
                self.assertEqual(by_query_confirm, {d.pk for d in everything if acts.can_confirm(d)})

    def test_me_capabilities_follow_the_chart(self):
        for name, user in self.people.items():
            held = authority.effective_capabilities(user)
            acts = authority.DocumentAuthority(user)
            with self.subTest(person=name):
                self.assertEqual(Capability.CREATE_DOCUMENT in held, acts.can_author_anywhere or Capability.CREATE_DOCUMENT in user.capabilities)
                self.assertEqual(Capability.APPROVE_DOCUMENT in held, name in ("ceo", "superuser"))
        self.assertIn(Capability.CONFIRM_DOCUMENT, authority.effective_capabilities(self.people["unit lead (ai)"]))
        self.assertNotIn(Capability.CONFIRM_DOCUMENT, authority.effective_capabilities(self.people["section lead (rag)"]))
        self.assertNotIn(Capability.CREATE_DOCUMENT, authority.effective_capabilities(self.people["member of rag"]))

    def test_the_owner_node_choices_are_exactly_the_authoring_scope(self):
        for name, user in self.people.items():
            ids = set(authority.eligible_owner_nodes(user).values_list("pk", flat=True))
            with self.subTest(person=name):
                self.assertEqual(ids, {n.pk for n in OrgNode.objects.filter(is_active=True) if self.expected(name, n)[0]})

    def test_one_lead_query_per_request_however_many_documents(self):
        acts = authority.DocumentAuthority(self.people["unit lead (ai)"])
        docs = list(Document.objects.select_related("owner_node"))
        with self.assertNumQueries(1):
            for doc in docs * 3:
                acts.can_author(doc)
                acts.can_confirm(doc)
