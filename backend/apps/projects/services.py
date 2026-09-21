"""Project rules — the one place that writes Project, ProjectMember and ProjectEvent.

Every mutation records its ProjectEvent **in the same transaction**, by an explicit call here and
never by a signal (signals in this project invalidate caches; they do not write audit trails), so
the feed can never disagree with the data, and a rolled-back change leaves no event behind.

Who may do what is decided in access.py and checked by the views. Two rules live here because they
need the row lock taken here: a project always keeps at least one مدیر پروژه, and an archived project
is read-only (un-archive it first).
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.core.exceptions import ConflictError
from apps.core.text import normalize_search_term, normalize_title
from apps.organization.models import Membership, OrgNodeKind
from apps.organization.tree import lock_node

from .models import Project, ProjectEvent, ProjectEventKind, ProjectMember, ProjectRole

User = get_user_model()

#: Sentinel for "the request did not mention this field" (None is a real value for a date).
UNSET = object()

#: Fields update_project accepts.
UPDATABLE = ("name", "goal", "starts_on", "due_on", "status")


def record_event(project: Project, kind: str, actor, **extra) -> ProjectEvent:
    """One line of the feed. Actor name and سمت are snapshotted as text."""
    return ProjectEvent.objects.create(
        project=project,
        kind=kind,
        actor=actor,
        actor_name=actor.full_name if actor else "",
        actor_title=actor.title if actor else "",
        **extra,
    )


def _lock_project(pk: int) -> Project:
    try:
        return Project.objects.select_for_update().select_related("section").get(pk=pk)
    except Project.DoesNotExist:
        raise NotFound("پروژه یافت نشد.")


def require_writable(project: Project) -> None:
    if project.is_archived:
        raise ConflictError(
            "این پروژه بایگانی شده و فقط‌خواندنی است. ابتدا آن را از بایگانی خارج کنید.",
            code="project_archived",
        )


def _clean_name(name: str) -> tuple[str, str]:
    name = normalize_title(name or "")
    if not name:
        raise ValidationError({"name": ["نام پروژه نمی‌تواند خالی باشد."]})
    return name, normalize_search_term(name)


def _check_dates(starts_on, due_on) -> None:
    if starts_on and due_on and due_on < starts_on:
        raise ValidationError({"due_on": ["مهلت پروژه نمی‌تواند پیش از تاریخ شروع آن باشد."]})


def _check_name_free(section_id: int, name_key: str, *, exclude_pk: int | None = None) -> None:
    clashes = Project.objects.filter(section_id=section_id, name_key=name_key)
    if exclude_pk is not None:
        clashes = clashes.exclude(pk=exclude_pk)
    clash = clashes.first()
    if clash is not None:
        raise ConflictError(
            "در این بخش پروژه‌ای با همین نام وجود دارد.", code="duplicate_name", existing_id=clash.pk
        )


# --------------------------------------------------------------------------
# Members
# --------------------------------------------------------------------------


def _add_member(project: Project, user, role: str, *, added_by, announce: bool = True) -> ProjectMember:
    if not user.is_active:
        raise ConflictError(
            "این شخص غیرفعال است و نمی‌توان او را به پروژه افزود.", code="user_inactive", user_id=user.pk
        )
    if project.members.count() >= settings.PROJECT_MAX_MEMBERS:
        raise ConflictError(
            f"یک پروژه حداکثر {settings.PROJECT_MAX_MEMBERS} عضو می‌تواند داشته باشد.", code="member_limit"
        )
    existing = project.members.filter(user=user).first()
    if existing is not None:
        raise ConflictError("این شخص از قبل عضو پروژه است.", code="already_member", existing_id=existing.pk)

    # Stored once, now: is the person in the project's بخش? (Not "is_guest = has a different بخش".)
    is_guest = not Membership.objects.filter(user=user, node_id=project.section_id).exists()
    member = ProjectMember.objects.create(
        project=project, user=user, role=role, is_guest=is_guest, added_by=added_by
    )
    if announce:
        record_event(
            project,
            ProjectEventKind.GUEST_INVITED if is_guest else ProjectEventKind.MEMBER_ADDED,
            added_by,
            subject_title=user.full_name,
            note=ProjectRole(role).label,
        )
    return member


@transaction.atomic
def add_member(project: Project, *, actor, user, role: str = ProjectRole.MEMBER) -> ProjectMember:
    project = _lock_project(project.pk)
    require_writable(project)
    return _add_member(project, user, role, added_by=actor)


def _other_managers(project: Project, member: ProjectMember) -> bool:
    return project.members.filter(role=ProjectRole.MANAGER).exclude(pk=member.pk).exists()


@transaction.atomic
def change_role(member: ProjectMember, *, actor, role: str) -> ProjectMember:
    project = _lock_project(member.project_id)
    require_writable(project)
    try:
        member = ProjectMember.objects.select_related("user").get(pk=member.pk, project=project)
    except ProjectMember.DoesNotExist:
        raise NotFound("عضو یافت نشد.")
    if member.role == role:
        return member
    if member.role == ProjectRole.MANAGER and not _other_managers(project, member):
        raise ConflictError(
            "هر پروژه باید دست‌کم یک مدیر داشته باشد. ابتدا مدیر دیگری تعیین کنید.", code="last_manager"
        )
    member.role = role
    member.save(update_fields=["role", "updated_at"])
    record_event(
        project, ProjectEventKind.MEMBER_ROLE_CHANGED, actor,
        subject_title=member.user.full_name, note=ProjectRole(role).label,
    )
    return member


@transaction.atomic
def remove_member(member: ProjectMember, *, actor) -> None:
    project = _lock_project(member.project_id)
    require_writable(project)
    try:
        member = ProjectMember.objects.select_related("user").get(pk=member.pk, project=project)
    except ProjectMember.DoesNotExist:
        raise NotFound("عضو یافت نشد.")
    if member.role == ProjectRole.MANAGER and not _other_managers(project, member):
        raise ConflictError(
            "هر پروژه باید دست‌کم یک مدیر داشته باشد. ابتدا مدیر دیگری تعیین کنید.", code="last_manager"
        )
    name = member.user.full_name
    member.delete()
    record_event(project, ProjectEventKind.MEMBER_REMOVED, actor, subject_title=name)


# --------------------------------------------------------------------------
# The project itself
# --------------------------------------------------------------------------


@transaction.atomic
def create_project(
    *, actor, section, name: str, goal: str = "", starts_on=None, due_on=None, members=()
) -> Project:
    """Create a project in a بخش. The creator is added as its مدیر پروژه automatically (as a guest if
    they are not in that بخش), so there is a manager from the first moment and the creator can
    always see what they made. `members` are `{"user": User, "role": …}`; the creator, if listed, is
    a manager regardless of the role given."""
    section = lock_node(section.pk)
    if section.kind != OrgNodeKind.SECTION:
        raise ValidationError({"section": ["پروژه فقط در یک بخش ساخته می‌شود."]})
    if not section.is_active:
        raise ConflictError(
            "به بخش بایگانی‌شده نمی‌توان پروژه افزود.", code="section_archived", section_id=section.pk
        )
    name, key = _clean_name(name)
    _check_dates(starts_on, due_on)
    _check_name_free(section.pk, key)

    project = Project.objects.create(
        section=section, name=name, name_key=key, goal=(goal or "").strip(),
        starts_on=starts_on, due_on=due_on, created_by=actor,
    )
    record_event(project, ProjectEventKind.PROJECT_CREATED, actor, subject_title=project.name)

    _add_member(project, actor, ProjectRole.MANAGER, added_by=actor, announce=False)
    seen = {actor.pk}
    for entry in members:
        user = entry["user"]
        if user.pk in seen:
            continue
        seen.add(user.pk)
        _add_member(project, user, entry.get("role", ProjectRole.MEMBER), added_by=actor)
    return project


@transaction.atomic
def update_project(project: Project, *, actor, changes: dict) -> Project:
    """Apply any subset of `UPDATABLE`. A status change is the only one written to the feed (the
    others are edits, not events)."""
    project = _lock_project(project.pk)
    require_writable(project)
    unknown = set(changes) - set(UPDATABLE)
    if unknown:
        raise ValueError(f"not updatable: {sorted(unknown)}")

    previous_status = project.status
    if "name" in changes:
        project.name, project.name_key = _clean_name(changes["name"])
        _check_name_free(project.section_id, project.name_key, exclude_pk=project.pk)
    if "goal" in changes:
        project.goal = (changes["goal"] or "").strip()
    if "starts_on" in changes:
        project.starts_on = changes["starts_on"]
    if "due_on" in changes:
        project.due_on = changes["due_on"]
    if "status" in changes:
        project.status = changes["status"]
    _check_dates(project.starts_on, project.due_on)

    project.save(update_fields=[*changes.keys(), *(["name_key"] if "name" in changes else []), "updated_at"])
    if project.status != previous_status:
        record_event(
            project, ProjectEventKind.PROJECT_STATUS_CHANGED, actor,
            from_status=previous_status, to_status=project.status,
        )
    return project


@transaction.atomic
def archive_project(project: Project, *, actor) -> Project:
    project = _lock_project(project.pk)
    if project.is_archived:
        return project
    project.archived_at = timezone.now()
    project.save(update_fields=["archived_at", "updated_at"])
    record_event(project, ProjectEventKind.PROJECT_ARCHIVED, actor)
    return project


@transaction.atomic
def unarchive_project(project: Project, *, actor) -> Project:
    project = _lock_project(project.pk)
    if not project.is_archived:
        return project
    if not project.section.is_active:
        raise ConflictError(
            "بخش این پروژه بایگانی شده است. ابتدا آن را از بایگانی خارج کنید.", code="section_archived"
        )
    project.archived_at = None
    project.save(update_fields=["archived_at", "updated_at"])
    record_event(project, ProjectEventKind.PROJECT_UNARCHIVED, actor)
    return project
