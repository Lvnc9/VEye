import io
import os
import shutil
import tempfile
import threading

from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from PIL import Image
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, Capability, User
from apps.accounts.tests import LOCMEM_CACHE, make_user
from apps.core.exceptions import ConflictError
from apps.core.text import normalize_search_term

from . import memberships, queries, tree
from .models import ALLOWED_PARENT_KINDS, Company, Membership, OrgNode, OrgNodeKind, SetupStep

COMPANY, DOMAIN, UNIT, SECTION = (
    OrgNodeKind.COMPANY,
    OrgNodeKind.DOMAIN,
    OrgNodeKind.UNIT,
    OrgNodeKind.SECTION,
)


def make_company(name="شرکت نمونه"):
    """What bootstrap will do (slice 7.4): the root node, then the Company(pk=1) row."""
    root = tree.create_root(name=name)
    Company.objects.create(pk=1, root=root, setup_step=SetupStep.DOMAINS)
    return root


def add(kind, name, parent):
    return tree.create_node(kind=kind, name=name, parent=parent)


class TreeAssertions:
    def assert_tree_consistent(self):
        """The invariants tree.py owns, checked on every row: they are what the access layer
        will rely on, so every mutating test ends with this."""
        nodes = {node.pk: node for node in OrgNode.objects.all()}
        for node in nodes.values():
            parent = nodes.get(node.parent_id)
            expected_path = (parent.path if parent else "") + f"{node.pk:010d}/"
            self.assertEqual(node.path, expected_path, node)
            self.assertEqual(node.depth, parent.depth + 1 if parent else 0, node)
            self.assertEqual(node.parent_kind, parent.kind if parent else "", node)
            self.assertIn(node.parent_kind, ALLOWED_PARENT_KINDS[node.kind], node)


class SampleTree(TreeAssertions):
    """company ─ D1 ─ U1 ─ S1
                    └ U2
               └ D2 ─ U3
               └ U4 (a واحد straight under the company)"""

    def build(self):
        self.root = make_company()
        self.d1 = add(DOMAIN, "حوزه یک", self.root)
        self.d2 = add(DOMAIN, "حوزه دو", self.root)
        self.u1 = add(UNIT, "واحد فروش", self.d1)
        self.u2 = add(UNIT, "واحد مالی", self.d1)
        self.u3 = add(UNIT, "واحد فروش", self.d2)  # same name as u1: siblings only must differ
        self.u4 = add(UNIT, "واحد مستقل", self.root)
        self.s1 = add(SECTION, "بخش یک", self.u1)


class TreeCreationTests(SampleTree, TestCase):
    def setUp(self):
        self.build()

    def test_the_root_is_depth_zero_with_its_own_id_as_its_path(self):
        self.assertEqual(self.root.depth, 0)
        self.assertEqual(self.root.path, f"{self.root.pk:010d}/")
        self.assertEqual(self.root.parent_kind, "")
        self.assertIsNone(self.root.parent_id)

    def test_path_and_depth_follow_the_parent(self):
        self.assertEqual(self.s1.path, self.root.path + f"{self.d1.pk:010d}/{self.u1.pk:010d}/{self.s1.pk:010d}/")
        self.assertEqual([n.depth for n in (self.d1, self.u1, self.s1)], [1, 2, 3])
        self.assertEqual(self.s1.parent_kind, UNIT)
        self.assert_tree_consistent()

    def test_a_company_with_no_domain_is_valid(self):
        # A واحد straight under the company: depth 1, so depth cannot be derived from kind.
        self.assertEqual(self.u4.depth, 1)
        self.assertEqual(self.u4.parent_kind, COMPANY)
        section = add(SECTION, "بخش مستقل", self.u4)
        self.assertEqual(section.depth, 2)
        self.assert_tree_consistent()

    def test_every_kind_and_parent_kind_pair_follows_the_table(self):
        parents = {COMPANY: self.root, DOMAIN: self.d1, UNIT: self.u1, SECTION: self.s1}
        for kind in (DOMAIN, UNIT, SECTION):
            for parent_kind, parent in parents.items():
                with self.subTest(kind=kind, parent=parent_kind):
                    if parent_kind in ALLOWED_PARENT_KINDS[kind]:
                        node = add(kind, f"{kind}-{parent_kind}", parent)
                        self.assertEqual(node.parent_id, parent.pk)
                    else:
                        with self.assertRaises(ValidationError) as caught:
                            add(kind, f"{kind}-{parent_kind}", parent)
                        self.assertIn("parent", caught.exception.detail)
        self.assert_tree_consistent()

    def test_a_second_company_root_cannot_be_made_through_create_node(self):
        with self.assertRaises(ValueError):
            tree.create_node(kind=COMPANY, name="شرکت دوم", parent=self.root)

    def test_a_second_root_is_refused_by_the_database(self):
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            tree.create_root(name="شرکت دوم")
        self.assertIn("uniq_company_root_node", str(caught.exception))

    def test_names_are_stored_normalised_with_zwnj_kept(self):
        node = add(UNIT, "  واحد   اجرايي  می\u200cشود ", self.d2)
        self.assertEqual(node.name, "واحد اجرایی می\u200cشود")  # Arabic yeh unified, spaces collapsed, ZWNJ kept

    def test_a_blank_name_is_refused(self):
        with self.assertRaises(ValidationError):
            add(UNIT, "   ", self.d2)

    def test_siblings_may_not_share_a_name_even_across_letterforms_and_digits(self):
        add(UNIT, "واحد ۱", self.d2)
        for clash in ("واحد 1", "واحد ۱", "  واحد  ۱  "):
            with self.subTest(clash=clash), self.assertRaises(ConflictError) as caught:
                add(UNIT, clash, self.d2)
            self.assertEqual(caught.exception.payload["code"], "duplicate_name")
        add(UNIT, "واحد ي", self.d2)
        with self.assertRaises(ConflictError):
            add(UNIT, "واحد ی", self.d2)  # Arabic yeh vs Persian yeh

    def test_the_duplicate_answer_names_the_node_it_collided_with(self):
        with self.assertRaises(ConflictError) as caught:
            add(UNIT, "واحد فروش", self.d1)
        self.assertEqual(caught.exception.payload["existing_id"], self.u1.pk)

    def test_different_parents_may_each_own_the_same_name(self):
        self.assertEqual(self.u1.name, self.u3.name)

    def test_nothing_can_be_created_under_an_archived_node(self):
        tree.archive_node(self.u2)
        with self.assertRaises(ConflictError) as caught:
            add(SECTION, "بخش تازه", self.u2)
        self.assertEqual(caught.exception.payload["code"], "parent_archived")


class DatabaseConstraintTests(SampleTree, TestCase):
    """The rules the schema keeps for itself, tried by writing rows *around* tree.py."""

    def setUp(self):
        self.build()

    def insert(self, **fields):
        defaults = dict(name="x", name_key="x", path="p", depth=1, kind=UNIT, parent=self.root, parent_kind=COMPANY)
        with transaction.atomic():
            return OrgNode.objects.create(**{**defaults, **fields})

    def test_the_parent_kind_table_is_enforced_for_every_pair(self):
        for kind in (DOMAIN, UNIT, SECTION):
            for parent_kind in (COMPANY, DOMAIN, UNIT, SECTION, ""):
                with self.subTest(kind=kind, parent_kind=parent_kind):
                    fields = dict(kind=kind, parent_kind=parent_kind, name_key=f"{kind}{parent_kind}")
                    if parent_kind in ALLOWED_PARENT_KINDS[kind]:
                        self.insert(**fields)
                    else:
                        with self.assertRaises(IntegrityError) as caught:
                            self.insert(**fields)
                        self.assertIn("org_node_parent_kind_allowed", str(caught.exception))

    def test_a_non_company_node_must_have_a_parent(self):
        with self.assertRaises(IntegrityError) as caught:
            self.insert(kind=DOMAIN, parent=None, parent_kind=COMPANY, name_key="orphan")
        self.assertIn("org_node_root_iff_company", str(caught.exception))

    def test_the_company_node_must_not_have_a_parent(self):
        with self.assertRaises(IntegrityError) as caught:
            self.insert(kind=COMPANY, parent=self.root, parent_kind="", name_key="second")
        self.assertIn("org_node_root_iff_company", str(caught.exception))

    def test_sibling_names_are_unique_on_the_key(self):
        with self.assertRaises(IntegrityError) as caught:
            self.insert(name_key=self.u1.name_key, parent=self.d1, parent_kind=DOMAIN)
        self.assertIn("uniq_org_node_name_per_parent", str(caught.exception))
        self.insert(name_key=self.u2.name_key, parent=self.d2, parent_kind=DOMAIN)  # D2 has no «واحد مالی»: fine

    def test_the_company_row_is_a_singleton(self):
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            Company.objects.create(pk=2, root=self.u4)
        self.assertIn("company_is_singleton", str(caught.exception))

    def test_the_foreign_key_protects_a_node_that_has_children(self):
        with self.assertRaises(ProtectedError):
            self.d1.delete()


class RenameTests(SampleTree, TestCase):
    def setUp(self):
        self.build()

    def test_rename_updates_the_name_and_the_key(self):
        node = tree.rename_node(self.u2, "واحد بازرگانی")
        node.refresh_from_db()
        self.assertEqual((node.name, node.name_key), ("واحد بازرگانی", "واحد بازرگانی"))

    def test_rename_to_a_siblings_name_conflicts(self):
        with self.assertRaises(ConflictError) as caught:
            tree.rename_node(self.u2, "واحد فروش")
        self.assertEqual(caught.exception.payload["code"], "duplicate_name")

    def test_a_node_may_be_renamed_to_a_respelling_of_its_own_name(self):
        node = tree.rename_node(self.u2, "واحد   مالی ")  # same key: it does not clash with itself
        self.assertEqual(node.name, "واحد مالی")

    def test_the_company_can_be_renamed(self):
        self.assertEqual(tree.rename_node(self.root, "نام تازه").name, "نام تازه")


class MoveTests(SampleTree, TestCase):
    def setUp(self):
        self.build()

    def test_moving_a_unit_moves_its_sections_and_shifts_their_depth(self):
        section = add(SECTION, "بخش مالی", self.u2)
        tree.move_node(self.u2, self.d2)  # D1 -> D2 keeps depth
        section.refresh_from_db()
        self.assertTrue(section.path.startswith(self.d2.path + f"{self.u2.pk:010d}/"))
        self.assertEqual(section.depth, 3)

        node = tree.move_node(self.u2, self.root)  # a واحد straight under the company: one level up
        section.refresh_from_db()
        self.assertEqual((node.depth, section.depth), (1, 2))
        self.assertEqual(node.parent_kind, COMPANY)
        self.assertEqual(section.parent_kind, UNIT)  # the section's own parent did not change
        self.assert_tree_consistent()

    def test_a_unit_under_the_company_can_move_into_a_domain_and_deepen(self):
        section = add(SECTION, "بخش مستقل", self.u4)
        tree.move_node(self.u4, self.d2)
        section.refresh_from_db()
        self.assertEqual(section.depth, 3)
        self.assert_tree_consistent()

    def test_moving_leaves_the_rest_of_the_tree_alone(self):
        section = add(SECTION, "بخش مالی", self.u2)
        moved = [self.u2.pk, section.pk]
        before = {n.pk: (n.path, n.depth) for n in OrgNode.objects.exclude(pk__in=moved)}
        tree.move_node(self.u2, self.d2)
        after = {n.pk: (n.path, n.depth) for n in OrgNode.objects.exclude(pk__in=moved)}
        self.assertEqual(before, after)

    def test_a_node_cannot_move_under_itself_or_its_descendants(self):
        cases = [(self.u1, self.u1), (self.d1, self.u1), (self.d1, self.s1), (self.u1, self.s1)]
        for node, target in cases:
            with self.subTest(node=node.name, target=target.name), self.assertRaises(ConflictError) as caught:
                tree.move_node(node, target)
            self.assertEqual(caught.exception.payload["code"], "cycle")
        self.assert_tree_consistent()

    def test_the_kind_table_applies_to_moves(self):
        with self.assertRaises(ValidationError):
            tree.move_node(self.s1, self.d1)  # a بخش needs a واحد
        with self.assertRaises(ValidationError):
            tree.move_node(self.u2, self.s1)

    def test_moving_to_the_current_parent_changes_nothing(self):
        self.assertEqual(tree.move_node(self.u2, self.d1).path, self.u2.path)

    def test_the_root_cannot_move(self):
        with self.assertRaises(ConflictError) as caught:
            tree.move_node(self.root, self.d1)
        self.assertEqual(caught.exception.payload["code"], "root_immutable")

    def test_a_move_into_a_parent_holding_the_same_name_conflicts(self):
        with self.assertRaises(ConflictError) as caught:
            tree.move_node(self.u3, self.d1)  # D1 already has a «واحد فروش»
        self.assertEqual(caught.exception.payload["code"], "duplicate_name")
        self.assert_tree_consistent()

    def test_nothing_can_move_into_an_archived_node(self):
        tree.archive_node(self.u2)
        with self.assertRaises(ConflictError) as caught:
            tree.move_node(self.s1, self.u2)
        self.assertEqual(caught.exception.payload["code"], "parent_archived")

    def test_a_failed_move_rolls_the_rename_back(self):
        with self.assertRaises(ValidationError):
            tree.update_node(self.s1, name="نام دیگر", parent=self.d1)
        self.s1.refresh_from_db()
        self.assertEqual(self.s1.name, "بخش یک")


class ArchiveAndDeleteTests(SampleTree, TestCase):
    def setUp(self):
        self.build()

    def test_a_node_with_active_children_cannot_be_archived(self):
        with self.assertRaises(ConflictError) as caught:
            tree.archive_node(self.u1)
        self.assertEqual(caught.exception.payload["code"], "has_active_children")
        self.assertEqual(caught.exception.payload["active_children"], 1)

    def test_archiving_bottom_up_works_and_is_idempotent(self):
        tree.archive_node(self.s1)
        tree.archive_node(self.u1)
        self.u1.refresh_from_db()
        self.assertFalse(self.u1.is_active)
        self.assertFalse(tree.archive_node(self.u1).is_active)

    def test_the_company_cannot_be_archived_or_deleted(self):
        for operation in (tree.archive_node, tree.delete_node):
            with self.subTest(operation=operation.__name__), self.assertRaises(ConflictError) as caught:
                operation(self.root)
            self.assertEqual(caught.exception.payload["code"], "root_immutable")

    def test_unarchiving_needs_an_active_parent(self):
        tree.archive_node(self.s1)
        tree.archive_node(self.u1)
        with self.assertRaises(ConflictError) as caught:
            tree.unarchive_node(self.s1)
        self.assertEqual(caught.exception.payload["code"], "parent_archived")
        tree.unarchive_node(self.u1)
        self.assertTrue(tree.unarchive_node(self.s1).is_active)

    def test_an_empty_node_is_deleted(self):
        tree.delete_node(self.u4)
        self.assertFalse(OrgNode.objects.filter(pk=self.u4.pk).exists())

    def test_a_node_with_children_is_not_deleted_and_the_answer_counts_them(self):
        with self.assertRaises(ConflictError) as caught:
            tree.delete_node(self.d1)
        self.assertEqual(caught.exception.payload["code"], "node_not_empty")
        self.assertEqual(caught.exception.payload["children"], 2)
        self.assertTrue(OrgNode.objects.filter(pk=self.d1.pk).exists())

    def test_archived_children_still_block_deletion(self):
        tree.archive_node(self.s1)
        with self.assertRaises(ConflictError):
            tree.delete_node(self.u1)


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class ApiTestCase(SampleTree, TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)
        self.ceo = make_user("9100000001", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
        self.guild = make_user("9100000002", AccessRoll.GUILD, AccessLevel.LEVEL_3)

    def as_(self, user):
        self.client.force_authenticate(user)
        return self.client


class TreeEndpointTests(ApiTestCase):
    def test_it_needs_a_login(self):
        self.assertEqual(self.client.get(reverse("org-tree")).status_code, 401)

    def test_before_setup_the_tree_is_empty(self):
        response = self.as_(self.guild).get(reverse("org-tree"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"truncated": False, "nodes": []})

    def test_any_signed_in_user_gets_the_whole_tree_in_depth_first_order_in_one_query(self):
        self.build()
        self.as_(self.guild)
        with self.assertNumQueries(1):
            response = self.client.get(reverse("org-tree"))
        names = [node["name"] for node in response.data["nodes"]]
        self.assertEqual(
            names,
            ["شرکت نمونه", "حوزه یک", "واحد فروش", "بخش یک", "واحد مالی", "حوزه دو", "واحد فروش", "واحد مستقل"],
        )
        self.assertEqual([n["depth"] for n in response.data["nodes"]], [0, 1, 2, 3, 2, 1, 2, 1])
        self.assertFalse(response.data["truncated"])

    def test_a_node_exposes_only_what_the_chart_needs(self):
        self.build()
        node = self.as_(self.guild).get(reverse("org-tree")).data["nodes"][1]
        self.assertEqual(
            set(node), {"id", "parent", "kind", "kind_label", "name", "depth", "is_active"}
        )
        self.assertEqual(node["kind_label"], "حوزه")

    @override_settings(ORG_TREE_MAX_NODES=4)
    def test_an_oversized_tree_returns_two_levels_and_says_so(self):
        self.build()
        response = self.as_(self.guild).get(reverse("org-tree"))
        self.assertTrue(response.data["truncated"])
        self.assertEqual({n["depth"] for n in response.data["nodes"]}, {0, 1})
        self.assertEqual(len(response.data["nodes"]), 4)  # company, D1, D2, U4

    @override_settings(ORG_TREE_MAX_NODES=8)
    def test_a_tree_exactly_at_the_cap_is_not_truncated(self):
        self.build()
        response = self.as_(self.guild).get(reverse("org-tree"))
        self.assertFalse(response.data["truncated"])
        self.assertEqual(len(response.data["nodes"]), 8)

    def test_parent_returns_one_nodes_direct_children(self):
        self.build()
        self.as_(self.guild)
        response = self.client.get(reverse("org-tree"), {"parent": self.d1.pk})
        self.assertEqual([n["name"] for n in response.data["nodes"]], ["واحد فروش", "واحد مالی"])
        self.assertEqual(self.client.get(reverse("org-tree"), {"parent": "abc"}).status_code, 400)
        self.assertEqual(self.client.get(reverse("org-tree"), {"parent": 999999999}).status_code, 404)


class NodePermissionTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.build()

    def test_the_matrix_follows_manage_organization_for_every_roll_and_level(self):
        combos = [(roll, level) for roll in AccessRoll.values for level in AccessLevel.values]
        for number, (roll, level) in enumerate(combos):
            user = make_user(f"93{number:08d}", roll, level)
            allowed = user.has_capability(Capability.MANAGE_ORGANIZATION)
            self.as_(user)
            with self.subTest(roll=roll, level=level):
                self.assertEqual(self.client.get(reverse("org-node-list")).status_code, 200)
                created = self.client.post(
                    reverse("org-node-list"),
                    {"kind": SECTION, "name": f"بخش {roll}{level}", "parent": self.u2.pk},
                    format="json",
                )
                self.assertEqual(created.status_code, 201 if allowed else 403, created.data)

    def test_only_employers_hold_manage_organization(self):
        holders = {
            (roll, level)
            for roll in AccessRoll.values
            for level in AccessLevel.values
            if User(access_roll=roll, access_level=level).has_capability(Capability.MANAGE_ORGANIZATION)
        }
        self.assertEqual(holders, {(AccessRoll.EMPLOYER, level) for level in AccessLevel.values})

    def test_a_guild_user_cannot_rename_move_archive_or_delete(self):
        self.as_(self.guild)
        url = reverse("org-node-detail", args=[self.u4.pk])
        self.assertEqual(self.client.patch(url, {"name": "هک"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.assertEqual(self.client.post(reverse("org-node-archive", args=[self.u4.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("org-node-unarchive", args=[self.u4.pk])).status_code, 403)
        self.u4.refresh_from_db()
        self.assertEqual(self.u4.name, "واحد مستقل")

    def test_anonymous_gets_401(self):
        self.assertEqual(self.client.get(reverse("org-node-list")).status_code, 401)
        self.assertEqual(self.client.post(reverse("org-node-list"), {}, format="json").status_code, 401)


class NodeCrudTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.build()
        self.as_(self.ceo)

    def test_create_returns_the_node(self):
        response = self.client.post(
            reverse("org-node-list"), {"kind": SECTION, "name": "بخش دو", "parent": self.u1.pk}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["depth"], 3)
        self.assertEqual(response.data["parent"], self.u1.pk)
        self.assertEqual(OrgNode.objects.get(pk=response.data["id"]).created_by, self.ceo)
        self.assert_tree_consistent()

    def test_a_company_node_cannot_be_created_here(self):
        response = self.client.post(
            reverse("org-node-list"), {"kind": COMPANY, "name": "شرکت", "parent": self.root.pk}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("kind", response.data)

    def test_a_wrong_parent_kind_is_a_400_with_a_persian_reason(self):
        response = self.client.post(
            reverse("org-node-list"), {"kind": SECTION, "name": "بخش", "parent": self.d1.pk}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["parent"], ["بخش فقط زیر یک واحد ساخته می‌شود."])

    def test_missing_fields_and_unknown_parents_are_400(self):
        for body in ({}, {"kind": UNIT, "name": "الف"}, {"kind": UNIT, "name": "الف", "parent": 999999999}):
            with self.subTest(body=body):
                self.assertEqual(self.client.post(reverse("org-node-list"), body, format="json").status_code, 400)

    def test_a_duplicate_name_is_a_typed_409(self):
        response = self.client.post(
            reverse("org-node-list"), {"kind": UNIT, "name": "واحد فروش", "parent": self.d1.pk}, format="json"
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "duplicate_name")
        self.assertEqual(response.data["existing_id"], self.u1.pk)  # an int, not "…"

    def test_patch_renames(self):
        response = self.client.patch(
            reverse("org-node-detail", args=[self.u2.pk]), {"name": "واحد مالی و اداری"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["name"], "واحد مالی و اداری")

    def test_patch_moves_with_the_subtree(self):
        response = self.client.patch(
            reverse("org-node-detail", args=[self.u1.pk]), {"parent": self.d2.pk}, format="json"
        )
        self.assertEqual(response.status_code, 409)  # D2 already has a «واحد فروش»
        self.assertEqual(response.data["code"], "duplicate_name")
        response = self.client.patch(
            reverse("org-node-detail", args=[self.u1.pk]),
            {"name": "واحد بازاریابی", "parent": self.d2.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data["parent"], response.data["depth"]), (self.d2.pk, 2))
        self.assert_tree_consistent()

    def test_a_cycle_is_a_409(self):
        response = self.client.patch(
            reverse("org-node-detail", args=[self.d1.pk]), {"parent": self.u1.pk}, format="json"
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "cycle")

    def test_the_kind_cannot_be_changed(self):
        url = reverse("org-node-detail", args=[self.u2.pk])
        response = self.client.patch(url, {"kind": SECTION}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["kind"], ["نوع گره پس از ساخت قابل تغییر نیست."])
        self.assertEqual(self.client.patch(url, {"kind": UNIT, "name": "واحد مالی ۲"}, format="json").status_code, 200)

    def test_put_is_not_offered(self):
        url = reverse("org-node-detail", args=[self.u2.pk])
        self.assertEqual(self.client.put(url, {"name": "x"}, format="json").status_code, 405)

    def test_is_active_is_not_writable_through_patch(self):
        self.client.patch(reverse("org-node-detail", args=[self.u4.pk]), {"is_active": False}, format="json")
        self.u4.refresh_from_db()
        self.assertTrue(self.u4.is_active)

    def test_archive_and_unarchive(self):
        url = reverse("org-node-archive", args=[self.u4.pk])
        self.assertFalse(self.client.post(url).data["is_active"])
        self.assertTrue(self.client.post(reverse("org-node-unarchive", args=[self.u4.pk])).data["is_active"])
        self.assertEqual(self.client.post(reverse("org-node-archive", args=[self.d1.pk])).status_code, 409)

    def test_delete_an_empty_node(self):
        self.assertEqual(self.client.delete(reverse("org-node-detail", args=[self.u4.pk])).status_code, 204)

    def test_delete_a_node_with_children_is_a_409_that_counts_them(self):
        response = self.client.delete(reverse("org-node-detail", args=[self.d1.pk]))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "node_not_empty")
        self.assertEqual(response.data["children"], 2)

    def test_an_unknown_node_is_a_404(self):
        self.assertEqual(self.client.get(reverse("org-node-detail", args=[999999999])).status_code, 404)

    def test_the_list_is_paginated_in_tree_order_and_filterable(self):
        response = self.client.get(reverse("org-node-list"))
        self.assertEqual(response.data["count"], 8)
        self.assertEqual(response.data["results"][0]["name"], "شرکت نمونه")
        units = self.client.get(reverse("org-node-list"), {"kind": UNIT}).data["results"]
        self.assertEqual(len(units), 4)
        children = self.client.get(reverse("org-node-list"), {"parent": self.d1.pk}).data["results"]
        self.assertEqual([n["name"] for n in children], ["واحد فروش", "واحد مالی"])
        self.assertEqual(self.client.get(reverse("org-node-list"), {"parent": "x"}).data["count"], 0)
        tree.archive_node(self.u4)
        inactive = self.client.get(reverse("org-node-list"), {"is_active": "false"}).data["results"]
        self.assertEqual([n["id"] for n in inactive], [self.u4.pk])


class CompanyEndpointTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self._media = tempfile.mkdtemp(prefix="veye-org-media-")
        self._override = override_settings(MEDIA_ROOT=self._media)
        self._override.enable()
        self.addCleanup(self._override.disable)
        self.addCleanup(shutil.rmtree, self._media, ignore_errors=True)

    def png(self, size=(40, 30), fmt="PNG"):
        buffer = io.BytesIO()
        Image.new("RGB", size, (200, 30, 30)).save(buffer, fmt)
        buffer.seek(0)
        buffer.name = "logo." + fmt.lower()
        return buffer

    def test_before_setup_there_is_no_company(self):
        response = self.as_(self.guild).get(reverse("org-company"))
        self.assertEqual(response.status_code, 404)

    def test_anyone_signed_in_reads_the_profile_and_the_name_is_the_roots(self):
        self.build()
        response = self.as_(self.guild).get(reverse("org-company"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "شرکت نمونه")
        self.assertEqual(response.data["root"], self.root.pk)
        self.assertEqual(response.data["setup_step"], SetupStep.DOMAINS)
        self.assertIsNone(response.data["logo_url"])
        self.assertEqual(set(response.data), {
            "id", "root", "name", "legal_name", "national_id", "logo_url",
            "setup_step", "setup_step_label", "setup_completed_at",
        })

    def test_a_manager_edits_the_profile(self):
        self.build()
        response = self.as_(self.ceo).patch(
            reverse("org-company"),
            {"name": "وپورویر", "legal_name": "  شرکت   ايران ", "national_id": "۱۴ ۰۰ ۱۲۳۴۵۶۷"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["name"], "وپورویر")
        self.assertEqual(response.data["legal_name"], "شرکت ایران")
        self.assertEqual(response.data["national_id"], "14001234567")
        self.root.refresh_from_db()
        self.assertEqual(self.root.name, "وپورویر")  # the chart and the header cannot disagree

    def test_a_partial_patch_leaves_the_rest_alone(self):
        self.build()
        self.as_(self.ceo).patch(reverse("org-company"), {"legal_name": "الف"}, format="json")
        response = self.client.patch(reverse("org-company"), {"national_id": "123"}, format="json")
        self.assertEqual((response.data["legal_name"], response.data["national_id"]), ("الف", "123"))
        self.assertEqual(response.data["name"], "شرکت نمونه")

    def test_a_guild_user_cannot_edit_the_profile(self):
        self.build()
        response = self.as_(self.guild).patch(reverse("org-company"), {"name": "هک"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.root.refresh_from_db()
        self.assertEqual(self.root.name, "شرکت نمونه")

    def test_the_company_cannot_be_deleted_through_the_api(self):
        self.build()
        self.assertEqual(self.as_(self.ceo).delete(reverse("org-company")).status_code, 405)
        response = self.client.delete(reverse("org-node-detail", args=[self.root.pk]))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "root_immutable")

    def test_logo_upload_is_normalised_to_png_and_served(self):
        self.build()
        self.as_(self.ceo)
        response = self.client.post(
            reverse("org-company-logo"), {"logo": self.png(fmt="JPEG")}, format="multipart"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("/api/v1/org/company/logo/?v=", response.data["logo_url"])
        company = Company.objects.get()
        self.assertTrue(company.logo.name.endswith(".png"))
        served = self.as_(self.guild).get(reverse("org-company-logo"))
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served["Content-Type"], "image/png")
        self.assertEqual(Image.open(io.BytesIO(b"".join(served.streaming_content))).format, "PNG")

    def test_a_file_that_is_not_an_image_is_refused(self):
        self.build()
        fake = io.BytesIO(b"this is not an image")
        fake.name = "logo.png"
        response = self.as_(self.ceo).post(reverse("org-company-logo"), {"logo": fake}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("logo", response.data)

    def test_a_guild_user_cannot_upload_or_remove_the_logo(self):
        self.build()
        self.as_(self.guild)
        self.assertEqual(self.client.post(reverse("org-company-logo"), {"logo": self.png()}, format="multipart").status_code, 403)
        self.assertEqual(self.client.delete(reverse("org-company-logo")).status_code, 403)

    def test_removing_the_logo_deletes_the_file_once_committed(self):
        self.build()
        self.as_(self.ceo)
        self.client.post(reverse("org-company-logo"), {"logo": self.png()}, format="multipart")
        company = Company.objects.get()
        path = company.logo.path
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(reverse("org-company-logo"))
        self.assertIsNone(response.data["logo_url"])
        self.assertFalse(os.path.exists(path))
        self.assertEqual(self.as_(self.guild).get(reverse("org-company-logo")).status_code, 404)

    def test_uploading_without_a_file_is_a_400(self):
        self.build()
        response = self.as_(self.ceo).post(reverse("org-company-logo"), {}, format="multipart")
        self.assertEqual(response.status_code, 400)


class Threaded:
    """Run a worker in N real threads, released together, each on its own connection."""

    def run_concurrently(self, worker, n):
        results, barrier = [], threading.Barrier(n)

        def target(i):
            try:
                barrier.wait()
                results.append(("ok", worker(i)))
            except Exception as exc:  # noqa: BLE001 - we assert on the type below
                results.append(("err", exc))
            finally:
                connection.close()

        threads = [threading.Thread(target=target, args=(i,)) for i in range(n)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        return results


@skipUnlessDBFeature("has_select_for_update")
class ConcurrencyTests(Threaded, TreeAssertions, TransactionTestCase):
    """Real threads against a real database. Skipped on SQLite, which has no row locks; run
    in the compose backend container (Postgres)."""

    def setUp(self):
        self.root = make_company()
        self.d1 = add(DOMAIN, "حوزه یک", self.root)
        self.d2 = add(DOMAIN, "حوزه دو", self.root)

    def assert_exactly_one_winner(self, results, losers):
        self.assertEqual(len([r for r in results if r[0] == "ok"]), 1, results)
        errors = [r[1] for r in results if r[0] == "err"]
        self.assertEqual(len(errors), losers, results)
        self.assertTrue(all(isinstance(e, ConflictError) for e in errors), errors)
        self.assertTrue(all(e.payload["code"] == "duplicate_name" for e in errors), errors)

    def test_concurrent_creators_of_one_name_under_one_parent_yield_exactly_one_node(self):
        results = self.run_concurrently(lambda i: add(UNIT, "همنام", self.d1), 6)
        self.assert_exactly_one_winner(results, losers=5)
        self.assertEqual(OrgNode.objects.filter(parent=self.d1, name="همنام").count(), 1)

    def test_concurrent_renames_to_one_name_yield_exactly_one_winner(self):
        # Renames do not lock the parent, so the loser may reach the unique index: the
        # constraint must still come back as the same 409, not a 500.
        units = [add(UNIT, f"واحد {i}", self.d1) for i in range(4)]
        results = self.run_concurrently(lambda i: tree.rename_node(units[i], "نام مشترک"), 4)
        self.assert_exactly_one_winner(results, losers=3)
        self.assertEqual(OrgNode.objects.filter(parent=self.d1, name="نام مشترک").count(), 1)

    def test_a_create_racing_the_move_of_its_parent_never_leaves_a_stale_path(self):
        for round_ in range(15):
            unit = add(UNIT, f"واحد {round_}", self.d1)
            add(SECTION, "بخش اول", unit)

            def worker(i, unit=unit):
                if i == 0:
                    return tree.move_node(unit, self.root)  # up to the company: depth shifts by one
                return add(SECTION, "بخش دوم", unit)

            results = self.run_concurrently(worker, 2)
            self.assertEqual([r for r in results if r[0] == "err"], [], round_)
            self.assert_tree_consistent()


# ---------------------------------------------------------------------------
# Memberships (slice 7.2)
# ---------------------------------------------------------------------------


def person(code, name=None, roll=AccessRoll.GUILD, level=AccessLevel.LEVEL_3, **extra):
    return make_user(code, roll, level, full_name=name or f"شخص {code}", **extra)


def join(user, node, **kwargs):
    return memberships.add_membership(user=user, node=node, **kwargs)


class MembershipAssertions:
    def assert_one_primary(self, user):
        rows = list(Membership.objects.filter(user=user))
        primaries = [m for m in rows if m.is_primary]
        self.assertEqual(len(primaries), 1 if rows else 0, [(m.node.name, m.is_primary) for m in rows])


class MembershipServiceTests(MembershipAssertions, SampleTree, TestCase):
    def setUp(self):
        self.build()
        self.ali = person("9200000001", "علی رضايي")

    def test_the_first_membership_is_primary_whatever_is_asked(self):
        for number, asked in enumerate((None, False, True)):
            user = person(f"921{number:07d}")
            self.assertTrue(join(user, self.s1, is_primary=asked).is_primary, asked)

    def test_later_memberships_are_not_primary_unless_asked(self):
        first = join(self.ali, self.s1)
        second = join(self.ali, self.u2)
        self.assertEqual((first.is_primary, second.is_primary), (True, False))
        self.assert_one_primary(self.ali)

    def test_asking_for_primary_demotes_the_old_one(self):
        first = join(self.ali, self.s1)
        second = join(self.ali, self.u2, is_primary=True)
        first.refresh_from_db()
        self.assertEqual((first.is_primary, second.is_primary), (False, True))
        self.assert_one_primary(self.ali)

    def test_the_same_person_cannot_join_a_node_twice(self):
        first = join(self.ali, self.s1)
        with self.assertRaises(ConflictError) as caught:
            join(self.ali, self.s1, is_lead=True)
        self.assertEqual(caught.exception.payload["code"], "already_member")
        self.assertEqual(caught.exception.payload["existing_id"], first.pk)

    def test_an_inactive_person_cannot_be_added(self):
        self.ali.is_active = False
        self.ali.save()
        with self.assertRaises(ConflictError) as caught:
            join(self.ali, self.s1)
        self.assertEqual(caught.exception.payload["code"], "user_inactive")

    def test_nobody_can_be_added_to_an_archived_node(self):
        tree.archive_node(self.u2)
        with self.assertRaises(ConflictError) as caught:
            join(self.ali, self.u2)
        self.assertEqual(caught.exception.payload["code"], "node_archived")

    def test_any_kind_of_node_takes_members_including_the_company(self):
        for node in (self.root, self.d1, self.u1, self.s1):
            self.assertEqual(join(person(f"93{node.pk:08d}"), node).node_id, node.pk)

    def test_a_node_may_have_several_leads_and_the_label_is_normalised(self):
        head = join(person("9200000010"), self.u1, is_lead=True, position_label="  رئيس   واحد ")
        deputy = join(person("9200000011"), self.u1, is_lead=True, position_label="معاون")
        self.assertEqual(head.position_label, "رئیس واحد")
        self.assertEqual(Membership.objects.filter(node=self.u1, is_lead=True).count(), 2)
        self.assertTrue(deputy.is_lead)

    def test_added_by_is_recorded(self):
        ceo = person("9200000012")
        self.assertEqual(join(self.ali, self.s1, added_by=ceo).added_by, ceo)

    def test_update_changes_lead_and_label(self):
        m = join(self.ali, self.s1)
        m = memberships.update_membership(m, is_lead=True, position_label="سرپرست بخش")
        m.refresh_from_db()
        self.assertEqual((m.is_lead, m.position_label), (True, "سرپرست بخش"))
        self.assertTrue(m.is_primary)  # untouched

    def test_making_another_membership_primary_moves_the_flag(self):
        first, second = join(self.ali, self.s1), join(self.ali, self.u2)
        memberships.update_membership(second, is_primary=True)
        first.refresh_from_db(); second.refresh_from_db()
        self.assertEqual((first.is_primary, second.is_primary), (False, True))
        self.assert_one_primary(self.ali)

    def test_the_primary_cannot_simply_be_unset(self):
        m = join(self.ali, self.s1)
        with self.assertRaises(ConflictError) as caught:
            memberships.update_membership(m, is_primary=False)
        self.assertEqual(caught.exception.payload["code"], "primary_required")
        m.refresh_from_db()
        self.assertTrue(m.is_primary)

    def test_unsetting_a_membership_that_is_not_primary_is_a_no_op(self):
        join(self.ali, self.s1)
        other = join(self.ali, self.u2)
        memberships.update_membership(other, is_primary=False)
        self.assert_one_primary(self.ali)

    def test_removing_a_non_primary_membership_leaves_the_primary_alone(self):
        first, second = join(self.ali, self.s1), join(self.ali, self.u2)
        memberships.remove_membership(second)
        first.refresh_from_db()
        self.assertTrue(first.is_primary)

    def test_removing_the_primary_promotes_the_earliest_remaining(self):
        first = join(self.ali, self.s1)
        second, third = join(self.ali, self.u2), join(self.ali, self.u4)
        memberships.remove_membership(first)
        second.refresh_from_db(); third.refresh_from_db()
        self.assertEqual((second.is_primary, third.is_primary), (True, False))
        memberships.remove_membership(second)
        third.refresh_from_db()
        self.assertTrue(third.is_primary)
        memberships.remove_membership(third)
        self.assertFalse(Membership.objects.filter(user=self.ali).exists())

    def test_a_node_with_members_cannot_be_deleted_and_the_answer_counts_them(self):
        m = join(self.ali, self.u4)
        with self.assertRaises(ConflictError) as caught:
            tree.delete_node(self.u4)
        self.assertEqual(caught.exception.payload["code"], "node_not_empty")
        self.assertEqual(caught.exception.payload["members"], 1)
        memberships.remove_membership(m)
        tree.delete_node(self.u4)
        self.assertFalse(OrgNode.objects.filter(pk=self.u4.pk).exists())

    def test_archiving_a_node_keeps_its_members(self):
        join(self.ali, self.u2)
        tree.archive_node(self.u2)
        self.assertEqual(Membership.objects.filter(node=self.u2).count(), 1)


class MembershipConstraintTests(SampleTree, TestCase):
    def setUp(self):
        self.build()
        self.ali = person("9200000020")

    def test_two_primaries_for_one_person_are_refused_by_the_database(self):
        Membership.objects.create(user=self.ali, node=self.u1, is_primary=True)
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            Membership.objects.create(user=self.ali, node=self.u2, is_primary=True)
        self.assertIn("uniq_primary_membership_per_user", str(caught.exception))
        Membership.objects.create(user=person("9200000021"), node=self.u2, is_primary=True)  # another person: fine

    def test_a_person_may_have_any_number_of_non_primary_memberships(self):
        for node in (self.u1, self.u2, self.u3, self.u4):
            Membership.objects.create(user=self.ali, node=node, is_primary=False)

    def test_one_membership_per_person_and_node(self):
        Membership.objects.create(user=self.ali, node=self.u1)
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            Membership.objects.create(user=self.ali, node=self.u1)
        self.assertIn("uniq_membership_user_node", str(caught.exception))

    def test_the_foreign_keys_protect_people_and_nodes(self):
        Membership.objects.create(user=self.ali, node=self.u4)
        with self.assertRaises(ProtectedError):
            self.ali.delete()
        with self.assertRaises(ProtectedError):
            self.u4.delete()


class SearchExpressionTests(TestCase):
    NAMES = [
        "علی رضايي",  # Arabic yeh, as the importer keeps it
        "  كاربر   ۱۲٣  ",  # Arabic kaf, Persian + Arabic-Indic digits, stray spaces
        "Sam   LEE",
        "می\u200cشود",  # ZWNJ must survive
        "ئ ي ى ك",
        "\tتب\u00a0ت ",  # tab and no-break space
    ]

    def test_the_sql_normalisation_agrees_with_the_python_one(self):
        """The SQL expression is a second implementation of normalize_search_term; this is what
        stops the two drifting apart."""
        users = [person(f"94{i:08d}", name) for i, name in enumerate(self.NAMES)]
        rows = {
            u.pk: u.name_key
            for u in User.objects.filter(pk__in=[u.pk for u in users]).annotate(
                name_key=queries.normalized_name_expression()
            )
        }
        for user, name in zip(users, self.NAMES):
            with self.subTest(name=name):
                self.assertEqual(rows[user.pk], normalize_search_term(name))

    def test_search_finds_people_however_the_letters_were_typed(self):
        ali = person("9500000001", "علی رضايي")
        person("9500000002", "کاربر ۱۲")
        person("9500000003", "Sam Lee")
        for term, expected in (
            ("رضایی", "علی رضايي"),
            ("رضايي", "علی رضايي"),
            ("  علی   رضایی ", "علی رضايي"),
            ("12", "کاربر ۱۲"),
            ("۱۲", "کاربر ۱۲"),
            ("SAM", "Sam Lee"),
        ):
            with self.subTest(term=term):
                found = queries.search_people(User.objects.all(), term)
                self.assertEqual([u.full_name for u in found], [expected])
        self.assertEqual(queries.search_people(User.objects.all(), "   ").count(), User.objects.count())
        self.assertTrue(User.objects.filter(pk=ali.pk).exists())


class MembershipApiTests(MembershipAssertions, ApiTestCase):
    def setUp(self):
        super().setUp()
        self.build()
        self.ali = person("9600000001", "علی رضايي")
        self.as_(self.ceo)

    def post(self, **body):
        return self.client.post(reverse("org-membership-list"), body, format="json")

    def test_only_employers_hold_manage_membership(self):
        holders = {
            (roll, level)
            for roll in AccessRoll.values
            for level in AccessLevel.values
            if User(access_roll=roll, access_level=level).has_capability(Capability.MANAGE_MEMBERSHIP)
        }
        self.assertEqual(holders, {(AccessRoll.EMPLOYER, level) for level in AccessLevel.values})

    def test_the_matrix_follows_manage_membership_for_every_roll_and_level(self):
        combos = [(roll, level) for roll in AccessRoll.values for level in AccessLevel.values]
        for number, (roll, level) in enumerate(combos):
            actor = make_user(f"9601{number:06d}", roll, level)
            target = person(f"9602{number:06d}")
            allowed = actor.has_capability(Capability.MANAGE_MEMBERSHIP)
            self.as_(actor)
            with self.subTest(roll=roll, level=level):
                self.assertEqual(self.client.get(reverse("org-membership-list")).status_code, 200)
                response = self.post(user=target.pk, node=self.u2.pk)
                self.assertEqual(response.status_code, 201 if allowed else 403, response.data)

    def test_create_returns_the_membership_without_personal_data(self):
        response = self.post(user=self.ali.pk, node=self.s1.pk, is_lead=True, position_label="سرپرست")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            set(response.data),
            {"id", "user", "user_name", "user_title", "user_is_active", "node", "node_name", "node_kind",
             "is_primary", "is_lead", "position_label"},
        )
        self.assertEqual(response.data["user_name"], "علی رضايي")
        self.assertEqual(response.data["user_title"], "کارمند/اپراتور")
        self.assertEqual((response.data["is_primary"], response.data["is_lead"]), (True, True))
        self.assertEqual(Membership.objects.get().added_by, self.ceo)

    def test_bad_input_is_a_400(self):
        for body in ({}, {"user": self.ali.pk}, {"node": self.s1.pk}, {"user": 999999999, "node": self.s1.pk},
                     {"user": self.ali.pk, "node": 999999999}):
            with self.subTest(body=body):
                self.assertEqual(self.post(**body).status_code, 400)

    def test_domain_conflicts_are_typed_409s(self):
        self.post(user=self.ali.pk, node=self.s1.pk)
        again = self.post(user=self.ali.pk, node=self.s1.pk)
        self.assertEqual((again.status_code, again.data["code"]), (409, "already_member"))
        self.assertIsInstance(again.data["existing_id"], int)
        tree.archive_node(self.u2)
        self.assertEqual(self.post(user=self.ali.pk, node=self.u2.pk).data["code"], "node_archived")
        self.ali.is_active = False
        self.ali.save()
        self.assertEqual(self.post(user=self.ali.pk, node=self.u4.pk).data["code"], "user_inactive")

    def test_patch_edits_lead_label_and_primary(self):
        first = self.post(user=self.ali.pk, node=self.s1.pk).data
        second = self.post(user=self.ali.pk, node=self.u2.pk).data
        url = reverse("org-membership-detail", args=[second["id"]])
        response = self.client.patch(url, {"is_primary": True, "is_lead": True, "position_label": "مدیر مالی"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data["is_primary"], response.data["is_lead"], response.data["position_label"]),
                         (True, True, "مدیر مالی"))
        self.assertFalse(Membership.objects.get(pk=first["id"]).is_primary)
        self.assert_one_primary(self.ali)

    def test_unsetting_the_primary_is_a_409(self):
        m = self.post(user=self.ali.pk, node=self.s1.pk).data
        response = self.client.patch(reverse("org-membership-detail", args=[m["id"]]), {"is_primary": False}, format="json")
        self.assertEqual((response.status_code, response.data["code"]), (409, "primary_required"))

    def test_the_person_and_node_cannot_be_changed(self):
        m = self.post(user=self.ali.pk, node=self.s1.pk).data
        url = reverse("org-membership-detail", args=[m["id"]])
        moved = self.client.patch(url, {"node": self.u2.pk}, format="json")
        self.assertEqual(moved.status_code, 400)
        self.assertIn("node", moved.data)
        swapped = self.client.patch(url, {"user": self.ceo.pk}, format="json")
        self.assertEqual(swapped.status_code, 400)
        self.assertEqual(self.client.patch(url, {"node": self.s1.pk, "is_lead": True}, format="json").status_code, 200)
        self.assertEqual(self.client.put(url, {}, format="json").status_code, 405)

    def test_delete_removes_and_promotes(self):
        first = self.post(user=self.ali.pk, node=self.s1.pk).data
        second = self.post(user=self.ali.pk, node=self.u2.pk).data
        self.assertEqual(self.client.delete(reverse("org-membership-detail", args=[first["id"]])).status_code, 204)
        self.assertTrue(Membership.objects.get(pk=second["id"]).is_primary)

    def test_a_guild_user_cannot_change_memberships(self):
        m = self.post(user=self.ali.pk, node=self.s1.pk).data
        self.as_(self.guild)
        url = reverse("org-membership-detail", args=[m["id"]])
        self.assertEqual(self.client.patch(url, {"is_lead": True}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.assertFalse(Membership.objects.get(pk=m["id"]).is_lead)

    def test_anonymous_gets_401(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse("org-membership-list")).status_code, 401)

    def test_the_list_filters(self):
        bea = person("9600000002", "بئاتریس")
        join(self.ali, self.s1, is_lead=True)
        join(self.ali, self.u2)
        join(bea, self.s1)
        url = reverse("org-membership-list")
        self.assertEqual(self.client.get(url).data["count"], 3)
        self.assertEqual(self.client.get(url, {"node": self.s1.pk}).data["count"], 2)
        self.assertEqual(self.client.get(url, {"user": self.ali.pk}).data["count"], 2)
        self.assertEqual(self.client.get(url, {"is_lead": "1"}).data["count"], 1)
        self.assertEqual(self.client.get(url, {"node": "x"}).data["count"], 0)

    def test_deactivated_people_are_hidden_by_default_but_keep_their_memberships(self):
        m = join(self.ali, self.s1)
        self.ali.is_active = False
        self.ali.save()
        url = reverse("org-membership-list")
        self.assertEqual(self.client.get(url).data["count"], 0)
        self.assertEqual(self.client.get(url, {"include_inactive": "1"}).data["count"], 1)
        self.assertEqual(self.client.get(reverse("org-membership-detail", args=[m.pk])).status_code, 200)
        self.ali.is_active = True
        self.ali.save()
        self.assertEqual(self.client.get(url).data["count"], 1)  # reactivating restores it

    def test_node_members_lists_leads_first_then_by_name(self):
        for code, name, lead in (("9600000003", "ژاله", False), ("9600000004", "ب", True), ("9600000005", "الف", False)):
            join(person(code, name), self.s1, is_lead=lead)
        gone = person("9600000006", "غایب")
        join(gone, self.s1)
        gone.is_active = False
        gone.save()
        self.as_(self.guild)
        response = self.client.get(reverse("org-node-members", args=[self.s1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([m["user_name"] for m in response.data["results"]], ["ب", "الف", "ژاله"])
        everyone = self.client.get(reverse("org-node-members", args=[self.s1.pk]), {"include_inactive": "1"})
        self.assertEqual(everyone.data["count"], 4)
        self.assertEqual(self.client.get(reverse("org-node-members", args=[999999999])).status_code, 404)

    def test_node_members_only_lists_that_nodes_direct_members(self):
        join(self.ali, self.s1)
        join(person("9600000007"), self.u1)
        self.assertEqual(self.client.get(reverse("org-node-members", args=[self.u1.pk])).data["count"], 1)

    def test_deleting_a_node_with_members_is_a_409_that_counts_them(self):
        join(self.ali, self.u4)
        response = self.client.delete(reverse("org-node-detail", args=[self.u4.pk]))
        self.assertEqual((response.status_code, response.data["members"]), (409, 1))


class PeopleApiTests(MembershipAssertions, ApiTestCase):
    def setUp(self):
        super().setUp()
        self.build()
        self.ali = person("9700000001", "علی رضايي", mobile_phone="09121112233")
        self.bea = person("9700000002", "بهار احمدی")
        self.cyrus = person("9700000003", "کوروش")
        join(self.ali, self.s1, is_lead=True, position_label="سرپرست")
        join(self.ali, self.u2)
        join(self.bea, self.s1)
        self.as_(self.guild)
        self.url = reverse("org-people")

    def names(self, **params):
        return [p["full_name"] for p in self.client.get(self.url, params).data["results"]]

    def test_it_needs_a_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_a_person_exposes_name_title_and_places_but_never_personal_data(self):
        person_row = next(p for p in self.client.get(self.url, {"q": "رضایی"}).data["results"])
        self.assertEqual(set(person_row), {"id", "full_name", "title", "is_active", "memberships"})
        self.assertEqual(person_row["title"], "کارمند/اپراتور")
        self.assertEqual(
            set(person_row["memberships"][0]),
            {"id", "node", "node_name", "node_kind", "is_primary", "is_lead", "position_label"},
        )
        self.assertNotIn("09121112233", str(self.client.get(self.url).data))
        self.assertNotIn(self.ali.national_code, str(self.client.get(self.url).data))

    def test_memberships_come_primary_first(self):
        row = next(iter(self.client.get(self.url, {"q": "رضایی"}).data["results"]))
        self.assertEqual([m["node_name"] for m in row["memberships"]], ["بخش یک", "واحد مالی"])
        self.assertTrue(row["memberships"][0]["is_primary"])

    def test_search_ignores_letterform_and_digit_differences(self):
        self.assertEqual(self.names(q="رضایی"), ["علی رضايي"])
        self.assertEqual(self.names(q="رضايي"), ["علی رضايي"])
        self.assertEqual(self.names(q="کوروش"), ["کوروش"])
        self.assertEqual(self.names(q="نامعلوم"), [])

    def test_unassigned_and_node_filters(self):
        self.assertIn("کوروش", self.names(unassigned="1"))
        self.assertNotIn("علی رضايي", self.names(unassigned="1"))
        self.assertEqual(sorted(self.names(node=self.s1.pk)), sorted(["علی رضايي", "بهار احمدی"]))
        self.assertEqual(self.names(node=self.u2.pk), ["علی رضايي"])  # one row, though Ali has two places
        self.assertEqual(self.names(node="x"), [])

    def test_deactivated_people_are_hidden_unless_asked_for(self):
        self.cyrus.is_active = False
        self.cyrus.save()
        self.assertNotIn("کوروش", self.names())
        self.assertIn("کوروش", self.names(include_inactive="1"))

    def test_the_directory_is_ordered_by_name_and_paginated(self):
        response = self.client.get(self.url)
        self.assertIn("count", response.data)
        names = [p["full_name"] for p in response.data["results"]]
        self.assertEqual(names, sorted(names))

    def test_a_page_costs_three_queries_however_many_people_there_are(self):
        for i in range(10):
            join(person(f"98{i:08d}", f"نفر {i}"), self.s1)
        with self.assertNumQueries(3):  # the count, the people, their memberships
            self.client.get(self.url, {"page_size": 50})


class PersonnelDeletionWithMembershipsTests(ApiTestCase):
    def test_a_person_with_memberships_cannot_be_deleted_and_the_answer_says_why(self):
        self.build()
        member = person("9800000001")
        join(member, self.s1)
        join(member, self.u2)
        response = self.as_(self.ceo).delete(reverse("personnel-detail", args=[member.pk]))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "user_has_memberships")
        self.assertEqual(response.data["memberships"], 2)
        self.assertIn("غیرفعال", response.data["detail"])
        self.assertTrue(User.objects.filter(pk=member.pk).exists())

    def test_once_their_memberships_are_gone_they_can_be_deleted(self):
        self.build()
        member = person("9800000002")
        membership = join(member, self.s1)
        memberships.remove_membership(membership)
        self.assertEqual(self.as_(self.ceo).delete(reverse("personnel-detail", args=[member.pk])).status_code, 204)

    def test_deactivating_is_the_supported_way_and_keeps_the_memberships(self):
        self.build()
        member = person("9800000003")
        join(member, self.s1)
        response = self.as_(self.ceo).patch(reverse("personnel-detail", args=[member.pk]), {"is_active": False}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Membership.objects.filter(user=member).count(), 1)


@skipUnlessDBFeature("has_select_for_update")
class MembershipConcurrencyTests(Threaded, MembershipAssertions, SampleTree, TransactionTestCase):
    def setUp(self):
        self.build()
        self.ali = person("9900000001")

    def test_concurrent_first_memberships_leave_exactly_one_primary(self):
        nodes = [self.u1, self.u2, self.u3, self.u4]
        results = self.run_concurrently(lambda i: join(self.ali, nodes[i]), 4)
        self.assertEqual([r for r in results if r[0] == "err"], [])
        self.assertEqual(Membership.objects.filter(user=self.ali).count(), 4)
        self.assert_one_primary(self.ali)

    def test_concurrent_primary_changes_leave_exactly_one_primary(self):
        rows = [join(self.ali, node) for node in (self.u1, self.u2, self.u3, self.u4)]
        results = self.run_concurrently(lambda i: memberships.update_membership(rows[i], is_primary=True), 4)
        self.assertEqual([r for r in results if r[0] == "err"], [])
        self.assert_one_primary(self.ali)

    def test_concurrent_removal_of_the_primary_and_another_keeps_one_primary(self):
        rows = [join(self.ali, node) for node in (self.u1, self.u2, self.u3)]
        results = self.run_concurrently(lambda i: memberships.remove_membership(rows[i]), 2)
        self.assertEqual([r for r in results if r[0] == "err"], [])
        self.assert_one_primary(self.ali)
