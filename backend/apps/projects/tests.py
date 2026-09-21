"""Slice 8.1: projects, their members and their activity events."""
from datetime import date
from unittest import mock

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse

from apps.accounts.models import AccessLevel, AccessRoll, Capability, User
from apps.core.exceptions import ConflictError
from apps.organization import memberships, tree
from apps.organization.tests import SampleTree, Threaded, add, join, person
from apps.organization.tests import ApiTestCase as OrgApiTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import services
from .models import Project, ProjectEvent, ProjectEventKind, ProjectMember, ProjectRole, ProjectStatus


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
