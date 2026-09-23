"""Slices 8.1 (projects, members, events) and 8.2 (objectives, progress)."""
from datetime import date, timedelta
from unittest import mock

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import AccessLevel, AccessRoll, Capability, User
from apps.core.exceptions import ConflictError
from apps.organization import memberships, tree
from apps.organization.tests import SampleTree, Threaded, add, join, person
from apps.organization.tests import ApiTestCase as OrgApiTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import services
from .models import (
    Objective,
    ObjectiveStatus,
    Project,
    ProjectComment,
    ProjectDocumentLink,
    ProjectEvent,
    ProjectEventKind,
    ProjectMember,
    ProjectRole,
    ProjectStatus,
)
from .queries import progress_percent
from .services import COMMENT_MAX_LENGTH


def new_project(actor, section, name="پروژه نمونه", **kwargs):
    return services.create_project(actor=actor, section=section, name=name, **kwargs)


def events(project):
    return list(project.events.values_list("kind", flat=True))


class ProjectFixtures(SampleTree):
    """The org sample tree (…D1 ─ U1 ─ S1, U2, D2 ─ U3, U4) plus a بخش in the other branch."""

    def build_world(self):
        self.build()
        self.s2 = add("SECTION", "بخش دو", self.u3)  # D2 ─ U3 ─ S2: another branch entirely
        self.mgr = person("9800000001", "مدیر پروژه")
        self.member = person("9800000002", "عضو پروژه")
        self.outsider = person("9800000003", "بیرونی")
        join(self.mgr, self.s1)
        join(self.member, self.s1)


class ProjectConstraintTests(ProjectFixtures, TestCase):
    def setUp(self):
        self.build_world()

    def test_names_are_unique_per_section_on_the_normalised_key(self):
        new_project(self.mgr, self.s1, "پروژه ي")
        with self.assertRaises(ConflictError) as caught:
            new_project(self.mgr, self.s1, "پروژه ی")  # Arabic vs Persian yeh
        self.assertEqual(caught.exception.payload["code"], "duplicate_name")
        new_project(self.mgr, self.s2, "پروژه ی")  # another بخش may reuse the name

    def test_the_database_refuses_a_duplicate_name_in_a_section(self):
        new_project(self.mgr, self.s1, "الف")
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            Project.objects.create(section=self.s1, name="ب", name_key="الف", created_by=self.mgr)
        self.assertIn("uniq_project_name_per_section", str(caught.exception))

    def test_the_database_refuses_a_deadline_before_the_start(self):
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            Project.objects.create(
                section=self.s1, name="ب", name_key="ب", created_by=self.mgr,
                starts_on=date(2026, 5, 10), due_on=date(2026, 5, 1),
            )
        self.assertIn("project_due_not_before_start", str(caught.exception))
        Project.objects.create(section=self.s1, name="ج", name_key="ج", created_by=self.mgr, due_on=date(2026, 5, 1))

    def test_a_person_is_a_member_of_a_project_once(self):
        project = new_project(self.mgr, self.s1)
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            ProjectMember.objects.create(project=project, user=self.mgr)
        self.assertIn("uniq_project_member", str(caught.exception))

    def test_the_foreign_keys_protect_people_and_sections(self):
        project = new_project(self.mgr, self.s1)
        with self.assertRaises(ProtectedError):
            self.mgr.delete()
        with self.assertRaises(ProtectedError):
            self.s1.delete()
        self.assertTrue(Project.objects.filter(pk=project.pk).exists())


class ProjectCreationTests(ProjectFixtures, TestCase):
    def setUp(self):
        self.build_world()

    def test_the_creator_becomes_the_manager_and_the_only_event_is_project_created(self):
        project = new_project(self.mgr, self.s1, goal="  هدف  ")
        self.assertEqual(project.goal, "هدف")
        [member] = project.members.all()
        self.assertEqual((member.user, member.role, member.is_guest), (self.mgr, ProjectRole.MANAGER, False))
        self.assertEqual(events(project), [ProjectEventKind.PROJECT_CREATED])

    def test_a_creator_outside_the_section_is_a_guest_manager(self):
        project = new_project(self.outsider, self.s1)
        [member] = project.members.all()
        self.assertEqual((member.role, member.is_guest), (ProjectRole.MANAGER, True))

    def test_members_are_added_and_guests_are_those_outside_the_section(self):
        project = new_project(
            self.mgr, self.s1,
            members=[{"user": self.member}, {"user": self.outsider, "role": ProjectRole.MANAGER}],
        )
        rows = {m.user_id: m for m in project.members.all()}
        self.assertEqual(rows[self.member.pk].is_guest, False)
        self.assertEqual((rows[self.outsider.pk].role, rows[self.outsider.pk].is_guest), (ProjectRole.MANAGER, True))
        self.assertEqual(
            events(project),
            [ProjectEventKind.PROJECT_CREATED, ProjectEventKind.MEMBER_ADDED, ProjectEventKind.GUEST_INVITED],
        )

    def test_the_creator_listed_as_an_ordinary_member_is_still_the_manager(self):
        project = new_project(self.mgr, self.s1, members=[{"user": self.mgr, "role": ProjectRole.MEMBER}, {"user": self.member}])
        self.assertEqual(project.members.count(), 2)
        self.assertEqual(project.members.get(user=self.mgr).role, ProjectRole.MANAGER)

    def test_a_person_listed_twice_is_added_once(self):
        project = new_project(self.mgr, self.s1, members=[{"user": self.member}, {"user": self.member, "role": ProjectRole.MANAGER}])
        self.assertEqual(project.members.filter(user=self.member).count(), 1)
        self.assertEqual(project.members.get(user=self.member).role, ProjectRole.MEMBER)  # the first entry wins

    def test_a_project_lives_in_a_section_only(self):
        for node in (self.root, self.d1, self.u1):
            with self.subTest(kind=node.kind), self.assertRaises(ValidationError) as caught:
                new_project(self.mgr, node)
            self.assertIn("section", caught.exception.detail)

    def test_an_archived_section_takes_no_projects(self):
        tree.archive_node(self.s1)
        with self.assertRaises(ConflictError) as caught:
            new_project(self.mgr, self.s1)
        self.assertEqual(caught.exception.payload["code"], "section_archived")

    def test_bad_names_and_dates_are_refused(self):
        with self.assertRaises(ValidationError):
            new_project(self.mgr, self.s1, "   ")
        with self.assertRaises(ValidationError) as caught:
            new_project(self.mgr, self.s1, starts_on=date(2026, 6, 1), due_on=date(2026, 5, 1))
        self.assertIn("due_on", caught.exception.detail)
        self.assertFalse(Project.objects.exists())

    def test_an_inactive_member_refuses_the_whole_creation_and_leaves_nothing_behind(self):
        gone = person("9800000010")
        gone.is_active = False
        gone.save()
        with self.assertRaises(ConflictError) as caught:
            new_project(self.mgr, self.s1, members=[{"user": self.member}, {"user": gone}])
        self.assertEqual(caught.exception.payload["code"], "user_inactive")
        self.assertEqual((Project.objects.count(), ProjectMember.objects.count(), ProjectEvent.objects.count()), (0, 0, 0))

    def test_a_failure_part_way_rolls_back_the_project_members_and_events(self):
        with mock.patch.object(services, "_add_member", side_effect=[None, RuntimeError("boom")]):
            with self.assertRaises(RuntimeError):
                new_project(self.mgr, self.s1, members=[{"user": self.member}])
        self.assertEqual((Project.objects.count(), ProjectEvent.objects.count()), (0, 0))

    @override_settings(PROJECT_MAX_MEMBERS=2)
    def test_a_project_holds_at_most_the_configured_number_of_people(self):
        third = person("9800000011")
        with self.assertRaises(ConflictError) as caught:
            new_project(self.mgr, self.s1, members=[{"user": self.member}, {"user": third}])
        self.assertEqual(caught.exception.payload["code"], "member_limit")
        self.assertFalse(Project.objects.exists())


class ProjectUpdateTests(ProjectFixtures, TestCase):
    def setUp(self):
        self.build_world()
        self.project = new_project(self.mgr, self.s1, "الف", starts_on=date(2026, 1, 1), due_on=date(2026, 12, 1))

    def update(self, **changes):
        return services.update_project(self.project, actor=self.mgr, changes=changes)

    def test_edits_apply_and_only_a_status_change_reaches_the_feed(self):
        project = self.update(name="  ب  ", goal="هدف تازه", due_on=date(2027, 1, 1))
        self.assertEqual((project.name, project.goal, str(project.due_on)), ("ب", "هدف تازه", "2027-01-01"))
        self.assertEqual(events(project), [ProjectEventKind.PROJECT_CREATED])

    def test_a_status_change_is_recorded_with_from_and_to(self):
        self.update(status=ProjectStatus.ON_HOLD)
        event = self.project.events.latest("id")
        self.assertEqual(
            (event.kind, event.from_status, event.to_status, event.actor_name),
            (ProjectEventKind.PROJECT_STATUS_CHANGED, ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD, self.mgr.full_name),
        )

    def test_status_moves_permissively_in_any_direction(self):
        for status in (ProjectStatus.DONE, ProjectStatus.ACTIVE, ProjectStatus.CANCELLED, ProjectStatus.ON_HOLD):
            self.assertEqual(self.update(status=status).status, status)
        self.assertEqual(events(self.project).count(ProjectEventKind.PROJECT_STATUS_CHANGED), 4)

    def test_setting_the_same_status_writes_no_event(self):
        self.update(status=ProjectStatus.ACTIVE)
        self.assertEqual(events(self.project), [ProjectEventKind.PROJECT_CREATED])

    def test_a_dates_can_be_cleared(self):
        project = self.update(due_on=None, starts_on=None)
        self.assertEqual((project.starts_on, project.due_on), (None, None))

    def test_renaming_onto_a_sibling_conflicts_and_keeps_its_own_name(self):
        new_project(self.mgr, self.s1, "ب")
        with self.assertRaises(ConflictError):
            self.update(name="ب")
        self.assertEqual(self.update(name="الف  ").name, "الف")  # its own name, respaced: no clash with itself

    def test_a_deadline_before_the_start_is_refused_and_nothing_changes(self):
        with self.assertRaises(ValidationError):
            self.update(due_on=date(2025, 1, 1), goal="نباید بماند")
        self.project.refresh_from_db()
        self.assertEqual(self.project.goal, "")

    def test_an_unknown_field_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            self.update(created_by=self.member)

    def test_the_actor_is_snapshotted_as_text_and_survives_a_rename(self):
        self.update(status=ProjectStatus.DONE)
        self.mgr.full_name = "نام تازه"
        self.mgr.save()
        event = self.project.events.latest("id")
        self.assertEqual(event.actor_name, "مدیر پروژه")
        self.assertEqual(event.actor_title, "کارمند/اپراتور")


class ProjectArchiveTests(ProjectFixtures, TestCase):
    def setUp(self):
        self.build_world()
        self.project = new_project(self.mgr, self.s1, members=[{"user": self.member}])

    def test_archiving_and_unarchiving_are_recorded_and_idempotent(self):
        services.archive_project(self.project, actor=self.mgr)
        services.archive_project(self.project, actor=self.mgr)  # second time: nothing new
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_archived)
        services.unarchive_project(self.project, actor=self.mgr)
        services.unarchive_project(self.project, actor=self.mgr)
        self.project.refresh_from_db()
        self.assertFalse(self.project.is_archived)
        self.assertEqual(
            events(self.project)[-2:], [ProjectEventKind.PROJECT_ARCHIVED, ProjectEventKind.PROJECT_UNARCHIVED]
        )
        self.assertEqual(events(self.project).count(ProjectEventKind.PROJECT_ARCHIVED), 1)

    def test_an_archived_project_is_read_only_everywhere(self):
        services.archive_project(self.project, actor=self.mgr)
        member = self.project.members.get(user=self.member)
        operations = {
            "update": lambda: services.update_project(self.project, actor=self.mgr, changes={"goal": "x"}),
            "add_member": lambda: services.add_member(self.project, actor=self.mgr, user=self.outsider),
            "change_role": lambda: services.change_role(member, actor=self.mgr, role=ProjectRole.MANAGER),
            "remove_member": lambda: services.remove_member(member, actor=self.mgr),
        }
        for name, operation in operations.items():
            with self.subTest(name), self.assertRaises(ConflictError) as caught:
                operation()
            self.assertEqual(caught.exception.payload["code"], "project_archived")
        self.assertEqual(self.project.members.count(), 2)

    def test_done_and_cancelled_projects_stay_editable_so_they_can_be_reopened(self):
        services.update_project(self.project, actor=self.mgr, changes={"status": ProjectStatus.DONE})
        project = services.update_project(self.project, actor=self.mgr, changes={"status": ProjectStatus.ACTIVE})
        self.assertEqual(project.status, ProjectStatus.ACTIVE)

    def test_a_project_cannot_come_back_into_an_archived_section(self):
        services.archive_project(self.project, actor=self.mgr)
        tree.archive_node(self.s1)
        with self.assertRaises(ConflictError) as caught:
            services.unarchive_project(self.project, actor=self.mgr)
        self.assertEqual(caught.exception.payload["code"], "section_archived")


class ProjectMemberServiceTests(ProjectFixtures, TestCase):
    def setUp(self):
        self.build_world()
        self.project = new_project(self.mgr, self.s1)

    def test_adding_a_member_or_a_guest_is_recorded_by_name(self):
        services.add_member(self.project, actor=self.mgr, user=self.member)
        guest = services.add_member(self.project, actor=self.mgr, user=self.outsider)
        self.assertTrue(guest.is_guest)
        added = list(self.project.events.filter(kind__in=[ProjectEventKind.MEMBER_ADDED, ProjectEventKind.GUEST_INVITED]))
        self.assertEqual([(e.kind, e.subject_title) for e in added],
                         [(ProjectEventKind.MEMBER_ADDED, "عضو پروژه"), (ProjectEventKind.GUEST_INVITED, "بیرونی")])

    def test_guest_status_is_stored_at_add_time_and_does_not_flip_when_they_move(self):
        guest = services.add_member(self.project, actor=self.mgr, user=self.outsider)
        join(self.outsider, self.s1)  # the guest later joins the بخش
        guest.refresh_from_db()
        self.assertTrue(guest.is_guest)  # history is not reclassified

    def test_someone_who_sits_in_another_section_is_still_a_guest_here(self):
        """Guest means "not in *this* project's بخش", not "in no بخش at all"."""
        elsewhere = person("9800000012")
        join(elsewhere, self.s2)
        member = services.add_member(self.project, actor=self.mgr, user=elsewhere)
        self.assertTrue(member.is_guest)

    def test_a_person_cannot_be_added_twice_or_when_inactive(self):
        first = services.add_member(self.project, actor=self.mgr, user=self.member)
        with self.assertRaises(ConflictError) as caught:
            services.add_member(self.project, actor=self.mgr, user=self.member)
        self.assertEqual((caught.exception.payload["code"], caught.exception.payload["existing_id"]), ("already_member", first.pk))
        self.outsider.is_active = False
        self.outsider.save()
        with self.assertRaises(ConflictError) as caught:
            services.add_member(self.project, actor=self.mgr, user=self.outsider)
        self.assertEqual(caught.exception.payload["code"], "user_inactive")

    def test_the_last_manager_can_be_neither_demoted_nor_removed(self):
        manager = self.project.members.get(user=self.mgr)
        for operation in (
            lambda: services.change_role(manager, actor=self.mgr, role=ProjectRole.MEMBER),
            lambda: services.remove_member(manager, actor=self.mgr),
        ):
            with self.assertRaises(ConflictError) as caught:
                operation()
            self.assertEqual(caught.exception.payload["code"], "last_manager")
        manager.refresh_from_db()
        self.assertEqual(manager.role, ProjectRole.MANAGER)

    def test_with_a_second_manager_either_can_step_down_or_leave(self):
        second = services.add_member(self.project, actor=self.mgr, user=self.member, role=ProjectRole.MANAGER)
        services.change_role(second, actor=self.mgr, role=ProjectRole.MEMBER)  # fine: mgr is still a manager
        services.change_role(second, actor=self.mgr, role=ProjectRole.MANAGER)
        services.remove_member(self.project.members.get(user=self.mgr), actor=self.member)
        self.assertEqual(list(self.project.members.values_list("user_id", flat=True)), [self.member.pk])

    def test_role_changes_and_removals_are_recorded(self):
        member = services.add_member(self.project, actor=self.mgr, user=self.member)
        services.change_role(member, actor=self.mgr, role=ProjectRole.MANAGER)
        services.change_role(member, actor=self.mgr, role=ProjectRole.MANAGER)  # unchanged: no event
        services.remove_member(member, actor=self.mgr)
        self.assertEqual(
            events(self.project)[-3:],
            [ProjectEventKind.MEMBER_ADDED, ProjectEventKind.MEMBER_ROLE_CHANGED, ProjectEventKind.MEMBER_REMOVED],
        )
        self.assertEqual(self.project.events.latest("id").subject_title, "عضو پروژه")

    def test_a_member_of_another_project_is_not_found(self):
        other = new_project(self.mgr, self.s1, "پروژه دیگر", members=[{"user": self.member}])
        foreign = other.members.get(user=self.member)
        with self.assertRaises(Exception) as caught:
            services.remove_member(ProjectMember(pk=foreign.pk, project=self.project, user=self.member), actor=self.mgr)
        self.assertEqual(getattr(caught.exception, "status_code", None), 404)
        self.assertTrue(other.members.filter(user=self.member).exists())


# ---------------------------------------------------------------------------
# The API
# ---------------------------------------------------------------------------


class ProjectApiCase(ProjectFixtures, OrgApiTestCase):
    def setUp(self):
        super().setUp()
        self.build_world()
        self.hq = person("9800000020", "ستادی", roll=AccessRoll.HEADQUARTERS, level=AccessLevel.LEVEL_2)
        self.lead_s1 = person("9800000021", "مسئول بخش")
        self.lead_d1 = person("9800000022", "مسئول حوزه")
        self.lead_d2 = person("9800000023", "مسئول حوزه دو")
        join(self.lead_s1, self.s1, is_lead=True)
        join(self.lead_d1, self.d1, is_lead=True)
        join(self.lead_d2, self.d2, is_lead=True)

    def create(self, **body):
        body = {"section": self.s1.pk, "name": "پروژهٔ آزمایشی", **body}
        return self.client.post(reverse("project-list"), body, format="json")

    def detail_url(self, project):
        return reverse("project-detail", args=[project.pk])


class ProjectCreateApiTests(ProjectApiCase):
    def test_who_may_create_follows_create_project_or_leading_the_section(self):
        allowed = [self.ceo, self.hq, self.lead_s1, self.lead_d1]  # capability, capability, lead, lead of an ancestor
        denied = [self.guild, self.member, self.lead_d2]  # صفی, plain member, lead of ANOTHER branch
        for number, user in enumerate(allowed):
            with self.subTest(user=user.full_name, allowed=True):
                self.as_(user)
                self.assertEqual(self.create(name=f"پروژه {number}").status_code, 201)
        for number, user in enumerate(denied):
            with self.subTest(user=user.full_name, allowed=False):
                self.as_(user)
                response = self.create(name=f"ممنوع {number}")
                self.assertEqual(response.status_code, 403)
                self.assertIn("اجازهٔ ایجاد پروژه", response.data["detail"])
        self.assertEqual(Project.objects.count(), 4)

    def test_the_capability_matrix_for_every_roll_and_level(self):
        combos = [(roll, level) for roll in AccessRoll.values for level in AccessLevel.values]
        for number, (roll, level) in enumerate(combos):
            user = person(f"9801{number:06d}", roll=roll, level=level)
            expected = User(access_roll=roll, access_level=level).has_capability(Capability.CREATE_PROJECT)
            self.as_(user)
            with self.subTest(roll=roll, level=level):
                self.assertEqual(self.create(name=f"م {number}").status_code, 201 if expected else 403)

    def test_create_returns_the_detail_with_the_creator_as_manager(self):
        self.as_(self.hq)
        response = self.create(goal="هدف", starts_on="2026-01-01", due_on="2026-06-01", members=[{"user": self.member.pk}])
        self.assertEqual(response.status_code, 201, response.data)
        body = response.data
        self.assertEqual((body["name"], body["my_role"], body["can_edit"], body["section_name"]),
                         ("پروژهٔ آزمایشی", "MANAGER", True, "بخش یک"))
        self.assertEqual([(m["user_name"], m["role"], m["is_guest"]) for m in body["members"]],
                         [("ستادی", "MANAGER", True), ("عضو پروژه", "MEMBER", False)])
        self.assertEqual(Project.objects.get().created_by, self.hq)

    def test_members_are_never_shown_with_personal_data(self):
        self.as_(self.hq)
        body = self.create(members=[{"user": self.member.pk}]).data
        self.assertEqual(set(body["members"][0]),
                         {"id", "user", "user_name", "user_title", "role", "role_label", "is_guest"})
        self.assertNotIn(self.member.national_code, str(body))

    def test_bad_input_is_a_400_and_domain_conflicts_are_typed_409s(self):
        self.as_(self.hq)
        for body in ({"name": "الف"}, {"section": self.s1.pk}, {"section": 999999999, "name": "الف"},
                     {"section": self.s1.pk, "name": "الف", "due_on": "not-a-date"},
                     {"section": self.s1.pk, "name": "الف", "members": [{"user": 999999999}]}):
            with self.subTest(body=body):
                self.assertEqual(self.client.post(reverse("project-list"), body, format="json").status_code, 400)
        self.assertEqual(self.create(section=self.u1.pk).status_code, 400)  # a واحد, not a بخش
        self.assertEqual(self.create().status_code, 201)
        clash = self.create()
        self.assertEqual((clash.status_code, clash.data["code"]), (409, "duplicate_name"))
        self.assertIsInstance(clash.data["existing_id"], int)

    def test_anonymous_gets_401(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse("project-list")).status_code, 401)
        self.assertEqual(self.client.post(reverse("project-list"), {}, format="json").status_code, 401)


class ProjectVisibilityApiTests(ProjectApiCase):
    def setUp(self):
        super().setUp()
        self.project = new_project(self.mgr, self.s1, "پروژهٔ بخش یک", members=[{"user": self.member}])
        self.other = new_project(self.hq, self.s2, "پروژهٔ بخش دو")  # a different branch, different people

    def names(self, user, **params):
        self.as_(user)
        return sorted(p["name"] for p in self.client.get(reverse("project-list"), params).data["results"])

    def test_a_member_sees_only_their_own_projects(self):
        self.assertEqual(self.names(self.member), ["پروژهٔ بخش یک"])
        self.assertEqual(self.names(self.hq), ["پروژهٔ بخش دو"])

    def test_leads_see_their_whole_subtree_and_nothing_beside_it(self):
        self.assertEqual(self.names(self.lead_s1), ["پروژهٔ بخش یک"])
        self.assertEqual(self.names(self.lead_d1), ["پروژهٔ بخش یک"])  # lead of an ancestor
        self.assertEqual(self.names(self.lead_d2), ["پروژهٔ بخش دو"])

    def test_manage_organization_sees_everything(self):
        self.assertEqual(self.names(self.ceo), ["پروژهٔ بخش دو", "پروژهٔ بخش یک"])

    def test_an_outsider_sees_nothing_and_an_invisible_project_is_a_404_not_a_403(self):
        self.assertEqual(self.names(self.outsider), [])
        self.assertEqual(self.client.get(self.detail_url(self.project)).status_code, 404)
        members_url = reverse("project-add-member", args=[self.project.pk])
        self.assertEqual(self.client.post(members_url, {"user": self.member.pk}, format="json").status_code, 404)
        self.assertEqual(self.client.patch(self.detail_url(self.project), {"goal": "x"}, format="json").status_code, 404)

    def test_someone_who_leads_a_different_branch_cannot_read_it(self):
        self.as_(self.lead_d2)
        self.assertEqual(self.client.get(self.detail_url(self.project)).status_code, 404)

    def test_an_archived_lead_membership_gives_no_visibility(self):
        tree.archive_node(self.s1)  # archiving needs no active children: a بخش has none
        self.assertEqual(self.names(self.lead_s1), [])

    def test_the_list_never_repeats_a_project_for_someone_who_is_both_member_and_lead(self):
        join(self.mgr, self.d1, is_lead=True)  # mgr is a member of the project AND leads an ancestor
        self.as_(self.mgr)
        self.assertEqual(self.client.get(reverse("project-list")).data["count"], 1)

    def test_the_filters(self):
        third = new_project(self.mgr, self.s1, "طرح ي دیگر", members=[{"user": self.member}])
        services.update_project(third, actor=self.mgr, changes={"status": ProjectStatus.ON_HOLD})
        self.assertEqual(self.names(self.ceo, section=self.s2.pk), ["پروژهٔ بخش دو"])
        self.assertEqual(self.names(self.ceo, status="ON_HOLD"), ["طرح ي دیگر".replace("ي", "ی")])
        self.assertEqual(self.names(self.ceo, q="طرح ی"), ["طرح ی دیگر"])  # Arabic yeh typed either way
        self.assertEqual(self.names(self.ceo, q="طرح ي"), ["طرح ی دیگر"])
        self.assertEqual(self.names(self.ceo, mine="1"), [])  # the CEO is on none of them
        self.assertEqual(self.names(self.member, mine="1"), sorted(["پروژهٔ بخش یک", "طرح ی دیگر"]))
        self.assertEqual(self.names(self.ceo, section="x"), [])

    def test_archived_projects_are_hidden_by_default_and_listed_on_request(self):
        services.archive_project(self.project, actor=self.mgr)
        self.assertEqual(self.names(self.ceo), ["پروژهٔ بخش دو"])
        self.assertEqual(self.names(self.ceo, archived="1"), ["پروژهٔ بخش یک"])
        self.as_(self.member)
        self.assertEqual(self.client.get(self.detail_url(self.project)).status_code, 200)  # still readable

    def test_a_list_page_costs_a_fixed_number_of_queries(self):
        for number in range(6):
            new_project(self.mgr, self.s1, f"انبوه {number}", members=[{"user": self.member}])
        self.as_(self.member)
        with self.assertNumQueries(4):  # the count, the projects, their members, the viewer's lead memberships
            self.client.get(reverse("project-list"), {"page_size": 50})

    def test_the_row_carries_what_a_list_needs(self):
        self.as_(self.member)
        row = self.client.get(reverse("project-list")).data["results"][0]
        self.assertEqual((row["my_role"], row["can_edit"], row["member_count"], row["status_label"]), ("MEMBER", False, 2, "در حال اجرا"))
        self.assertEqual([m["name"] for m in row["members_preview"]], ["مدیر پروژه", "عضو پروژه"])
        self.assertNotIn("members", row)


class ProjectEditApiTests(ProjectApiCase):
    def setUp(self):
        super().setUp()
        self.project = new_project(self.mgr, self.s1, members=[{"user": self.member}])

    def test_the_manager_and_leads_may_edit_a_plain_member_may_not(self):
        for user in (self.mgr, self.lead_s1, self.lead_d1):
            self.as_(user)
            with self.subTest(user=user.full_name):
                response = self.client.patch(self.detail_url(self.project), {"goal": f"توسط {user.pk}"}, format="json")
                self.assertEqual(response.status_code, 200, response.data)
        self.as_(self.member)
        denied = self.client.patch(self.detail_url(self.project), {"goal": "هک"}, format="json")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.data["detail"], "شما مدیر این پروژه نیستید.")
        self.assertNotEqual(Project.objects.get().goal, "هک")

    def test_manage_organization_reads_everything_but_edits_only_as_a_lead_or_manager(self):
        """Plan §5.3: read = member, lead of an ancestor, or manage_organization; edit = the project's
        manager or a lead of its بخش (or an ancestor). Bootstrap makes the مدیر عامل lead of the company
        root, which is how they edit everything in a real deployment."""
        self.as_(self.ceo)
        self.assertEqual(self.client.get(self.detail_url(self.project)).status_code, 200)
        self.assertEqual(self.client.patch(self.detail_url(self.project), {"goal": "x"}, format="json").status_code, 403)
        join(self.ceo, self.root, is_lead=True)  # what bootstrap does
        self.assertEqual(self.client.patch(self.detail_url(self.project), {"goal": "y"}, format="json").status_code, 200)

    def test_the_can_edit_flag_is_the_same_answer(self):
        for user, expected in ((self.mgr, True), (self.member, False), (self.lead_d1, True), (self.ceo, False)):
            self.as_(user)
            self.assertEqual(self.client.get(self.detail_url(self.project)).data["can_edit"], expected, user.full_name)

    def test_patch_changes_status_and_dates_and_validates(self):
        self.as_(self.mgr)
        ok = self.client.patch(self.detail_url(self.project), {"status": "ON_HOLD", "due_on": "2026-09-01"}, format="json")
        self.assertEqual((ok.status_code, ok.data["status"], ok.data["status_label"]), (200, "ON_HOLD", "متوقف"))
        self.assertEqual(self.client.patch(self.detail_url(self.project), {"status": "NOPE"}, format="json").status_code, 400)
        early = self.client.patch(self.detail_url(self.project), {"starts_on": "2027-01-01"}, format="json")
        self.assertEqual(early.status_code, 400)  # the deadline (2026-09-01) would precede the start

    def test_put_and_delete_are_not_offered(self):
        self.as_(self.mgr)
        self.assertEqual(self.client.put(self.detail_url(self.project), {}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(self.detail_url(self.project)).status_code, 405)

    def test_archive_and_unarchive_and_the_read_only_answer(self):
        self.as_(self.mgr)
        archived = self.client.post(reverse("project-archive", args=[self.project.pk]))
        self.assertEqual((archived.status_code, archived.data["is_archived"]), (200, True))
        blocked = self.client.patch(self.detail_url(self.project), {"goal": "x"}, format="json")
        self.assertEqual((blocked.status_code, blocked.data["code"]), (409, "project_archived"))
        back = self.client.post(reverse("project-unarchive", args=[self.project.pk]))
        self.assertFalse(back.data["is_archived"])
        self.as_(self.member)
        self.assertEqual(self.client.post(reverse("project-archive", args=[self.project.pk])).status_code, 403)


class ProjectMemberApiTests(ProjectApiCase):
    def setUp(self):
        super().setUp()
        self.project = new_project(self.mgr, self.s1, members=[{"user": self.member}])
        self.members_url = reverse("project-add-member", args=[self.project.pk])

    def member_url(self, member):
        return reverse("project-member", args=[self.project.pk, member.pk])

    def test_a_manager_adds_a_member_and_a_guest(self):
        self.as_(self.mgr)
        member = self.client.post(self.members_url, {"user": self.outsider.pk}, format="json")
        self.assertEqual((member.status_code, member.data["is_guest"], member.data["role"]), (201, True, "MEMBER"))
        again = self.client.post(self.members_url, {"user": self.outsider.pk}, format="json")
        self.assertEqual((again.status_code, again.data["code"]), (409, "already_member"))
        self.assertEqual(self.client.post(self.members_url, {"user": 999999999}, format="json").status_code, 400)

    def test_a_plain_member_cannot_manage_members_but_a_lead_can(self):
        self.as_(self.member)
        self.assertEqual(self.client.post(self.members_url, {"user": self.outsider.pk}, format="json").status_code, 403)
        self.as_(self.lead_d1)
        self.assertEqual(self.client.post(self.members_url, {"user": self.outsider.pk}, format="json").status_code, 201)

    def test_role_change_and_removal_and_the_last_manager_guard(self):
        self.as_(self.mgr)
        row = self.project.members.get(user=self.member)
        promoted = self.client.patch(self.member_url(row), {"role": "MANAGER"}, format="json")
        self.assertEqual((promoted.status_code, promoted.data["role"]), (200, "MANAGER"))
        mgr_row = self.project.members.get(user=self.mgr)
        self.assertEqual(self.client.delete(self.member_url(mgr_row)).status_code, 204)  # a second manager exists now
        self.as_(self.member)  # the first manager left, so the promoted member now runs the project
        last = self.client.delete(self.member_url(row))
        self.assertEqual((last.status_code, last.data["code"]), (409, "last_manager"))

    def test_bad_role_and_unknown_member(self):
        self.as_(self.mgr)
        row = self.project.members.get(user=self.member)
        self.assertEqual(self.client.patch(self.member_url(row), {"role": "BOSS"}, format="json").status_code, 400)
        other = new_project(self.mgr, self.s1, "پروژه دیگر", members=[{"user": self.member}])
        foreign = other.members.get(user=self.member)
        self.assertEqual(self.client.delete(self.member_url(foreign)).status_code, 404)  # a member of a different project
        self.assertTrue(other.members.filter(user=self.member).exists())

    def test_deleting_a_person_or_a_section_with_projects_is_refused_with_the_reason(self):
        self.as_(self.ceo)
        response = self.client.delete(reverse("personnel-detail", args=[self.member.pk]))
        self.assertEqual(response.status_code, 409)
        self.assertIn(response.data["code"], {"user_has_memberships", "user_has_projects"})
        for membership in list(self.member.memberships.all()):
            memberships.remove_membership(membership)
        response = self.client.delete(reverse("personnel-detail", args=[self.member.pk]))
        self.assertEqual((response.status_code, response.data["code"], response.data["projects"]), (409, "user_has_projects", 1))
        section = self.client.delete(reverse("org-node-detail", args=[self.s1.pk]))
        self.assertEqual(section.status_code, 409)
        self.assertEqual(section.data["projects"], 1)


@skipUnlessDBFeature("has_select_for_update")
class ProjectConcurrencyTests(Threaded, ProjectFixtures, TransactionTestCase):
    def setUp(self):
        self.build_world()
        self.project = new_project(self.mgr, self.s1)

    def test_two_managers_leaving_at_once_never_leave_a_project_without_one(self):
        second = services.add_member(self.project, actor=self.mgr, user=self.member, role=ProjectRole.MANAGER)
        first = self.project.members.get(user=self.mgr)
        results = self.run_concurrently(lambda i: services.remove_member((first, second)[i], actor=self.mgr), 2)
        errors = [r[1] for r in results if r[0] == "err"]
        self.assertEqual(len([r for r in results if r[0] == "ok"]), 1, results)
        self.assertTrue(all(isinstance(e, ConflictError) and e.payload["code"] == "last_manager" for e in errors), errors)
        self.assertEqual(self.project.members.filter(role=ProjectRole.MANAGER).count(), 1)

    def test_concurrent_adds_of_one_person_yield_exactly_one_member(self):
        results = self.run_concurrently(lambda i: services.add_member(self.project, actor=self.mgr, user=self.outsider), 4)
        self.assertEqual(len([r for r in results if r[0] == "ok"]), 1, results)
        self.assertTrue(all(isinstance(r[1], ConflictError) and r[1].payload["code"] == "already_member" for r in results if r[0] == "err"))
        self.assertEqual(self.project.members.filter(user=self.outsider).count(), 1)
        self.assertEqual(self.project.events.filter(kind=ProjectEventKind.GUEST_INVITED).count(), 1)


# ---------------------------------------------------------------------------
# Slice 8.2 — objectives, assignment, progress
# ---------------------------------------------------------------------------


def add_objective(project, actor, assignee_member, **kwargs):
    kwargs.setdefault("title", "ریزهدف نمونه")
    kwargs.setdefault("due_on", date(2026, 12, 1))
    return services.add_objective(project, actor=actor, assignee=assignee_member, **kwargs)


class ObjectiveServiceTests(ProjectFixtures, TestCase):
    def setUp(self):
        self.build_world()
        self.project = new_project(self.mgr, self.s1, members=[{"user": self.member}])
        self.mgr_member = self.project.members.get(user=self.mgr)
        self.member_row = self.project.members.get(user=self.member)

    def test_an_objective_needs_an_assignee_and_a_deadline_and_gets_position_one(self):
        objective = add_objective(self.project, self.mgr, self.member_row, title="  اولین  ")
        self.assertEqual((objective.title, objective.position, objective.assignee, objective.status),
                         ("اولین", 1, self.member_row, ObjectiveStatus.TODO))
        self.assertEqual(events(self.project)[-1], ProjectEventKind.OBJECTIVE_ADDED)

    def test_positions_increase_and_are_never_reused(self):
        first = add_objective(self.project, self.mgr, self.member_row, title="یک")
        second = add_objective(self.project, self.mgr, self.member_row, title="دو")
        services.remove_objective(first, actor=self.mgr)
        third = add_objective(self.project, self.mgr, self.member_row, title="سه")
        self.assertEqual((second.position, third.position), (2, 3))

    def test_the_assignee_must_be_a_member_of_this_very_project(self):
        elsewhere = new_project(self.mgr, self.s1, "پروژهٔ دیگر", members=[{"user": self.outsider}])
        foreign_member = elsewhere.members.get(user=self.outsider)
        with self.assertRaises(ValidationError) as caught:
            add_objective(self.project, self.mgr, foreign_member)
        self.assertIn("assignee", caught.exception.detail)
        self.assertFalse(Objective.objects.filter(project=self.project).exists())

    def test_a_blank_title_is_refused(self):
        with self.assertRaises(ValidationError):
            add_objective(self.project, self.mgr, self.member_row, title="   ")

    def test_the_database_refuses_a_non_positive_weight(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Objective.objects.create(
                project=self.project, position=1, title="بد", assignee=self.member_row,
                due_on=date(2026, 1, 1), weight=0,
            )

    def test_an_objective_cannot_be_added_to_an_archived_project(self):
        services.archive_project(self.project, actor=self.mgr)
        with self.assertRaises(ConflictError) as caught:
            add_objective(self.project, self.mgr, self.member_row)
        self.assertEqual(caught.exception.payload["code"], "project_archived")

    @override_settings(PROJECT_MAX_OBJECTIVES=2)
    def test_a_project_holds_at_most_the_configured_number_of_objectives(self):
        add_objective(self.project, self.mgr, self.member_row, title="یک")
        add_objective(self.project, self.mgr, self.member_row, title="دو")
        with self.assertRaises(ConflictError) as caught:
            add_objective(self.project, self.mgr, self.member_row, title="سه")
        self.assertEqual(caught.exception.payload["code"], "objective_limit")
        self.assertEqual(Objective.objects.filter(project=self.project).count(), 2)


class ObjectiveUpdateTests(ProjectFixtures, TestCase):
    def setUp(self):
        self.build_world()
        self.project = new_project(self.mgr, self.s1, members=[{"user": self.member}])
        self.mgr_member = self.project.members.get(user=self.mgr)
        self.member_row = self.project.members.get(user=self.member)
        self.objective = add_objective(self.project, self.mgr, self.member_row, due_on=date(2026, 6, 1))

    def update(self, **changes):
        return services.update_objective(self.objective, actor=self.mgr, changes=changes)

    def test_title_description_and_weight_change_without_an_event(self):
        before = len(events(self.project))
        objective = self.update(title="  تازه  ", description="شرح", weight=3)
        self.assertEqual((objective.title, objective.description, objective.weight), ("تازه", "شرح", 3))
        self.assertEqual(len(events(self.project)), before)

    def test_a_status_change_is_recorded_with_from_and_to(self):
        self.update(status=ObjectiveStatus.IN_PROGRESS)
        event = self.project.events.latest("id")
        self.assertEqual(
            (event.kind, event.from_status, event.to_status, event.objective_id),
            (ProjectEventKind.OBJECTIVE_STATUS_CHANGED, ObjectiveStatus.TODO, ObjectiveStatus.IN_PROGRESS, self.objective.pk),
        )

    def test_completed_at_follows_done_and_only_done(self):
        objective = self.update(status=ObjectiveStatus.DONE)
        self.assertIsNotNone(objective.completed_at)
        objective = self.update(status=ObjectiveStatus.IN_PROGRESS)
        self.assertIsNone(objective.completed_at)

    def test_marking_done_twice_writes_no_second_event(self):
        self.update(status=ObjectiveStatus.DONE)
        before = len(events(self.project))
        self.update(status=ObjectiveStatus.DONE)
        self.assertEqual(len(events(self.project)), before)

    def test_a_due_date_change_is_recorded_as_iso_dates(self):
        self.update(due_on=date(2026, 7, 15))
        event = self.project.events.latest("id")
        self.assertEqual(
            (event.kind, event.from_status, event.to_status),
            (ProjectEventKind.OBJECTIVE_DUE_CHANGED, "2026-06-01", "2026-07-15"),
        )

    def test_reassigning_is_recorded_and_must_stay_inside_the_project(self):
        other = services.add_member(self.project, actor=self.mgr, user=self.outsider)
        objective = self.update(assignee=other)
        self.assertEqual(objective.assignee_id, other.pk)
        event = self.project.events.latest("id")
        self.assertEqual((event.kind, event.note), (ProjectEventKind.OBJECTIVE_ASSIGNED, "بیرونی"))

        elsewhere = new_project(self.mgr, self.s1, "پروژهٔ دیگر")
        foreign = elsewhere.members.get(user=self.mgr)
        with self.assertRaises(ValidationError):
            self.update(assignee=foreign)

    def test_several_changes_in_one_call_write_one_event_each(self):
        self.update(status=ObjectiveStatus.DONE, due_on=date(2026, 8, 1), title="دیگر")
        kinds = events(self.project)[-2:]
        self.assertEqual(set(kinds), {ProjectEventKind.OBJECTIVE_STATUS_CHANGED, ProjectEventKind.OBJECTIVE_DUE_CHANGED})

    def test_an_unknown_field_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            self.update(project=self.project)

    def test_updates_are_refused_on_an_archived_project(self):
        services.archive_project(self.project, actor=self.mgr)
        with self.assertRaises(ConflictError) as caught:
            self.update(title="نباید")
        self.assertEqual(caught.exception.payload["code"], "project_archived")


class ObjectiveRemovalTests(ProjectFixtures, TestCase):
    def setUp(self):
        self.build_world()
        self.project = new_project(self.mgr, self.s1)
        self.mgr_member = self.project.members.get(user=self.mgr)
        self.objective = add_objective(self.project, self.mgr, self.mgr_member, title="برای حذف")

    def test_removal_is_recorded_and_the_title_survives_in_the_feed(self):
        services.remove_objective(self.objective, actor=self.mgr)
        self.assertFalse(Objective.objects.filter(pk=self.objective.pk).exists())
        event = self.project.events.latest("id")
        self.assertEqual((event.kind, event.subject_title, event.objective), (ProjectEventKind.OBJECTIVE_REMOVED, "برای حذف", None))

    def test_removal_is_refused_on_an_archived_project(self):
        services.archive_project(self.project, actor=self.mgr)
        with self.assertRaises(ConflictError) as caught:
            services.remove_objective(self.objective, actor=self.mgr)
        self.assertEqual(caught.exception.payload["code"], "project_archived")
        self.assertTrue(Objective.objects.filter(pk=self.objective.pk).exists())

    def test_a_member_who_still_owns_an_objective_cannot_be_removed(self):
        with self.assertRaises(ConflictError) as caught:
            services.remove_member(self.mgr_member, actor=self.mgr)
        self.assertIn(caught.exception.payload["code"], {"last_manager", "member_has_objectives"})
        # give the project a second manager so the last_manager guard is not what fires
        second = services.add_member(self.project, actor=self.mgr, user=self.member, role=ProjectRole.MANAGER)
        with self.assertRaises(ConflictError) as caught:
            services.remove_member(self.mgr_member, actor=self.mgr)
        self.assertEqual((caught.exception.payload["code"], caught.exception.payload["objectives"]), ("member_has_objectives", 1))

    def test_once_reassigned_the_former_owner_can_be_removed(self):
        second = services.add_member(self.project, actor=self.mgr, user=self.member, role=ProjectRole.MANAGER)
        services.update_objective(self.objective, actor=self.mgr, changes={"assignee": second})
        services.remove_member(self.mgr_member, actor=self.mgr)
        self.assertFalse(self.project.members.filter(user=self.mgr).exists())


class ReorderTests(ProjectFixtures, TestCase):
    def setUp(self):
        self.build_world()
        self.project = new_project(self.mgr, self.s1)
        self.mgr_member = self.project.members.get(user=self.mgr)
        self.a = add_objective(self.project, self.mgr, self.mgr_member, title="الف")
        self.b = add_objective(self.project, self.mgr, self.mgr_member, title="ب")
        self.c = add_objective(self.project, self.mgr, self.mgr_member, title="ج")

    def positions(self):
        return list(self.project.objectives.order_by("position").values_list("title", flat=True))

    def test_reordering_sets_the_new_positions(self):
        services.reorder_objectives(self.project, actor=self.mgr, ordered_ids=[self.c.pk, self.a.pk, self.b.pk])
        self.assertEqual(self.positions(), ["ج", "الف", "ب"])

    def test_a_partial_or_stale_list_is_refused(self):
        for ids in ([self.a.pk, self.b.pk], [self.a.pk, self.b.pk, self.c.pk, 999999], [self.a.pk, self.a.pk, self.b.pk]):
            with self.subTest(ids=ids), self.assertRaises(ConflictError) as caught:
                services.reorder_objectives(self.project, actor=self.mgr, ordered_ids=ids)
            self.assertEqual(caught.exception.payload["code"], "objectives_changed")
        self.assertEqual(self.positions(), ["الف", "ب", "ج"])

    def test_reordering_an_archived_project_is_refused(self):
        services.archive_project(self.project, actor=self.mgr)
        with self.assertRaises(ConflictError) as caught:
            services.reorder_objectives(self.project, actor=self.mgr, ordered_ids=[self.a.pk, self.b.pk, self.c.pk])
        self.assertEqual(caught.exception.payload["code"], "project_archived")


class CreateProjectWithObjectivesTests(ProjectFixtures, TestCase):
    def setUp(self):
        self.build_world()

    def test_objectives_are_created_assigned_to_the_new_members(self):
        project = new_project(
            self.mgr, self.s1,
            members=[{"user": self.member}],
            objectives=[
                {"title": "یک", "assignee": self.mgr, "due_on": date(2026, 5, 1)},
                {"title": "دو", "assignee": self.member, "due_on": date(2026, 6, 1), "weight": 2},
            ],
        )
        rows = list(project.objectives.order_by("position"))
        self.assertEqual([(o.title, o.assignee.user, o.position, o.weight) for o in rows],
                         [("یک", self.mgr, 1, 1), ("دو", self.member, 2, 2)])
        self.assertEqual(events(project).count(ProjectEventKind.OBJECTIVE_ADDED), 2)

    def test_an_objective_assigned_to_a_non_member_rolls_back_the_whole_project(self):
        with self.assertRaises(ValidationError):
            new_project(
                self.mgr, self.s1,
                objectives=[{"title": "بد", "assignee": self.outsider, "due_on": date(2026, 5, 1)}],
            )
        self.assertFalse(Project.objects.exists())
        self.assertFalse(ProjectMember.objects.exists())


class ProgressQueryTests(ProjectFixtures, TestCase):
    def setUp(self):
        self.build_world()
        self.project = new_project(self.mgr, self.s1)
        self.mgr_member = self.project.members.get(user=self.mgr)

    def fetch(self):
        from .queries import with_progress
        return with_progress(Project.objects.filter(pk=self.project.pk)).get()

    def test_a_project_with_no_objectives_has_null_progress(self):
        row = self.fetch()
        self.assertEqual((row.weight_total, row.weight_done, row.objective_count), (0, 0, 0))
        self.assertIsNone(progress_percent(row.weight_done, row.weight_total))

    def test_progress_is_weighted_and_ignores_cancelled_work(self):
        a = add_objective(self.project, self.mgr, self.mgr_member, title="۱", weight=1)
        b = add_objective(self.project, self.mgr, self.mgr_member, title="۲", weight=3)
        c = add_objective(self.project, self.mgr, self.mgr_member, title="۳", weight=5)
        services.update_objective(a, actor=self.mgr, changes={"status": ObjectiveStatus.DONE})
        services.update_objective(c, actor=self.mgr, changes={"status": ObjectiveStatus.CANCELLED})
        row = self.fetch()
        # total counts only live (non-cancelled) weight: a(1) + b(3) = 4; done: a(1)
        self.assertEqual((row.weight_total, row.weight_done), (4, 1))
        self.assertEqual(progress_percent(row.weight_done, row.weight_total), 25)

    def test_overdue_counts_only_open_objectives_past_their_deadline(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        tomorrow = timezone.localdate() + timedelta(days=1)
        late_open = add_objective(self.project, self.mgr, self.mgr_member, title="دیرکرد", due_on=yesterday)
        add_objective(self.project, self.mgr, self.mgr_member, title="به‌موقع", due_on=tomorrow)
        late_done = add_objective(self.project, self.mgr, self.mgr_member, title="دیر ولی انجام‌شده", due_on=yesterday)
        services.update_objective(late_done, actor=self.mgr, changes={"status": ObjectiveStatus.DONE})
        row = self.fetch()
        self.assertEqual(row.overdue_count, 1)


class ObjectiveApiTests(ProjectApiCase):
    def setUp(self):
        super().setUp()
        self.project = new_project(self.mgr, self.s1, members=[{"user": self.member}])
        self.mgr_member = self.project.members.get(user=self.mgr)
        self.member_row = self.project.members.get(user=self.member)
        self.list_url = reverse("project-objectives", args=[self.project.pk])

    def objective_url(self, objective):
        return reverse("project-objective", args=[self.project.pk, objective.pk])

    def post(self, **body):
        body = {"title": "ریزهدف", "assignee": self.member.pk, "due_on": "2026-06-01", **body}
        return self.client.post(self.list_url, body, format="json")

    def test_anyone_who_can_read_the_project_reads_its_objectives_an_outsider_gets_404(self):
        add_objective(self.project, self.mgr, self.member_row)
        for user in (self.mgr, self.member, self.lead_s1, self.lead_d1, self.ceo):
            self.as_(user)
            with self.subTest(user=user.full_name):
                self.assertEqual(self.client.get(self.list_url).status_code, 200)
        self.as_(self.outsider)
        self.assertEqual(self.client.get(self.list_url).status_code, 404)

    def test_only_the_manager_or_a_lead_may_create_an_objective(self):
        for user in (self.mgr, self.lead_s1, self.lead_d1):
            self.as_(user)
            with self.subTest(user=user.full_name):
                self.assertEqual(self.post(title=f"از {user.pk}").status_code, 201)
        self.as_(self.member)
        denied = self.post(title="ممنوع")
        self.assertEqual((denied.status_code, denied.data["detail"]), (403, "شما مدیر این پروژه نیستید."))

    def test_the_assignee_and_due_date_are_required_and_the_assignee_must_be_a_member(self):
        self.as_(self.mgr)
        for body in ({"title": "بی‌مسئول", "due_on": "2026-06-01"}, {"title": "بی‌مهلت", "assignee": self.member.pk},
                     {"title": "بیرونی", "assignee": self.outsider.pk, "due_on": "2026-06-01"}):
            with self.subTest(body=body):
                self.assertEqual(self.client.post(self.list_url, body, format="json").status_code, 400)
        self.assertEqual(self.client.post(self.list_url, {**{"title": "بد وزن", "assignee": self.member.pk, "due_on": "2026-06-01"}, "weight": 0}, format="json").status_code, 400)

    def test_create_returns_the_objective_with_the_viewer_rights(self):
        self.as_(self.mgr)
        response = self.post(weight=2)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            (response.data["assignee"], response.data["assignee_name"], response.data["weight"], response.data["can_edit"], response.data["can_change_status"]),
            (self.member.pk, "عضو پروژه", 2, True, True),
        )

    def test_the_assignee_may_change_only_the_status_not_other_fields(self):
        objective = add_objective(self.project, self.mgr, self.member_row)
        self.as_(self.member)
        ok = self.client.patch(self.objective_url(objective), {"status": "DONE"}, format="json")
        self.assertEqual((ok.status_code, ok.data["status"]), (200, "DONE"))
        denied = self.client.patch(self.objective_url(objective), {"title": "هک"}, format="json")
        self.assertEqual((denied.status_code, denied.data["detail"]), (403, "شما مدیر این پروژه نیستید."))
        combo = self.client.patch(self.objective_url(objective), {"status": "TODO", "title": "هک"}, format="json")
        self.assertEqual(combo.status_code, 403)  # status + another field together needs the manager
        objective.refresh_from_db()
        self.assertEqual(objective.title, "ریزهدف نمونه")

    def test_a_plain_member_who_is_not_the_assignee_cannot_touch_it(self):
        other = person("9800000030")
        join(other, self.s1)
        services.add_member(self.project, actor=self.mgr, user=other)
        objective = add_objective(self.project, self.mgr, self.member_row)
        self.as_(other)
        self.assertEqual(self.client.patch(self.objective_url(objective), {"status": "DONE"}, format="json").status_code, 403)

    def test_the_manager_and_leads_may_edit_everything_including_reassignment(self):
        for user in (self.mgr, self.lead_s1, self.lead_d1):
            objective = add_objective(self.project, self.mgr, self.member_row, title=f"برای {user.pk}")
            self.as_(user)
            response = self.client.patch(self.objective_url(objective), {"title": "ویرایش‌شده", "weight": 4}, format="json")
            self.assertEqual(response.status_code, 200, response.data)

    def test_delete_needs_the_manager_and_the_object_is_gone(self):
        objective = add_objective(self.project, self.mgr, self.member_row)
        self.as_(self.member)
        self.assertEqual(self.client.delete(self.objective_url(objective)).status_code, 403)
        self.as_(self.mgr)
        self.assertEqual(self.client.delete(self.objective_url(objective)).status_code, 204)
        self.assertFalse(Objective.objects.filter(pk=objective.pk).exists())

    def test_reorder_needs_the_manager_and_returns_the_new_order(self):
        a = add_objective(self.project, self.mgr, self.member_row, title="الف")
        b = add_objective(self.project, self.mgr, self.member_row, title="ب")
        reorder_url = reverse("project-reorder", args=[self.project.pk])
        self.as_(self.member)
        self.assertEqual(self.client.post(reorder_url, {"order": [b.pk, a.pk]}, format="json").status_code, 403)
        self.as_(self.mgr)
        ok = self.client.post(reorder_url, {"order": [b.pk, a.pk]}, format="json")
        self.assertEqual([o["title"] for o in ok.data], ["ب", "الف"])

    def test_filters_status_assignee_and_overdue(self):
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        mine = add_objective(self.project, self.mgr, self.member_row, title="من", due_on=yesterday)
        services.update_objective(mine, actor=self.mgr, changes={"status": ObjectiveStatus.IN_PROGRESS})
        add_objective(self.project, self.mgr, self.mgr_member, title="مدیر")
        self.as_(self.member)
        by_status = self.client.get(self.list_url, {"status": "IN_PROGRESS"}).data
        self.assertEqual([o["title"] for o in by_status], ["من"])
        by_me = self.client.get(self.list_url, {"assignee": "me"}).data
        self.assertEqual([o["title"] for o in by_me], ["من"])
        by_id = self.client.get(self.list_url, {"assignee": self.mgr.pk}).data
        self.assertEqual([o["title"] for o in by_id], ["مدیر"])
        overdue = self.client.get(self.list_url, {"overdue": "1"}).data
        self.assertEqual([o["title"] for o in overdue], ["من"])
        self.assertTrue(overdue[0]["is_overdue"])

    def test_the_project_row_carries_progress_and_the_overdue_filter_works(self):
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        objective = add_objective(self.project, self.mgr, self.member_row, weight=2, due_on=yesterday)
        self.as_(self.mgr)
        row = self.client.get(self.detail_url(self.project)).data
        self.assertEqual((row["progress"], row["weight_total"], row["weight_done"], row["objective_count"], row["overdue_count"]),
                         (0, 2, 0, 1, 1))
        services.update_objective(objective, actor=self.mgr, changes={"status": ObjectiveStatus.DONE})
        done_row = self.client.get(self.detail_url(self.project)).data
        self.assertEqual((done_row["progress"], done_row["overdue_count"]), (100, 0))

        overdue_projects = self.client.get(reverse("project-list"), {"overdue": "1"}).data["results"]
        self.assertEqual(overdue_projects, [])  # the objective is DONE now, so nothing is overdue
        other = new_project(self.mgr, self.s2, "پروژهٔ دیگر بخش")
        stale = other.members.get(user=self.mgr)
        add_objective(other, self.mgr, stale, due_on=yesterday)
        self.as_(self.ceo)
        overdue_projects = self.client.get(reverse("project-list"), {"overdue": "1"}).data["results"]
        self.assertEqual([p["name"] for p in overdue_projects], ["پروژهٔ دیگر بخش"])

    def test_an_unknown_objective_or_project_is_a_404(self):
        self.as_(self.mgr)
        missing_objective = self.client.patch(
            reverse("project-objective", args=[self.project.pk, 999999]), {"status": "DONE"}, format="json"
        )
        self.assertEqual(missing_objective.status_code, 404)
        self.assertEqual(self.client.get(reverse("project-objectives", args=[999999])).status_code, 404)


# ---------------------------------------------------------------------------
# Slice 8.3 — the activity feed
# ---------------------------------------------------------------------------


class ActivityLabelTests(ProjectFixtures, TestCase):
    """`from_status`/`to_status` are overloaded by kind; only the two status-carrying kinds get a
    human label — the others (a blank pair, or an ISO-date pair) get none."""

    def setUp(self):
        self.build_world()
        self.project = new_project(self.mgr, self.s1)
        self.mgr_member = self.project.members.get(user=self.mgr)

    def serialize(self, event):
        from .history import ProjectActivitySerializer

        return ProjectActivitySerializer(event).data

    def test_a_project_status_change_carries_project_status_labels(self):
        services.update_project(self.project, actor=self.mgr, changes={"status": ProjectStatus.ON_HOLD})
        row = self.serialize(self.project.events.get(kind=ProjectEventKind.PROJECT_STATUS_CHANGED))
        self.assertEqual((row["from_status"], row["from_status_label"]), (ProjectStatus.ACTIVE, "در حال اجرا"))
        self.assertEqual((row["to_status"], row["to_status_label"]), (ProjectStatus.ON_HOLD, "متوقف"))

    def test_an_objective_status_change_carries_objective_status_labels(self):
        objective = add_objective(self.project, self.mgr, self.mgr_member)
        services.update_objective(objective, actor=self.mgr, changes={"status": ObjectiveStatus.DONE})
        row = self.serialize(self.project.events.get(kind=ProjectEventKind.OBJECTIVE_STATUS_CHANGED))
        self.assertEqual((row["from_status"], row["from_status_label"]), (ObjectiveStatus.TODO, "انجام نشده"))
        self.assertEqual((row["to_status"], row["to_status_label"]), (ObjectiveStatus.DONE, "انجام شد"))

    def test_a_due_date_change_carries_iso_dates_and_no_label(self):
        objective = add_objective(self.project, self.mgr, self.mgr_member, due_on=date(2026, 5, 1))
        services.update_objective(objective, actor=self.mgr, changes={"due_on": date(2026, 6, 1)})
        row = self.serialize(self.project.events.get(kind=ProjectEventKind.OBJECTIVE_DUE_CHANGED))
        self.assertEqual((row["from_status"], row["to_status"]), ("2026-05-01", "2026-06-01"))
        self.assertEqual((row["from_status_label"], row["to_status_label"]), ("", ""))

    def test_a_plain_event_carries_no_status_at_all(self):
        row = self.serialize(self.project.events.get(kind=ProjectEventKind.PROJECT_CREATED))
        self.assertEqual((row["from_status"], row["to_status"], row["from_status_label"], row["to_status_label"]), ("", "", "", ""))

    def test_the_objective_is_null_once_it_is_deleted_and_the_project_is_always_present(self):
        objective = add_objective(self.project, self.mgr, self.mgr_member, title="زودگذر")
        services.remove_objective(objective, actor=self.mgr)
        row = self.serialize(self.project.events.get(kind=ProjectEventKind.OBJECTIVE_REMOVED))
        self.assertIsNone(row["objective"])
        self.assertEqual(row["subject_title"], "زودگذر")
        self.assertEqual(row["project"], {"id": self.project.pk, "name": self.project.name})

    def test_a_live_objective_reference_carries_its_id_and_title(self):
        objective = add_objective(self.project, self.mgr, self.mgr_member, title="پابرجا")
        row = self.serialize(self.project.events.get(kind=ProjectEventKind.OBJECTIVE_ADDED))
        self.assertEqual(row["objective"], {"id": objective.pk, "title": "پابرجا"})


class ProjectActivityApiTests(ProjectApiCase):
    """`GET /projects/{id}/activity/` — one project's own feed."""

    def setUp(self):
        super().setUp()
        self.project = new_project(self.mgr, self.s1, members=[{"user": self.member}])
        self.mgr_member = self.project.members.get(user=self.mgr)
        self.url = reverse("project-activity", args=[self.project.pk])

    def test_it_is_newest_first_and_starts_with_project_created(self):
        self.as_(self.mgr)
        add_objective(self.project, self.mgr, self.mgr_member, title="یک")
        services.update_project(self.project, actor=self.mgr, changes={"status": ProjectStatus.ON_HOLD})
        rows = self.client.get(self.url).data["results"]
        kinds = [r["kind"] for r in rows]
        self.assertEqual(kinds[0], ProjectEventKind.PROJECT_STATUS_CHANGED)  # newest first
        self.assertEqual(kinds[-1], ProjectEventKind.PROJECT_CREATED)

    def test_anyone_who_can_read_the_project_reads_its_feed_an_outsider_and_an_unknown_id_get_404(self):
        for user in (self.mgr, self.member, self.lead_s1, self.lead_d1, self.ceo):
            self.as_(user)
            with self.subTest(user=user.full_name):
                self.assertEqual(self.client.get(self.url).status_code, 200)
        self.as_(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.as_(self.mgr)
        self.assertEqual(self.client.get(reverse("project-activity", args=[999999])).status_code, 404)

    def test_a_lead_of_a_different_branch_gets_404_not_the_wrong_projects_feed(self):
        self.as_(self.lead_d2)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_only_this_projects_events_appear_never_another_projects(self):
        self.as_(self.mgr)
        other = new_project(self.mgr, self.s1, "پروژهٔ دیگر")
        services.update_project(other, actor=self.mgr, changes={"goal": "چیز دیگر"})
        rows = self.client.get(self.url).data["results"]
        self.assertTrue(all(r["project"]["id"] == self.project.pk for r in rows))

    def test_kind_filter_and_an_unknown_kind_matches_nothing(self):
        self.as_(self.mgr)
        add_objective(self.project, self.mgr, self.mgr_member)
        by_kind = self.client.get(self.url, {"kind": ProjectEventKind.OBJECTIVE_ADDED}).data["results"]
        self.assertTrue(all(r["kind"] == ProjectEventKind.OBJECTIVE_ADDED for r in by_kind))
        self.assertNotEqual(len(by_kind), 0)
        nothing = self.client.get(self.url, {"kind": "not_a_real_kind"}).data["results"]
        self.assertEqual(nothing, [])

    def test_objective_filter_narrows_to_one_objectives_history(self):
        self.as_(self.mgr)
        a = add_objective(self.project, self.mgr, self.mgr_member, title="الف")
        b = add_objective(self.project, self.mgr, self.mgr_member, title="ب")
        services.update_objective(a, actor=self.mgr, changes={"status": ObjectiveStatus.DONE})
        rows = self.client.get(self.url, {"objective": a.pk}).data["results"]
        self.assertTrue(all(r["objective"]["id"] == a.pk for r in rows))
        self.assertGreaterEqual(len(rows), 2)  # objective_added + objective_status_changed
        self.assertEqual(self.client.get(self.url, {"objective": "x"}).data["results"], [])

    def test_actor_filter_matches_the_snapshotted_name(self):
        self.as_(self.mgr)
        services.add_member(self.project, actor=self.mgr, user=self.outsider)
        services.update_project(self.project, actor=self.mgr, changes={"goal": "چیزی"})
        rows = self.client.get(self.url, {"actor": "مدیر"}).data["results"]
        self.assertTrue(all("مدیر" in r["actor_name"] for r in rows))
        self.assertNotEqual(len(rows), 0)

    def test_actor_filter_normalises_the_query_letterform(self):
        # The actor name is stored raw (the snapshot), typed here with a Persian yeh; searching with
        # the Arabic yeh only matches if the query is letterform-normalised before the icontains.
        # update_project only records an event on a *status* change (services.py) — goal/name edits
        # are silent — so use add_member, which always writes one.
        writer = person("9800000040", "علی رضایی")
        services.add_member(self.project, actor=writer, user=self.outsider)
        self.as_(self.mgr)
        rows = self.client.get(self.url, {"actor": "رضايي"}).data["results"]  # Arabic yeh
        self.assertTrue(any(r["actor_name"] == "علی رضایی" for r in rows))

    def test_days_filter(self):
        self.as_(self.mgr)
        old = ProjectEvent.objects.create(
            project=self.project, kind=ProjectEventKind.COMMENT_ADDED, actor=self.mgr,
            actor_name="قدیمی", note="خیلی وقت پیش",
        )
        ProjectEvent.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=40))
        within_range = self.client.get(self.url, {"days": "7"}).data["results"]
        self.assertFalse(any(r["id"] == old.pk for r in within_range))
        everything = self.client.get(self.url, {"days": "9999"}).data["results"]
        self.assertTrue(any(r["id"] == old.pk for r in everything))
        self.assertEqual(self.client.get(self.url, {"days": "0"}).data["results"], [])
        self.assertEqual(self.client.get(self.url, {"days": "not-a-number"}).data["results"], [])

    def test_anonymous_gets_401(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)


class AllProjectsActivityApiTests(ProjectApiCase):
    """`GET /projects/activity/` — the feed across every project the caller may read."""

    def setUp(self):
        super().setUp()
        self.url = reverse("projects-activity")
        self.mine = new_project(self.mgr, self.s1, "پروژهٔ بخش یک", members=[{"user": self.member}])
        self.theirs = new_project(self.hq, self.s2, "پروژهٔ بخش دو")

    def kinds(self, **params):
        return [r["kind"] for r in self.client.get(self.url, params).data["results"]]

    def project_names(self, **params):
        return sorted({r["project"]["name"] for r in self.client.get(self.url, params).data["results"]})

    def test_a_member_sees_only_events_from_projects_they_can_read(self):
        self.as_(self.member)
        self.assertEqual(self.project_names(), ["پروژهٔ بخش یک"])
        self.as_(self.hq)
        self.assertEqual(self.project_names(), ["پروژهٔ بخش دو"])

    def test_a_lead_sees_their_whole_subtree_and_manage_organization_sees_everything(self):
        self.as_(self.lead_d1)
        self.assertEqual(self.project_names(), ["پروژهٔ بخش یک"])
        self.as_(self.ceo)
        self.assertEqual(self.project_names(), ["پروژهٔ بخش دو", "پروژهٔ بخش یک"])

    def test_an_outsider_sees_nothing(self):
        self.as_(self.outsider)
        self.assertEqual(self.client.get(self.url).data["results"], [])

    def test_newest_first_across_projects(self):
        services.update_project(self.mine, actor=self.mgr, changes={"status": ProjectStatus.ON_HOLD})
        self.as_(self.ceo)
        rows = self.client.get(self.url).data["results"]
        self.assertEqual(rows[0]["kind"], ProjectEventKind.PROJECT_STATUS_CHANGED)
        created_at = [r["created_at"] for r in rows]
        self.assertEqual(created_at, sorted(created_at, reverse=True))

    def test_the_project_filter_narrows_and_an_invisible_id_yields_nothing_not_a_403(self):
        self.as_(self.ceo)
        self.assertEqual(self.project_names(project=self.mine.pk), ["پروژهٔ بخش یک"])
        self.as_(self.member)  # cannot read پروژهٔ بخش دو
        self.assertEqual(self.kinds(project=self.theirs.pk), [])
        self.assertEqual(self.kinds(project="not-a-number"), [])

    def test_q_searches_the_project_name_letterform_insensitively(self):
        third = new_project(self.mgr, self.s1, "طرح ي ویژه")  # Arabic yeh in the stored name's raw input
        self.as_(self.ceo)
        self.assertIn("طرح ی ویژه", self.project_names(q="طرح ي"))  # typed with Arabic yeh
        self.assertIn("طرح ی ویژه", self.project_names(q="طرح ی"))  # typed with Persian yeh
        self.assertEqual(self.project_names(q="نامعلوم"), [])

    def test_kind_actor_objective_and_days_filters_apply_here_too(self):
        mgr_member = self.mine.members.get(user=self.mgr)
        objective = add_objective(self.mine, self.mgr, mgr_member, title="ریزهدف")
        self.as_(self.ceo)
        self.assertEqual(self.kinds(kind="not_a_real_kind"), [])
        by_objective = self.client.get(self.url, {"objective": objective.pk}).data["results"]
        self.assertTrue(all(r["objective"]["id"] == objective.pk for r in by_objective))
        by_actor = self.client.get(self.url, {"actor": "مدیر پروژه"}).data["results"]
        self.assertTrue(all("مدیر پروژه" in r["actor_name"] for r in by_actor))

    def test_anonymous_gets_401(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)


# ---------------------------------------------------------------------------
# Slice 8.4 — comments and linked documents
# ---------------------------------------------------------------------------


def make_document(author, title="سند نمونه", group="FORM", category="INSIDE"):
    from apps.documents import services as document_services

    return document_services.create_document(user=author, category=category, title=title, group=group)


class CommentServiceTests(ProjectFixtures, TestCase):
    def setUp(self):
        self.build_world()
        self.project = new_project(self.mgr, self.s1, members=[{"user": self.member}])
        self.mgr_member = self.project.members.get(user=self.mgr)

    def test_a_comment_is_recorded_with_a_snapshot_and_an_event(self):
        comment = services.add_comment(self.project, actor=self.mgr, body="  یادداشت اول  ")
        self.assertEqual((comment.body, comment.author, comment.author_name, comment.author_title, comment.objective),
                         ("یادداشت اول", self.mgr, "مدیر پروژه", "کارمند/اپراتور", None))
        event = self.project.events.latest("id")
        self.assertEqual((event.kind, event.subject_title, event.note), (ProjectEventKind.COMMENT_ADDED, self.project.name, "یادداشت اول"))

    def test_a_comment_may_be_attached_to_one_of_the_projects_own_objectives(self):
        objective = add_objective(self.project, self.mgr, self.mgr_member, title="هدف")
        comment = services.add_comment(self.project, actor=self.mgr, body="روی این کار کنید", objective=objective)
        self.assertEqual(comment.objective, objective)
        event = self.project.events.latest("id")
        self.assertEqual((event.objective_id, event.subject_title), (objective.pk, "هدف"))

    def test_an_objective_from_another_project_is_refused(self):
        other = new_project(self.mgr, self.s1, "پروژهٔ دیگر")
        foreign = add_objective(other, self.mgr, other.members.get(user=self.mgr))
        with self.assertRaises(ValidationError) as caught:
            services.add_comment(self.project, actor=self.mgr, body="نامعتبر", objective=foreign)
        self.assertIn("objective", caught.exception.detail)
        self.assertFalse(ProjectComment.objects.exists())

    def test_a_blank_or_too_long_comment_is_refused(self):
        with self.assertRaises(ValidationError):
            services.add_comment(self.project, actor=self.mgr, body="   ")
        with self.assertRaises(ValidationError):
            services.add_comment(self.project, actor=self.mgr, body="خ" * (COMMENT_MAX_LENGTH + 1))
        self.assertFalse(ProjectComment.objects.exists())

    def test_comments_are_refused_on_an_archived_project(self):
        services.archive_project(self.project, actor=self.mgr)
        with self.assertRaises(ConflictError) as caught:
            services.add_comment(self.project, actor=self.mgr, body="نباید ثبت شود")
        self.assertEqual(caught.exception.payload["code"], "project_archived")

    def test_removal_is_recorded_and_preserves_the_subject(self):
        objective = add_objective(self.project, self.mgr, self.mgr_member, title="هدف حذف‌شده")
        comment = services.add_comment(self.project, actor=self.member, body="نظر", objective=objective)
        services.remove_comment(comment, actor=self.member)
        self.assertFalse(ProjectComment.objects.filter(pk=comment.pk).exists())
        event = self.project.events.latest("id")
        self.assertEqual((event.kind, event.subject_title), (ProjectEventKind.COMMENT_REMOVED, "هدف حذف‌شده"))

    def test_removal_is_refused_on_an_archived_project(self):
        comment = services.add_comment(self.project, actor=self.mgr, body="نظر")
        services.archive_project(self.project, actor=self.mgr)
        with self.assertRaises(ConflictError) as caught:
            services.remove_comment(comment, actor=self.mgr)
        self.assertEqual(caught.exception.payload["code"], "project_archived")

    def test_the_actor_is_snapshotted_and_survives_a_rename(self):
        services.add_comment(self.project, actor=self.mgr, body="پیش از تغییر نام")
        self.mgr.full_name = "نام تازه"
        self.mgr.save()
        comment = self.project.comments.latest("id")
        self.assertEqual(comment.author_name, "مدیر پروژه")


class DocumentLinkServiceTests(ProjectFixtures, TestCase):
    def setUp(self):
        self.build_world()
        self.project = new_project(self.mgr, self.s1)
        self.document = make_document(self.mgr, title="سند یک")

    def test_linking_is_recorded_by_the_documents_printed_code(self):
        link = services.link_document(self.project, actor=self.mgr, document=self.document, caption="  گزارش نهایی  ")
        self.assertEqual((link.document, link.caption, link.linked_by), (self.document, "گزارش نهایی", self.mgr))
        event = self.project.events.latest("id")
        self.assertEqual((event.kind, event.subject_title, event.note),
                         (ProjectEventKind.DOCUMENT_LINKED, self.document.full_code, "گزارش نهایی"))

    def test_the_same_document_cannot_be_linked_twice(self):
        first = services.link_document(self.project, actor=self.mgr, document=self.document)
        with self.assertRaises(ConflictError) as caught:
            services.link_document(self.project, actor=self.mgr, document=self.document)
        self.assertEqual((caught.exception.payload["code"], caught.exception.payload["existing_id"]), ("already_linked", first.pk))

    def test_the_database_refuses_a_duplicate_link_independently_of_the_service(self):
        """The service's own pre-check (above) is a nicety for a clean 409; this is the net."""
        ProjectDocumentLink.objects.create(project=self.project, document=self.document)
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            ProjectDocumentLink.objects.create(project=self.project, document=self.document)
        self.assertIn("uniq_project_document_link", str(caught.exception))

    def test_a_different_project_may_link_the_same_document(self):
        other = new_project(self.mgr, self.s1, "پروژهٔ دیگر")
        services.link_document(self.project, actor=self.mgr, document=self.document)
        services.link_document(other, actor=self.mgr, document=self.document)
        self.assertEqual(ProjectDocumentLink.objects.filter(document=self.document).count(), 2)

    def test_linking_is_refused_on_an_archived_project(self):
        services.archive_project(self.project, actor=self.mgr)
        with self.assertRaises(ConflictError) as caught:
            services.link_document(self.project, actor=self.mgr, document=self.document)
        self.assertEqual(caught.exception.payload["code"], "project_archived")

    def test_unlinking_is_recorded_and_the_link_is_gone(self):
        link = services.link_document(self.project, actor=self.mgr, document=self.document)
        services.unlink_document(link, actor=self.mgr)
        self.assertFalse(ProjectDocumentLink.objects.filter(pk=link.pk).exists())
        event = self.project.events.latest("id")
        self.assertEqual((event.kind, event.subject_title), (ProjectEventKind.DOCUMENT_UNLINKED, self.document.full_code))

    def test_unlinking_is_refused_on_an_archived_project(self):
        link = services.link_document(self.project, actor=self.mgr, document=self.document)
        services.archive_project(self.project, actor=self.mgr)
        with self.assertRaises(ConflictError) as caught:
            services.unlink_document(link, actor=self.mgr)
        self.assertEqual(caught.exception.payload["code"], "project_archived")

    def test_deleting_the_document_is_protected_while_linked(self):
        services.link_document(self.project, actor=self.mgr, document=self.document)
        with self.assertRaises(ProtectedError):
            self.document.delete()


class CommentApiTests(ProjectApiCase):
    def setUp(self):
        super().setUp()
        self.project = new_project(self.mgr, self.s1, members=[{"user": self.member}])
        self.list_url = reverse("project-comments", args=[self.project.pk])

    def detail_url_by_id(self, comment_id):
        return reverse("project-comment", args=[self.project.pk, comment_id])

    def test_anyone_who_can_read_the_project_may_read_and_post_an_outsider_gets_404(self):
        for user in (self.mgr, self.member, self.lead_s1, self.lead_d1, self.ceo):
            self.as_(user)
            with self.subTest(user=user.full_name):
                self.assertEqual(self.client.get(self.list_url).status_code, 200)
                response = self.client.post(self.list_url, {"body": f"از {user.pk}"}, format="json")
                self.assertEqual(response.status_code, 201, response.data)
        self.as_(self.outsider)
        self.assertEqual(self.client.get(self.list_url).status_code, 404)
        self.assertEqual(self.client.post(self.list_url, {"body": "ممنوع"}, format="json").status_code, 404)

    def test_a_plain_member_may_comment_though_they_cannot_edit_the_project(self):
        self.as_(self.member)
        response = self.client.post(self.list_url, {"body": "نظر من"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual((response.data["author"], response.data["author_name"], response.data["can_delete"]),
                         (self.member.pk, "عضو پروژه", True))

    def test_a_blank_body_is_a_400(self):
        self.as_(self.mgr)
        self.assertEqual(self.client.post(self.list_url, {"body": "  "}, format="json").status_code, 400)
        self.assertEqual(self.client.post(self.list_url, {}, format="json").status_code, 400)

    def test_only_the_author_may_delete_their_own_comment(self):
        self.as_(self.mgr)
        comment = self.client.post(self.list_url, {"body": "نظر مدیر"}, format="json").data
        self.as_(self.member)
        denied = self.client.delete(self.detail_url_by_id(comment["id"]))
        self.assertEqual(denied.status_code, 403)
        self.as_(self.mgr)
        self.assertEqual(self.client.delete(self.detail_url_by_id(comment["id"])).status_code, 204)

    def test_not_even_a_lead_or_manage_organization_may_delete_someone_elses_comment(self):
        self.as_(self.member)
        comment_id = self.client.post(self.list_url, {"body": "نظر عضو"}, format="json").data["id"]
        for user in (self.mgr, self.lead_s1, self.lead_d1, self.ceo):
            self.as_(user)
            with self.subTest(user=user.full_name):
                self.assertEqual(self.client.delete(self.detail_url_by_id(comment_id)).status_code, 403)
        self.assertTrue(ProjectComment.objects.filter(pk=comment_id).exists())

    def test_the_can_delete_flag_matches_the_enforcement(self):
        self.as_(self.mgr)
        comment = self.client.post(self.list_url, {"body": "نظر مدیر"}, format="json").data
        self.assertTrue(comment["can_delete"])
        self.as_(self.member)
        seen = self.client.get(self.list_url).data["results"][0]
        self.assertFalse(seen["can_delete"])

    def test_comments_can_target_one_objective(self):
        self.as_(self.mgr)
        mgr_member = self.project.members.get(user=self.mgr)
        objective = add_objective(self.project, self.mgr, mgr_member)
        response = self.client.post(self.list_url, {"body": "روی این کار کنید", "objective": objective.pk}, format="json")
        self.assertEqual(response.data["objective"], objective.pk)

    def test_the_list_is_paginated_newest_first(self):
        self.as_(self.mgr)
        for i in range(3):
            self.client.post(self.list_url, {"body": f"نظر {i}"}, format="json")
        body = self.client.get(self.list_url).data
        self.assertIn("count", body)
        self.assertEqual([r["body"] for r in body["results"]], ["نظر 2", "نظر 1", "نظر 0"])

    def test_an_unknown_comment_is_a_404(self):
        self.as_(self.mgr)
        self.assertEqual(self.client.delete(self.detail_url_by_id(999999)).status_code, 404)

    def test_anonymous_gets_401(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.list_url).status_code, 401)


class DocumentLinkApiTests(ProjectApiCase):
    def setUp(self):
        super().setUp()
        self.project = new_project(self.mgr, self.s1, members=[{"user": self.member}])
        self.document = make_document(self.mgr, title="سند آزمایشی")
        self.list_url = reverse("project-documents", args=[self.project.pk])

    def link_url(self, link_id):
        return reverse("project-document-link", args=[self.project.pk, link_id])

    def test_the_manager_and_leads_may_link_a_document_a_plain_member_may_not(self):
        for user, document in ((self.mgr, self.document), (self.lead_s1, make_document(self.mgr, "سند دو")), (self.lead_d1, make_document(self.mgr, "سند سه"))):
            self.as_(user)
            with self.subTest(user=user.full_name):
                response = self.client.post(self.list_url, {"document": document.pk}, format="json")
                self.assertEqual(response.status_code, 201, response.data)
        self.as_(self.member)
        denied = self.client.post(self.list_url, {"document": make_document(self.mgr, "سند چهار").pk}, format="json")
        self.assertEqual(denied.status_code, 403)

    def test_reading_the_list_needs_only_project_read_access(self):
        self.as_(self.mgr)
        self.client.post(self.list_url, {"document": self.document.pk, "caption": "سند اصلی"}, format="json")
        for user in (self.mgr, self.member, self.lead_s1, self.ceo):
            self.as_(user)
            rows = self.client.get(self.list_url).data
            self.assertEqual([r["document_full_code"] for r in rows], [self.document.full_code])
            self.assertEqual(rows[0]["caption"], "سند اصلی")
        self.as_(self.outsider)
        self.assertEqual(self.client.get(self.list_url).status_code, 404)

    def test_linking_the_same_document_twice_is_a_409(self):
        self.as_(self.mgr)
        self.client.post(self.list_url, {"document": self.document.pk}, format="json")
        again = self.client.post(self.list_url, {"document": self.document.pk}, format="json")
        self.assertEqual((again.status_code, again.data["code"]), (409, "already_linked"))

    def test_an_unknown_document_id_is_a_400(self):
        self.as_(self.mgr)
        self.assertEqual(self.client.post(self.list_url, {"document": 999999999}, format="json").status_code, 400)

    def test_unlink_needs_the_manager_too(self):
        self.as_(self.mgr)
        link_id = self.client.post(self.list_url, {"document": self.document.pk}, format="json").data["id"]
        self.as_(self.member)
        self.assertEqual(self.client.delete(self.link_url(link_id)).status_code, 403)
        self.as_(self.mgr)
        self.assertEqual(self.client.delete(self.link_url(link_id)).status_code, 204)
        self.assertFalse(ProjectDocumentLink.objects.filter(pk=link_id).exists())

    def test_an_unknown_link_is_a_404(self):
        self.as_(self.mgr)
        self.assertEqual(self.client.delete(self.link_url(999999)).status_code, 404)

    def test_anonymous_gets_401(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.list_url).status_code, 401)


class CommentAndLinkActivityApiTests(ProjectApiCase):
    """The feed (8.3) picks up the two new kinds without any changes of its own."""

    def test_comment_and_document_events_appear_in_both_feeds(self):
        project = new_project(self.mgr, self.s1)
        document = make_document(self.mgr, title="سند فعالیت")
        services.add_comment(project, actor=self.mgr, body="یادداشت")
        services.link_document(project, actor=self.mgr, document=document)
        self.as_(self.mgr)
        per_project = self.client.get(reverse("project-activity", args=[project.pk])).data["results"]
        kinds = {r["kind"] for r in per_project}
        self.assertTrue({ProjectEventKind.COMMENT_ADDED, ProjectEventKind.DOCUMENT_LINKED} <= kinds)
        cross_project = self.client.get(reverse("projects-activity"), {"project": project.pk}).data["results"]
        self.assertTrue({ProjectEventKind.COMMENT_ADDED, ProjectEventKind.DOCUMENT_LINKED} <= {r["kind"] for r in cross_project})
