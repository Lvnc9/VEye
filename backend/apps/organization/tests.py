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

from . import tree
from .models import ALLOWED_PARENT_KINDS, Company, OrgNode, OrgNodeKind, SetupStep

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


@skipUnlessDBFeature("has_select_for_update")
class ConcurrencyTests(TreeAssertions, TransactionTestCase):
    """Real threads against a real database. Skipped on SQLite, which has no row locks; run
    in the compose backend container (Postgres)."""

    def setUp(self):
        self.root = make_company()
        self.d1 = add(DOMAIN, "حوزه یک", self.root)
        self.d2 = add(DOMAIN, "حوزه دو", self.root)

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
