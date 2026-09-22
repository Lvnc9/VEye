"""The Projects activity feed (Phase 8.3) — the "git log" rail: who created a project, changed its
status, added or reassigned an objective, and why, in one place.

A close clone of `apps/documents/history.py`'s `ActivityFeedView`, with one structural difference
that document history does not need: **documents have no visibility scoping** (any signed-in user
may read the whole register), but a project may not. So every queryset here starts from
`visible_projects(request)` — the exact function the project list and detail views already use —
rather than from `Project.objects.all()`. An id for a project the caller cannot read behaves like
one that does not exist: `?project=<id>` on the cross-project feed silently returns nothing (it is
filtered on top of an already-scoped queryset, so this never leaks whether the project exists), and
`/projects/{id}/activity/` for one is a 404 via `get_object_or_404`.

Two views, matching the plan's two routes:

* **`ProjectActivityView`** — `GET /projects/{id}/activity/`, one project's feed.
* **`AllProjectsActivityView`** — `GET /projects/activity/`, the feed across every project the
  caller may read (`?project=` narrows it further, `?q=` searches by project name).

Both are plain Postgres reads; nothing here writes an event — that is services.py's job, inside the
same transaction as the change (docs/11 §2.5).
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers
from rest_framework.generics import ListAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated

from apps.core.pagination import DefaultPagination
from apps.core.text import normalize_search_term

from .access import visible_projects
from .models import ObjectiveStatus, ProjectEvent, ProjectEventKind, ProjectStatus

MAX_DAYS = 3650

#: `from_status` / `to_status` are overloaded by kind: a ProjectStatus pair for
#: project_status_changed, an ObjectiveStatus pair for objective_status_changed, an ISO-date pair
#: for objective_due_changed (already frontend-ready as text, no label), and blank everywhere else.
#: Only the two status-carrying kinds get a human label — `get_..._display()` would be wrong here
#: since the column has no single `choices=` (a CharField cannot declare two enums at once).
_STATUS_ENUM_BY_KIND = {
    ProjectEventKind.PROJECT_STATUS_CHANGED: ProjectStatus,
    ProjectEventKind.OBJECTIVE_STATUS_CHANGED: ObjectiveStatus,
}


def _status_label(kind: str, value: str) -> str:
    enum = _STATUS_ENUM_BY_KIND.get(kind)
    if not enum or not value:
        return ""
    try:
        return enum(value).label
    except ValueError:
        return ""


def _int_param(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class ActivityProjectSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class ActivityObjectiveSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()


class ProjectActivitySerializer(serializers.ModelSerializer):
    project = ActivityProjectSerializer(read_only=True)
    #: null once the objective it was about has been deleted (SET_NULL) — the event still reads
    #: correctly through `subject_title`, exactly as DocumentEvent reads after a superseded revision.
    objective = ActivityObjectiveSerializer(read_only=True)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    from_status_label = serializers.SerializerMethodField()
    to_status_label = serializers.SerializerMethodField()

    class Meta:
        model = ProjectEvent
        fields = [
            "id", "project", "objective", "kind", "kind_label",
            "from_status", "from_status_label", "to_status", "to_status_label",
            "actor_name", "actor_title", "subject_title", "note", "created_at",
        ]
        read_only_fields = fields

    def get_from_status_label(self, obj) -> str:
        return _status_label(obj.kind, obj.from_status)

    def get_to_status_label(self, obj) -> str:
        return _status_label(obj.kind, obj.to_status)


def _apply_shared_filters(qs, params):
    """Filters common to both feeds: `kind` (an unknown value matches nothing, same rule as
    documents' history), `objective` (one objective's own history), `actor` (name contains, same
    normalisation as the register's search), `days` (only the last N, capped)."""
    kind = params.get("kind")
    if kind:
        qs = qs.filter(kind=kind) if kind in ProjectEventKind.values else qs.none()

    if params.get("objective"):
        objective_id = _int_param(params["objective"])
        qs = qs.filter(objective_id=objective_id) if objective_id is not None else qs.none()

    actor = normalize_search_term(params.get("actor", ""))
    if actor:
        qs = qs.filter(actor_name__icontains=actor)

    if params.get("days"):
        days = _int_param(params["days"])
        if days is None or days < 1:
            return qs.none()
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=min(days, MAX_DAYS)))

    return qs


class ProjectActivityView(ListAPIView):
    """GET /projects/{id}/activity/ — one project's feed, newest first.

    Visible to whoever can read the project (`visible_projects`, the same rule the project detail
    view uses): its members, a lead of its بخش or an ancestor, or `manage_organization`. A project
    the caller cannot read is a 404, not a 403 — consistent with `/projects/{id}/`.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = DefaultPagination
    serializer_class = ProjectActivitySerializer

    def get_queryset(self):
        project = get_object_or_404(visible_projects(self.request), pk=self.kwargs["pk"])
        qs = ProjectEvent.objects.filter(project=project).select_related("project", "objective")
        return _apply_shared_filters(qs, self.request.query_params).order_by("-created_at", "-id")


class AllProjectsActivityView(ListAPIView):
    """GET /projects/activity/ — the feed across every project the caller may read, newest first.

    Filters: `kind`, `objective`, `actor`, `days` (see `_apply_shared_filters`), plus `project` (an
    id — narrowed to what is already visible, so one the caller cannot read simply returns nothing,
    the same "an id behaves like it does not exist" rule the list and detail views follow) and `q`
    (the project's own name — the cross-project analogue of the register's search box; `Project.name`
    is already stored letterform-normalised, `services._clean_name`, so this matches the precedent in
    `apps/documents/queries.py search()`: `title__icontains=<normalize_search_term(q)>`).
    """

    permission_classes = [IsAuthenticated]
    pagination_class = DefaultPagination
    serializer_class = ProjectActivitySerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = ProjectEvent.objects.filter(project__in=visible_projects(self.request).values("pk")).select_related(
            "project", "objective"
        )

        if params.get("project"):
            project_id = _int_param(params["project"])
            qs = qs.filter(project_id=project_id) if project_id is not None else qs.none()

        term = normalize_search_term(params.get("q", ""))
        if term:
            qs = qs.filter(project__name__icontains=term)

        return _apply_shared_filters(qs, params).order_by("-created_at", "-id")
