from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Index, Q, UniqueConstraint

from apps.core.models import TimeStampedModel
from apps.organization.models import OrgNode


class ProjectStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "در حال اجرا"
    ON_HOLD = "ON_HOLD", "متوقف"
    DONE = "DONE", "پایان‌یافته"
    CANCELLED = "CANCELLED", "لغو شده"


class ProjectRole(models.TextChoices):
    MANAGER = "MANAGER", "مدیر پروژه"
    MEMBER = "MEMBER", "عضو"


class ObjectiveStatus(models.TextChoices):
    TODO = "TODO", "انجام نشده"
    IN_PROGRESS = "IN_PROGRESS", "در حال انجام"
    BLOCKED = "BLOCKED", "متوقف"
    DONE = "DONE", "انجام شد"
    CANCELLED = "CANCELLED", "لغو شد"


#: An objective in one of these no longer counts as overdue (finished, or dropped).
CLOSED_OBJECTIVE_STATUSES = (ObjectiveStatus.DONE, ObjectiveStatus.CANCELLED)


class ProjectEventKind(models.TextChoices):
    """Every kind the project's activity feed will ever carry. The objective, comment and document
    kinds are written from slices 8.2–8.4; declaring them all now keeps the column's choices stable."""

    PROJECT_CREATED = "project_created", "پروژه ایجاد شد"
    PROJECT_STATUS_CHANGED = "project_status_changed", "وضعیت پروژه تغییر کرد"
    PROJECT_ARCHIVED = "project_archived", "پروژه بایگانی شد"
    PROJECT_UNARCHIVED = "project_unarchived", "پروژه از بایگانی خارج شد"
    MEMBER_ADDED = "member_added", "عضو افزوده شد"
    GUEST_INVITED = "guest_invited", "مهمان دعوت شد"
    MEMBER_ROLE_CHANGED = "member_role_changed", "نقش عضو تغییر کرد"
    MEMBER_REMOVED = "member_removed", "عضو حذف شد"
    OBJECTIVE_ADDED = "objective_added", "ریزهدف افزوده شد"
    OBJECTIVE_ASSIGNED = "objective_assigned", "ریزهدف واگذار شد"
    OBJECTIVE_STATUS_CHANGED = "objective_status_changed", "وضعیت ریزهدف تغییر کرد"
    OBJECTIVE_DUE_CHANGED = "objective_due_changed", "مهلت ریزهدف تغییر کرد"
    OBJECTIVE_REMOVED = "objective_removed", "ریزهدف حذف شد"
    OBJECTIVE_UPDATE_ADDED = "objective_update_added", "گزارش پیشرفت ثبت شد"
    COMMENT_ADDED = "comment_added", "یادداشت افزوده شد"
    COMMENT_REMOVED = "comment_removed", "یادداشت حذف شد"
    DOCUMENT_LINKED = "document_linked", "مستند پیوست شد"
    DOCUMENT_UNLINKED = "document_unlinked", "پیوند مستند حذف شد"
    MEETING_SCHEDULED = "meeting_scheduled", "جلسه تعیین شد"
    MEETING_CHANGED = "meeting_changed", "جلسه تغییر کرد"
    MEETING_CANCELLED = "meeting_cancelled", "جلسه لغو شد"


class Project(TimeStampedModel):
    """A piece of planned work, owned by one بخش.

    Not a controlled document: its status moves permissively (every change is *recorded*, not
    guarded), unlike the document workflow's rigid state machine. `archived_at` is deliberately
    separate from `status = DONE` — DONE is an outcome, archived is a visibility decision, and
    conflating them would make it impossible to un-hide a project without reopening it.
    """

    #: A kind=SECTION node; checked by the service (a CHECK cannot read another row).
    section = models.ForeignKey(OrgNode, on_delete=models.PROTECT, related_name="projects")
    name = models.CharField(max_length=255)
    #: normalize_search_term(name): what per-بخش uniqueness compares. Never client-settable.
    name_key = models.CharField(max_length=255)
    #: هدف
    goal = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=ProjectStatus.choices, default=ProjectStatus.ACTIVE)
    starts_on = models.DateField(null=True, blank=True)
    due_on = models.DateField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_projects"
    )

    class Meta:
        ordering = ["-id"]
        constraints = [
            UniqueConstraint(fields=["section", "name_key"], name="uniq_project_name_per_section"),
            CheckConstraint(
                check=Q(starts_on__isnull=True) | Q(due_on__isnull=True) | Q(due_on__gte=models.F("starts_on")),
                name="project_due_not_before_start",
            ),
        ]
        indexes = [Index(fields=["section", "status"], name="project_section_status_idx")]

    def __str__(self):
        return self.name

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


class ProjectMember(TimeStampedModel):
    """A person on a project. `is_guest` is *stored*, not derived: derived would cost a query per
    member and would flip retroactively when someone changes بخش, silently reclassifying history.
    The service computes it once, at add time (is the person in the project's بخش?)."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="project_memberships")
    role = models.CharField(max_length=8, choices=ProjectRole.choices, default=ProjectRole.MEMBER)
    is_guest = models.BooleanField(default=False)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["role", "id"]  # "MANAGER" sorts before "MEMBER"
        constraints = [UniqueConstraint(fields=["project", "user"], name="uniq_project_member")]

    def __str__(self):
        return f"{self.user.full_name} @ {self.project.name}"


class Objective(TimeStampedModel):
    """A ریز هدف: one piece of a project's plan, with **several assignees (at least one) and one
    deadline, both required** — there is no unassigned backlog. Who owns it lives in
    `ObjectiveAssignee`, below; there are no levels among assignees, and any of them may write
    under their own name and change the status.

    Progress and overdue-ness are **derived, never stored** (queries.py): a stored percentage is a
    cache that goes stale the moment anyone edits a weight.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="objectives")
    #: Manual order in the «اهداف» list (1-based, kept dense by the service).
    position = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_on = models.DateField()
    status = models.CharField(max_length=16, choices=ObjectiveStatus.choices, default=ObjectiveStatus.TODO)
    #: How much it counts towards the project's progress.
    weight = models.PositiveSmallIntegerField(default=1)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["position", "id"]
        constraints = [CheckConstraint(check=Q(weight__gte=1), name="objective_weight_positive")]
        indexes = [
            Index(fields=["project", "position"], name="objective_project_position_idx"),
            Index(fields=["status", "due_on"], name="objective_status_due_idx"),
        ]

    def __str__(self):
        return self.title


class ObjectiveAssignee(TimeStampedModel):
    """One person responsible for a ریز هدف. `member` points at the *ProjectMember*, not the User —
    the model's most valuable detail, kept from the single-assignee design: the database itself
    refuses an objective assigned to a non-member, and removing a member who still owns work is a
    409 instead of a silent orphan. "At least one assignee" cannot be a CHECK constraint (it cannot
    count sibling rows), so services.py enforces it."""

    objective = models.ForeignKey(Objective, on_delete=models.CASCADE, related_name="assignees")
    member = models.ForeignKey(ProjectMember, on_delete=models.PROTECT, related_name="objective_assignments")

    class Meta:
        ordering = ["id"]
        constraints = [UniqueConstraint(fields=["objective", "member"], name="uniq_objective_assignee")]

    def __str__(self):
        return f"{self.member.user.full_name} → {self.objective.title}"


class ObjectiveUpdate(TimeStampedModel):
    """A dated progress entry under one objective, written by one of its assignees. Every write is a
    new row — the newest shows under the author's name, older ones expand in «سوابق» — never an edit
    of an older one; the author may PATCH only **their own latest** entry on this objective
    (views.py + services.py, the same "no delete, no rewriting history" rule `ProjectComment` half-
    follows, tightened here to "your latest only" because a progress log is a timeline, not a
    discussion).

    `author_name`/`author_title` are the usual durable text snapshot, so an entry keeps reading
    correctly after its author is deactivated or moves بخش.
    """

    objective = models.ForeignKey(Objective, on_delete=models.CASCADE, related_name="updates")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    author_name = models.CharField(max_length=255)
    author_title = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Forward, so objective.updates.all() reads as a timeline; the API view orders newest first.
        ordering = ["created_at", "id"]
        indexes = [
            Index(fields=["objective", "created_at"], name="obj_update_obj_time_idx"),
            #: Backs "this author's latest entry on this objective" (services.py, and the objective
            #: payload's per-assignee latest_update/update_count, queries.py).
            Index(fields=["objective", "author"], name="obj_update_obj_author_idx"),
        ]

    def __str__(self):
        return f"{self.author_name} on {self.objective.title}"


class ProjectEvent(TimeStampedModel):
    """One line of the project's activity feed — a near-copy of DocumentEvent, including the
    load-bearing decision: actor name and title are *text snapshots*, so the trail keeps reading
    correctly after someone is deactivated or moves بخش. Written by the service inside the same
    transaction as the change it records — never by a signal."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=32, choices=ProjectEventKind.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    actor_name = models.CharField(max_length=255)
    actor_title = models.CharField(max_length=255, blank=True)
    #: The objective it is about, if any. SET_NULL: deleting an objective keeps its history, which
    #: still reads correctly through `subject_title`.
    objective = models.ForeignKey(
        Objective, null=True, blank=True, on_delete=models.SET_NULL, related_name="events"
    )
    #: What the event is about, as it read at the time (an objective's title, a member's name…).
    subject_title = models.CharField(max_length=255, blank=True)
    #: A status change's before and after. For `objective_due_changed` the same two fields hold the
    #: old and new deadline as ISO dates (they fit), so the feed needs no extra columns.
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        # Forward, so project.events.all() reads as a timeline; the feed *views* order newest first.
        ordering = ["created_at", "id"]
        indexes = [Index(fields=["project", "created_at"], name="projectevent_project_time_idx")]

    def __str__(self):
        return f"{self.project.name} {self.kind} by {self.actor_name}"


class ProjectComment(TimeStampedModel):
    """A human note on a project (or, with `objective` set, on one ریز هدف of it) — a feed with no
    human note is a machine log; without this, people discuss the project in chat and the project
    loses its record. Append-only: no editing, no deleting except by the author (the same "sender
    only, never a lead" principle the chat design states for messages, §2.6).

    `author_name`/`author_title` are text snapshots, the same device as every other actor field in
    this app, so a comment keeps reading correctly after its author is deactivated or moves بخش.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="comments")
    #: Nullable: a comment on the project as a whole, or on one specific ریز هدف.
    objective = models.ForeignKey(
        Objective, null=True, blank=True, on_delete=models.SET_NULL, related_name="comments"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    author_name = models.CharField(max_length=255)
    author_title = models.CharField(max_length=255, blank=True)
    body = models.TextField()

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [Index(fields=["project", "created_at"], name="projectcomment_time_idx")]

    def __str__(self):
        return f"{self.author_name} on {self.project.name}"


class ProjectDocumentLink(TimeStampedModel):
    """VEye *is* a document system; a project that produced PR-07 should say so.

    `document` PROTECTs: a document a project points at cannot be deleted out from under the link
    (documents are never hard-deleted in this app anyway, but the guard costs nothing and matches
    the PROTECT convention used everywhere else a row is *referenced*, not *owned*).
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="document_links")
    document = models.ForeignKey(
        "documents.Document", on_delete=models.PROTECT, related_name="project_links"
    )
    caption = models.CharField(max_length=255, blank=True)
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [UniqueConstraint(fields=["project", "document"], name="uniq_project_document_link")]

    def __str__(self):
        return f"{self.project.name} → {self.document.full_code}"


class ProjectMeeting(TimeStampedModel):
    """A meeting on the project's «جدول جلسات». Every project reader sees every meeting; only the
    invited attendees acknowledge it («مشاهده شد»). Who may create, edit or cancel one is narrower
    than `can_manage_project` on purpose (access.can_manage_meetings): the project's MANAGER role, or
    a کارفرمایی account — not a بخش lead (ADR-010, and the owner's 2026-09-26 addition)."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="meetings")
    title = models.CharField(max_length=255)
    held_on = models.DateField()
    #: Optional: a meeting may be fixed to a day before its hour is.
    start_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    #: Snapshot, like every other actor name in this app.
    created_by_name = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-held_on", models.F("start_time").desc(nulls_last=True), "-id"]
        indexes = [Index(fields=["project", "held_on"], name="meeting_project_day_idx")]

    def __str__(self):
        return f"{self.title} ({self.held_on})"


class MeetingAttendee(TimeStampedModel):
    """One invited project member. CASCADE on the member: someone removed from the project stops
    being an attendee (ADR-010's default). `acknowledged_at` is set once, the first time they press
    «مشاهده شد», and cleared for everyone when the date, time or place changes."""

    meeting = models.ForeignKey(ProjectMeeting, on_delete=models.CASCADE, related_name="attendees")
    member = models.ForeignKey(ProjectMember, on_delete=models.CASCADE, related_name="meeting_invitations")
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [UniqueConstraint(fields=["meeting", "member"], name="uniq_meeting_attendee")]

    def __str__(self):
        return f"{self.member.user.full_name} → {self.meeting.title}"



class ProjectDraft(TimeStampedModel):
    """The one half-typed new project a person has, autosaved from /projects/new (ADR-010: server-side,
    one per user, deleted when a project is created). `payload` is opaque to the server — the
    frontend owns its shape and versioning (`{version, form}`); only its size is bounded
    (`PROJECT_DRAFT_MAX_BYTES`). Not a `Project` row with a DRAFT status: that would leak into
    visibility, lists, events, progress and name uniqueness."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_draft")
    payload = models.JSONField()

    def __str__(self):
        return f"draft of {self.user_id}"
