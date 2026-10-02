"""The reports surface (Phase 17): CSV exports of the document register and of the projects a person
may read. Gated by `view_reports`; each export is exactly what the matching screen would show, so
nothing here widens who can see what — the document register is open to everyone signed in, and the
project export goes through `visible_projects`, the same scoping `/projects/` uses."""
import jdatetime
from django.utils import timezone
from rest_framework.views import APIView

from apps.accounts.models import Capability
from apps.core.permissions import HasCapability
from apps.documents import queries as document_queries
from apps.documents.models import Document
from apps.projects.access import visible_projects
from apps.projects.models import ProjectMember, ProjectRole
from apps.projects.queries import progress_percent, with_progress
from rest_framework.permissions import IsAuthenticated

from .csv_export import csv_response


def jalali(moment) -> str:
    """`1405/07/10` for a date or an aware datetime (in the local zone); empty for None."""
    if moment is None:
        return ""
    day = timezone.localtime(moment).date() if hasattr(moment, "hour") else moment
    return jdatetime.date.fromgregorian(date=day).strftime("%Y/%m/%d")


class _ReportView(APIView):
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = Capability.VIEW_REPORTS


DOCUMENT_HEADER = [
    "کد مستند", "عنوان", "گروه", "دسته‌بندی", "وضعیت", "بازنگری", "گرهٔ مالک", "ایجادکننده",
    "تاریخ ایجاد", "آخرین تغییر",
]


class DocumentsExportView(_ReportView):
    """GET /reports/documents/export/ — the register as a spreadsheet: one row per revision, with
    the register's own filters (`?group=`, `?category=`, `?status=`, `?search=`)."""

    def get(self, request):
        queryset = document_queries.apply_filters(
            Document.objects.select_related("owner_node", "created_by").order_by("group", "number", "revision"),
            request.query_params,
        )
        rows = (
            [
                d.full_code, d.title, d.get_group_display(), d.get_category_display(), d.get_status_display(),
                d.revision, d.owner_node.name if d.owner_node else "", d.created_by.full_name,
                jalali(d.created_at), jalali(d.updated_at),
            ]
            for d in queryset.iterator(chunk_size=500)
        )
        return csv_response("documents", DOCUMENT_HEADER, rows)


PROJECT_HEADER = [
    "نام پروژه", "بخش", "وضعیت", "هدف", "تاریخ شروع", "مهلت", "پیشرفت (٪)", "تعداد ریزهدف",
    "ریزهدف دیرکرد", "تعداد اعضا", "مدیران پروژه", "بایگانی‌شده", "تاریخ ایجاد",
]


class ProjectsExportView(_ReportView):
    """GET /reports/projects/export/ — the projects this person may read, one row each, with the
    derived progress (never a stored number) and the overdue count. `?archived=1` for archived ones."""

    def get(self, request):
        archived = request.query_params.get("archived") in ("1", "true")
        projects = list(
            with_progress(visible_projects(request))
            .filter(archived_at__isnull=not archived)
            .order_by("section__path", "name")
        )
        members: dict[int, list] = {}
        for member in ProjectMember.objects.filter(project__in=projects).select_related("user"):
            members.setdefault(member.project_id, []).append(member)
        rows = []
        for p in projects:
            team = members.get(p.pk, [])
            managers = "، ".join(m.user.full_name for m in team if m.role == ProjectRole.MANAGER)
            percent = progress_percent(p.weight_done, p.weight_total)
            rows.append(
                [
                    p.name, p.section.name, p.get_status_display(), p.goal, jalali(p.starts_on), jalali(p.due_on),
                    "" if percent is None else percent, p.objective_count, p.overdue_count, len(team), managers,
                    p.is_archived, jalali(p.created_at),
                ]
            )
        return csv_response("projects", PROJECT_HEADER, rows)
