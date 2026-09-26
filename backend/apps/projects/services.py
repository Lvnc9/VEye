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
from django.db.models import Count
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.core.exceptions import ConflictError
from apps.core.text import normalize_search_term, normalize_title
from apps.organization.models import Membership, OrgNodeKind
from apps.organization.tree import lock_node

from .models import (
    MeetingAttendee,
    Objective,
    ObjectiveAssignee,
    ObjectiveStatus,
    ObjectiveUpdate,
    Project,
    ProjectComment,
    ProjectDocumentLink,
    ProjectDraft,
    ProjectEvent,
    ProjectEventKind,
    ProjectMeeting,
    ProjectMember,
    ProjectRole,
)

#: A comment is a note, not a document; bounded generously so the feed stays a feed.
COMMENT_MAX_LENGTH = 4000
#: How much of a comment's body a feed row previews. The comment row itself (never edited) is the
#: source of truth; this is a cheap, never-stale snippet, not a second copy of the data.
COMMENT_PREVIEW_LENGTH = 160
#: A progress entry is a log line, not a report; the same bound as a comment.
OBJECTIVE_UPDATE_MAX_LENGTH = 4000

User = get_user_model()

#: Sentinel for "the request did not mention this field" (None is a real value for a date).
UNSET = object()

#: Fields update_project accepts.
UPDATABLE = ("name", "goal", "starts_on", "due_on", "status")
#: Fields update_objective accepts. Only `status` may be changed by an assignee (views.py).
OBJECTIVE_UPDATABLE = ("title", "description", "assignees", "due_on", "status", "weight")
#: Fields update_meeting accepts.
MEETING_UPDATABLE = ("title", "held_on", "start_time", "location", "description", "attendees")
#: Changing any of these clears every acknowledgement: people saw a different meeting (ADR-010).
MEETING_WHEN_WHERE = ("held_on", "start_time", "location")


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
    # A 409 only when removing them would leave some objective with zero assignees — being one of
    # several assignees is fine, the others keep it staffed. The base queryset is this member's own
    # rows (a plain field filter, no join yet), so the annotate's own join to the objective's full
    # assignee list is independent of it and counts every assignee, not just this one
    # (filtering and Count()-ing the *same* relation in one query would silently restrict the count
    # to the filtered join instead).
    sole_owned = (
        ObjectiveAssignee.objects.filter(member=member)
        .annotate(assignee_count=Count("objective__assignees"))
        .filter(assignee_count=1)
        .count()
    )
    if sole_owned:
        raise ConflictError(
            "این عضو تنها مسئول یک یا چند ریزهدف است. ابتدا آن‌ها را به عضو دیگری واگذار کنید.",
            code="member_has_objectives",
            objectives=sole_owned,
        )
    member.objective_assignments.all().delete()
    name = member.user.full_name
    member.delete()
    record_event(project, ProjectEventKind.MEMBER_REMOVED, actor, subject_title=name)


# --------------------------------------------------------------------------
# The project itself
# --------------------------------------------------------------------------


@transaction.atomic
def create_project(
    *, actor, section, name: str, goal: str = "", starts_on=None, due_on=None, members=(), objectives=()
) -> Project:
    """Create a project in a بخش. The creator is added as its مدیر پروژه automatically (as a guest if
    they are not in that بخش), so there is a manager from the first moment and the creator can
    always see what they made. `members` are `{"user": User, "role": …}`; the creator, if listed, is
    a manager regardless of the role given. `objectives` are `{"title", "description", "assignee": User,
    "due_on", "weight"}`, each assigned to someone who is on the project once the members are in — a
    half-created project (some members, no plan) cannot exist, because it is all one transaction."""
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

    for index, entry in enumerate(objectives):
        try:
            assignee_members = [project.members.get(user=user) for user in entry["assignees"]]
        except ProjectMember.DoesNotExist:
            raise ValidationError(
                {"objectives": {index: {"assignees": ["مسئول ریزهدف باید یکی از اعضای پروژه باشد."]}}}
            )
        _add_objective(
            project, actor, assignees=assignee_members, **{k: v for k, v in entry.items() if k != "assignees"}
        )
    # The creator's half-typed draft has become this project (ADR-010). Same transaction: a create
    # that fails keeps the draft.
    ProjectDraft.objects.filter(user=actor).delete()
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


# --------------------------------------------------------------------------
# Objectives
# --------------------------------------------------------------------------


def _clean_title(title: str) -> str:
    title = normalize_title(title or "")
    if not title:
        raise ValidationError({"title": ["عنوان ریزهدف نمی‌تواند خالی باشد."]})
    return title


def _dedupe_members(members: list[ProjectMember]) -> list[ProjectMember]:
    """First occurrence wins; every entry is (or is about to be checked as) the same project's
    member, so any duplicate is interchangeable with the one already kept."""
    return list({member.pk: member for member in members}.values())


def _require_assignees(members: list[ProjectMember]) -> list[ProjectMember]:
    members = _dedupe_members(members)
    if not members:
        raise ValidationError({"assignees": ["ریزهدف باید دست‌کم یک مسئول داشته باشد."]})
    return members


def _assignee_names(members: list[ProjectMember]) -> str:
    return "، ".join(member.user.full_name for member in members)


def _add_objective(
    project: Project, actor, *, title, assignees: list[ProjectMember], due_on, description="", weight=1,
    status=ObjectiveStatus.TODO,
) -> Objective:
    assignees = _require_assignees(assignees)
    if project.objectives.count() >= settings.PROJECT_MAX_OBJECTIVES:
        raise ConflictError(
            f"یک پروژه حداکثر {settings.PROJECT_MAX_OBJECTIVES} ریزهدف می‌تواند داشته باشد.",
            code="objective_limit",
        )
    last = project.objectives.order_by("-position").values_list("position", flat=True).first() or 0
    objective = Objective.objects.create(
        project=project,
        position=last + 1,
        title=_clean_title(title),
        description=(description or "").strip(),
        due_on=due_on,
        weight=weight,
        status=status,
        completed_at=timezone.now() if status == ObjectiveStatus.DONE else None,
        created_by=actor,
    )
    ObjectiveAssignee.objects.bulk_create(
        ObjectiveAssignee(objective=objective, member=member) for member in assignees
    )
    record_event(
        project, ProjectEventKind.OBJECTIVE_ADDED, actor,
        objective=objective, subject_title=objective.title, note=_assignee_names(assignees),
    )
    return objective


def _member_of(project: Project, member) -> ProjectMember:
    if member.project_id != project.pk:
        raise ValidationError({"assignees": ["مسئول ریزهدف باید یکی از اعضای همین پروژه باشد."]})
    return member


@transaction.atomic
def add_objective(project: Project, *, actor, assignees: list[ProjectMember], **fields) -> Objective:
    project = _lock_project(project.pk)
    require_writable(project)
    return _add_objective(project, actor, assignees=[_member_of(project, m) for m in assignees], **fields)


def _lock_objective(objective: Objective) -> tuple[Project, Objective]:
    project = _lock_project(objective.project_id)
    try:
        return project, Objective.objects.get(pk=objective.pk, project=project)
    except Objective.DoesNotExist:
        raise NotFound("ریزهدف یافت نشد.")


@transaction.atomic
def update_objective(objective: Objective, *, actor, changes: dict) -> Objective:
    """Apply any subset of `OBJECTIVE_UPDATABLE`. Status, deadline and assignee-set changes are each
    written to the feed (with the old and the new value); edits to the title, description and
    weight are not events. `completed_at` follows the status: set on DONE, cleared when it leaves.
    `assignees`, when given, **replaces** the whole set — never a partial add/remove."""
    project, objective = _lock_objective(objective)
    require_writable(project)
    unknown = set(changes) - set(OBJECTIVE_UPDATABLE)
    if unknown:
        raise ValueError(f"not updatable: {sorted(unknown)}")

    old_status, old_due = objective.status, objective.due_on
    old_member_ids = set(objective.assignees.values_list("member_id", flat=True))
    if "title" in changes:
        objective.title = _clean_title(changes["title"])
    if "description" in changes:
        objective.description = (changes["description"] or "").strip()
    if "weight" in changes:
        objective.weight = changes["weight"]
    if "due_on" in changes:
        objective.due_on = changes["due_on"]
    if "status" in changes:
        objective.status = changes["status"]
        if objective.status == ObjectiveStatus.DONE and old_status != ObjectiveStatus.DONE:
            objective.completed_at = timezone.now()
        elif objective.status != ObjectiveStatus.DONE:
            objective.completed_at = None

    objective.save()

    new_members = None
    if "assignees" in changes:
        new_members = _require_assignees([_member_of(project, m) for m in changes["assignees"]])
        new_member_ids = {m.pk for m in new_members}
        if new_member_ids != old_member_ids:
            objective.assignees.exclude(member_id__in=new_member_ids).delete()
            kept_ids = set(objective.assignees.values_list("member_id", flat=True))
            ObjectiveAssignee.objects.bulk_create(
                ObjectiveAssignee(objective=objective, member=m) for m in new_members if m.pk not in kept_ids
            )
        else:
            new_members = None  # unchanged: no event, no note needed below

    common = {"objective": objective, "subject_title": objective.title}
    if objective.status != old_status:
        record_event(
            project, ProjectEventKind.OBJECTIVE_STATUS_CHANGED, actor,
            from_status=old_status, to_status=objective.status, **common,
        )
    if objective.due_on != old_due:
        record_event(
            project, ProjectEventKind.OBJECTIVE_DUE_CHANGED, actor,
            from_status=old_due.isoformat(), to_status=objective.due_on.isoformat(), **common,
        )
    if new_members is not None:
        record_event(
            project, ProjectEventKind.OBJECTIVE_ASSIGNED, actor, note=_assignee_names(new_members), **common
        )
    return objective


@transaction.atomic
def remove_objective(objective: Objective, *, actor) -> None:
    """Delete an objective. Its history stays in the feed, reading through `subject_title`."""
    project, objective = _lock_objective(objective)
    require_writable(project)
    title = objective.title
    objective.delete()
    record_event(project, ProjectEventKind.OBJECTIVE_REMOVED, actor, subject_title=title)


@transaction.atomic
def reorder_objectives(project: Project, *, actor, ordered_ids: list[int]) -> None:
    """Set the manual order. `ordered_ids` must be exactly the project's objectives, each once — a
    partial or stale list (someone added one meanwhile) is refused rather than half-applied."""
    project = _lock_project(project.pk)
    require_writable(project)
    current = set(project.objectives.values_list("pk", flat=True))
    if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != current:
        raise ConflictError(
            "فهرست اهداف تغییر کرده است. صفحه را تازه کنید و دوباره تلاش کنید.", code="objectives_changed"
        )
    for position, pk in enumerate(ordered_ids, start=1):
        Objective.objects.filter(pk=pk).update(position=position, updated_at=timezone.now())


# --------------------------------------------------------------------------
# Progress log
# --------------------------------------------------------------------------


def _clean_update_body(body: str) -> str:
    body = (body or "").strip()
    if not body:
        raise ValidationError({"body": ["متن گزارش نمی‌تواند خالی باشد."]})
    if len(body) > OBJECTIVE_UPDATE_MAX_LENGTH:
        raise ValidationError({"body": [f"متن گزارش نباید بیش از {OBJECTIVE_UPDATE_MAX_LENGTH} نویسه باشد."]})
    return body


@transaction.atomic
def add_objective_update(objective: Objective, *, actor, body: str) -> ObjectiveUpdate:
    """Append a dated entry. Who may call this (a current assignee) is the view's job, the same
    "sender only" split every other author-scoped write in this app follows; this only enforces that
    the project is still writable and records the entry and its event in one transaction."""
    project, objective = _lock_objective(objective)
    require_writable(project)
    body = _clean_update_body(body)
    update = ObjectiveUpdate.objects.create(
        objective=objective, author=actor,
        author_name=actor.full_name if actor else "", author_title=actor.title if actor else "",
        body=body,
    )
    record_event(
        project, ProjectEventKind.OBJECTIVE_UPDATE_ADDED, actor,
        objective=objective, subject_title=objective.title, note=body[:COMMENT_PREVIEW_LENGTH],
    )
    return update


@transaction.atomic
def edit_objective_update(update: ObjectiveUpdate, *, actor, body: str) -> ObjectiveUpdate:
    """The author may edit **only their own latest entry on this objective** — the "latest" check
    needs the project's row lock (two concurrent posts by the same author must not both think the
    older one is still current), so it lives here, not in the view. Authorship itself is the view's
    job, the same split `add_objective_update` follows."""
    project = _lock_project(update.objective.project_id)
    require_writable(project)
    try:
        update = ObjectiveUpdate.objects.get(pk=update.pk)
    except ObjectiveUpdate.DoesNotExist:
        raise NotFound("گزارش پیشرفت یافت نشد.")
    latest_id = (
        ObjectiveUpdate.objects.filter(objective_id=update.objective_id, author_id=update.author_id)
        .order_by("-created_at", "-id").values_list("id", flat=True).first()
    )
    if latest_id != update.pk:
        raise ConflictError(
            "فقط آخرین گزارش شما روی این ریزهدف قابل ویرایش است.", code="not_latest_update"
        )
    update.body = _clean_update_body(body)
    update.edited_at = timezone.now()
    update.save(update_fields=["body", "edited_at", "updated_at"])
    return update


# --------------------------------------------------------------------------
# Comments
# --------------------------------------------------------------------------


def _clean_body(body: str) -> str:
    body = (body or "").strip()
    if not body:
        raise ValidationError({"body": ["متن یادداشت نمی‌تواند خالی باشد."]})
    if len(body) > COMMENT_MAX_LENGTH:
        raise ValidationError({"body": [f"متن یادداشت نباید بیش از {COMMENT_MAX_LENGTH} نویسه باشد."]})
    return body


@transaction.atomic
def add_comment(project: Project, *, actor, body: str, objective: Objective | None = None) -> ProjectComment:
    """Append-only: this is a feed, not a document. `objective`, if given, must belong to this very
    project — the same rule `_member_of` enforces for an objective's assignee."""
    project = _lock_project(project.pk)
    require_writable(project)
    body = _clean_body(body)
    if objective is not None and objective.project_id != project.pk:
        raise ValidationError({"objective": ["این ریزهدف متعلق به این پروژه نیست."]})

    comment = ProjectComment.objects.create(
        project=project, objective=objective, author=actor,
        author_name=actor.full_name if actor else "", author_title=actor.title if actor else "",
        body=body,
    )
    record_event(
        project, ProjectEventKind.COMMENT_ADDED, actor,
        objective=objective, subject_title=objective.title if objective else project.name,
        note=body[:COMMENT_PREVIEW_LENGTH],
    )
    return comment


@transaction.atomic
def remove_comment(comment: ProjectComment, *, actor) -> None:
    """Delete a comment. Who may call this is decided by the view (author-only, no exception — the
    same "sender only, never a lead, never مدیر عامل" rule the chat design states for messages,
    §2.6); this only enforces that the project is still writable and records the removal."""
    project = _lock_project(comment.project_id)
    require_writable(project)
    try:
        comment = ProjectComment.objects.get(pk=comment.pk, project=project)
    except ProjectComment.DoesNotExist:
        raise NotFound("یادداشت یافت نشد.")
    subject = comment.objective.title if comment.objective_id else project.name
    comment.delete()
    record_event(project, ProjectEventKind.COMMENT_REMOVED, actor, subject_title=subject)


# --------------------------------------------------------------------------
# Linked documents
# --------------------------------------------------------------------------


@transaction.atomic
def link_document(project: Project, *, actor, document, caption: str = "") -> ProjectDocumentLink:
    project = _lock_project(project.pk)
    require_writable(project)
    existing = ProjectDocumentLink.objects.filter(project=project, document=document).first()
    if existing is not None:
        raise ConflictError(
            "این مستند قبلاً به این پروژه پیوست شده است.", code="already_linked", existing_id=existing.pk
        )
    link = ProjectDocumentLink.objects.create(
        project=project, document=document, caption=(caption or "").strip(), linked_by=actor
    )
    record_event(
        project, ProjectEventKind.DOCUMENT_LINKED, actor,
        subject_title=document.full_code, note=link.caption,
    )
    return link


@transaction.atomic
def unlink_document(link: ProjectDocumentLink, *, actor) -> None:
    project = _lock_project(link.project_id)
    require_writable(project)
    try:
        link = ProjectDocumentLink.objects.select_related("document").get(pk=link.pk, project=project)
    except ProjectDocumentLink.DoesNotExist:
        raise NotFound("پیوند مستند یافت نشد.")
    full_code = link.document.full_code
    link.delete()
    record_event(project, ProjectEventKind.DOCUMENT_UNLINKED, actor, subject_title=full_code)


# --------------------------------------------------------------------------
# Meetings
# --------------------------------------------------------------------------


def _clean_meeting_title(title: str) -> str:
    title = normalize_title(title or "")
    if not title:
        raise ValidationError({"title": ["عنوان جلسه نمی‌تواند خالی باشد."]})
    return title


def _meeting_attendees(project: Project, members: list[ProjectMember]) -> list[ProjectMember]:
    members = _dedupe_members([m for m in members])
    if not members:
        raise ValidationError({"attendees": ["جلسه باید دست‌کم یک شرکت‌کننده داشته باشد."]})
    if any(m.project_id != project.pk for m in members):
        raise ValidationError({"attendees": ["شرکت‌کنندگان باید از اعضای همین پروژه باشند."]})
    if len(members) > settings.PROJECT_MAX_MEMBERS:
        raise ValidationError(
            {"attendees": [f"یک جلسه حداکثر {settings.PROJECT_MAX_MEMBERS} شرکت‌کننده می‌تواند داشته باشد."]}
        )
    return members


def _meeting_event(meeting: ProjectMeeting) -> dict:
    """A meeting event's fields. The day goes in `to_status` as an ISO date — the same overloading
    `objective_due_changed` uses, so the frontend formats it as Jalali rather than printing it raw —
    and the note carries the time and place, if any."""
    parts = []
    if meeting.start_time:
        parts.append(meeting.start_time.strftime("%H:%M"))
    if meeting.location:
        parts.append(meeting.location)
    return {"subject_title": meeting.title, "to_status": meeting.held_on.isoformat(), "note": " · ".join(parts)}


@transaction.atomic
def create_meeting(
    project: Project, *, actor, title: str, held_on, attendees: list[ProjectMember], start_time=None,
    location: str = "", description: str = "",
) -> ProjectMeeting:
    """Schedule a meeting. Who may call this (`can_manage_meetings`) is the view's job."""
    project = _lock_project(project.pk)
    require_writable(project)
    attendees = _meeting_attendees(project, attendees)
    meeting = ProjectMeeting.objects.create(
        project=project, title=_clean_meeting_title(title), held_on=held_on, start_time=start_time,
        location=(location or "").strip(), description=(description or "").strip(),
        created_by=actor, created_by_name=actor.full_name if actor else "",
    )
    MeetingAttendee.objects.bulk_create(MeetingAttendee(meeting=meeting, member=m) for m in attendees)
    record_event(project, ProjectEventKind.MEETING_SCHEDULED, actor, **_meeting_event(meeting))
    return meeting


def _lock_meeting(meeting: ProjectMeeting) -> tuple[Project, ProjectMeeting]:
    project = _lock_project(meeting.project_id)
    try:
        return project, ProjectMeeting.objects.get(pk=meeting.pk, project=project)
    except ProjectMeeting.DoesNotExist:
        raise NotFound("جلسه یافت نشد.")


@transaction.atomic
def update_meeting(meeting: ProjectMeeting, *, actor, changes: dict) -> ProjectMeeting:
    """Apply any subset of `MEETING_UPDATABLE`. `attendees`, when given, replaces the whole set (kept
    attendees keep their acknowledgement). A change of day, time or place clears **every**
    acknowledgement — they acknowledged a different meeting. One `meeting_changed` event, only
    when something actually changed."""
    project, meeting = _lock_meeting(meeting)
    require_writable(project)
    unknown = set(changes) - set(MEETING_UPDATABLE)
    if unknown:
        raise ValueError(f"not updatable: {sorted(unknown)}")

    before = {f: getattr(meeting, f) for f in ("title", "held_on", "start_time", "location", "description")}
    if "title" in changes:
        meeting.title = _clean_meeting_title(changes["title"])
    for field in ("held_on", "start_time"):
        if field in changes:
            setattr(meeting, field, changes[field])
    for field in ("location", "description"):
        if field in changes:
            setattr(meeting, field, (changes[field] or "").strip())
    after = {f: getattr(meeting, f) for f in before}
    changed = before != after
    meeting.save()

    if "attendees" in changes:
        members = _meeting_attendees(project, changes["attendees"])
        wanted = {m.pk for m in members}
        current = set(meeting.attendees.values_list("member_id", flat=True))
        if wanted != current:
            changed = True
            meeting.attendees.exclude(member_id__in=wanted).delete()
            MeetingAttendee.objects.bulk_create(
                MeetingAttendee(meeting=meeting, member=m) for m in members if m.pk not in current
            )

    if any(before[f] != after[f] for f in MEETING_WHEN_WHERE):
        meeting.attendees.update(acknowledged_at=None, updated_at=timezone.now())
    if changed:
        record_event(project, ProjectEventKind.MEETING_CHANGED, actor, **_meeting_event(meeting))
    return meeting


@transaction.atomic
def cancel_meeting(meeting: ProjectMeeting, *, actor) -> None:
    """Delete a meeting (and its attendee rows). Its history stays in the feed."""
    project, meeting = _lock_meeting(meeting)
    require_writable(project)
    fields = _meeting_event(meeting)
    meeting.delete()
    record_event(project, ProjectEventKind.MEETING_CANCELLED, actor, **fields)


@transaction.atomic
def acknowledge_meeting(meeting: ProjectMeeting, *, user) -> ProjectMeeting:
    """«مشاهده شد». Invited attendees only (PermissionDenied otherwise); idempotent — the first
    acknowledgement's time is kept. Not a feed event: it is a read receipt, not a change to the plan."""
    project, meeting = _lock_meeting(meeting)
    require_writable(project)
    attendee = meeting.attendees.filter(member__user=user).first()
    if attendee is None:
        raise PermissionDenied("فقط شرکت‌کنندگان دعوت‌شده می‌توانند دیدن جلسه را تأیید کنند.")
    if attendee.acknowledged_at is None:
        attendee.acknowledged_at = timezone.now()
        attendee.save(update_fields=["acknowledged_at", "updated_at"])
    return meeting


# --------------------------------------------------------------------------
# The new-project draft
# --------------------------------------------------------------------------


def save_draft(*, user, payload: dict) -> ProjectDraft:
    """Keep the one draft this person has (insert or replace). The payload is opaque; its shape and
    size are the view's job."""
    draft, _ = ProjectDraft.objects.update_or_create(user=user, defaults={"payload": payload})
    return draft


def delete_draft(*, user) -> None:
    ProjectDraft.objects.filter(user=user).delete()
