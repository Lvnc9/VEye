"""«تقویم» (Phase 22, owner's decision 2026-10-15): one person's dated work for a window of days — gathered from
the apps that own it, read-only. "Mine" means what is *on me*: assigned to me, led by me, owned by me, or a
document I may write that is due for review. A lead may add «مرخصی تیم» — the leave of the people under the
nodes they lead. (Named `agenda`, not `calendar`, so it never shadows the standard library.)"""
from datetime import date

from django.db.models import Q
from django.utils import timezone

KIND_LABELS = {
    "objective": "ریزهدف",
    "action": "اقدام اصلاحی",
    "meeting": "جلسه",
    "audit": "ممیزی",
    "risk_review": "بازنگری ریسک",
    "document_review": "بازنگری مستند",
    "leave": "مرخصی من",
    "delegation": "جانشینی",
    "team_leave": "مرخصی تیم",
    "holiday": "تعطیل رسمی",
}


def _item(kind, day, title, url="", *, end=None, subtitle="", overdue=False, key=None):
    return {
        "key": key or f"{kind}:{title}:{day}",
        "kind": kind,
        "kind_label": KIND_LABELS[kind],
        "date": day,
        "end_date": end,
        "title": title,
        "subtitle": subtitle,
        "url": url,
        "overdue": overdue,
    }


def gather(request, start: date, end: date, *, team: bool) -> list[dict]:
    from apps.leave.models import Holiday, LeaveRequest, LeaveStatus
    from apps.organization.access import access_for
    from apps.organization.models import Delegation
    from apps.projects.models import CLOSED_OBJECTIVE_STATUSES, Objective, ProjectMeeting
    from apps.quality.models import FINAL_AUDIT_STATUSES, OPEN_ACTION_STATUSES, CorrectiveAction, InternalAudit, RiskItem, RiskStatus

    user = request.user
    today = timezone.localdate()
    items: list[dict] = []

    for o in (
        Objective.objects.filter(assignees__member__user=user, due_on__range=(start, end), project__archived_at__isnull=True)
        .exclude(status__in=CLOSED_OBJECTIVE_STATUSES)
        .select_related("project")
        .distinct()
    ):
        items.append(_item("objective", o.due_on, o.title, f"/projects/{o.project_id}", subtitle=o.project.name,
                           overdue=o.due_on < today, key=f"objective:{o.pk}"))

    for a in CorrectiveAction.objects.filter(assignee=user, due_on__range=(start, end), status__in=OPEN_ACTION_STATUSES).select_related("nc"):
        items.append(_item("action", a.due_on, a.title, f"/quality/{a.nc_id}", subtitle=a.nc.code,
                           overdue=a.due_on < today, key=f"action:{a.pk}"))

    for m in (
        ProjectMeeting.objects.filter(attendees__member__user=user, held_on__range=(start, end), project__archived_at__isnull=True)
        .select_related("project")
        .distinct()
    ):
        when = m.start_time.strftime("%H:%M") if m.start_time else ""
        items.append(_item("meeting", m.held_on, m.title, f"/projects/{m.project_id}",
                           subtitle=" · ".join(part for part in (m.project.name, when) if part), key=f"meeting:{m.pk}"))

    for au in InternalAudit.objects.filter(lead_auditor=user, planned_on__range=(start, end)).exclude(status__in=FINAL_AUDIT_STATUSES):
        items.append(_item("audit", au.planned_on, au.title, f"/quality/audits/{au.pk}", subtitle=au.code,
                           overdue=au.planned_on < today, key=f"audit:{au.pk}"))

    for r in RiskItem.objects.filter(owner=user, review_on__range=(start, end)).exclude(status=RiskStatus.CLOSED):
        items.append(_item("risk_review", r.review_on, r.title, f"/quality/risks/{r.pk}", subtitle=r.code,
                           overdue=r.review_on < today, key=f"risk:{r.pk}"))

    items.extend(_document_reviews(request, start, end, today))

    for lv in LeaveRequest.objects.filter(
        requester=user, status__in=(LeaveStatus.PENDING, LeaveStatus.APPROVED), starts_on__lte=end, ends_on__gte=start
    ):
        items.append(_item("leave", lv.starts_on, lv.get_leave_type_display(), "/leave", end=lv.ends_on,
                           subtitle=lv.get_status_display(), key=f"leave:{lv.pk}"))

    for d in Delegation.objects.filter(delegate=user, starts_on__lte=end, ends_on__gte=start).select_related("node"):
        items.append(_item("delegation", d.starts_on, f"جانشین موقت «{d.node.name}»", "/organization", end=d.ends_on,
                           key=f"delegation:{d.pk}"))

    for h in Holiday.objects.filter(date__range=(start, end)):
        items.append(_item("holiday", h.date, h.title, key=f"holiday:{h.pk}"))

    if team:
        org = access_for(request)
        led = org.led_subtree_q("node__path")
        for lv in (
            LeaveRequest.objects.filter(led, status__in=(LeaveStatus.PENDING, LeaveStatus.APPROVED), starts_on__lte=end, ends_on__gte=start)
            .exclude(requester=user)
            .select_related("requester")
        ):
            items.append(_item("team_leave", lv.starts_on, lv.requester.full_name, "/leave", end=lv.ends_on,
                               subtitle=f"{lv.get_leave_type_display()} · {lv.get_status_display()}", key=f"team_leave:{lv.pk}"))

    items.sort(key=lambda item: (item["date"], item["kind"], item["title"]))
    return items


def _document_reviews(request, start, end, today) -> list[dict]:
    from apps.core.constants import DocumentStatus
    from apps.documents import authority
    from apps.documents.models import Document

    documents = Document.objects.filter(
        authority.for_request(request).authoring_q(), status=DocumentStatus.UNDER_CONTROL, review_due_on__range=(start, end)
    )
    return [
        _item("document_review", d.review_due_on, f"{d.full_code} — {d.title}", f"/documents/{d.pk}/edit",
              overdue=d.review_due_on < today, key=f"document:{d.pk}")
        for d in documents
    ]


def leads_anything(request) -> bool:
    from apps.organization.access import access_for

    return bool(access_for(request).lead_nodes)
