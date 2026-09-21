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
    COMMENT_ADDED = "comment_added", "یادداشت افزوده شد"
    DOCUMENT_LINKED = "document_linked", "مستند پیوست شد"


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
    #: What the event is about, as it read at the time (an objective's title, a member's name…).
    subject_title = models.CharField(max_length=255, blank=True)
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        # Forward, so project.events.all() reads as a timeline; the feed *views* order newest first.
        ordering = ["created_at", "id"]
        indexes = [Index(fields=["project", "created_at"], name="projectevent_project_time_idx")]

    def __str__(self):
        return f"{self.project.name} {self.kind} by {self.actor_name}"
