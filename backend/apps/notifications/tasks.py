"""Scheduled reminders (Phase 15) — the first Celery **beat** tasks in the project (every task
before this one ran on demand: a PDF build, a bulk-print ZIP). Each task here is read-only
except for the `Notification` rows it writes, is safe to run more than once a day (the
`dedupe_key` on each notification makes a repeat a no-op, see `services.notify`), and never
changes a document's or objective's own state — a reminder nudges, it does not act.

Registered in `config/celery.py`'s `CELERY_BEAT_SCHEDULE`; `docker-compose.yml` runs them from a
dedicated `celery-beat` service (the worker container does not also run the scheduler).
"""
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from . import services
from .models import NotificationKind


@shared_task(name="notifications.check_due_objectives")
def check_due_objectives() -> int:
    """نزدیک‌به‌مهلت/گذشته‌ازمهلت ریزهدف، once per calendar day per objective (`dedupe_key` keys
    on today's date, so a beat interval shorter than a day never double-reminds). Mirrors the
    query `apps.dashboard.views.DashboardInboxView` already computes live for the badge; this
    task is the only thing that turns it into something a person can read and dismiss."""
    from apps.projects.models import CLOSED_OBJECTIVE_STATUSES, Objective

    today = timezone.localdate()
    horizon = today + timezone.timedelta(days=settings.INBOX_DUE_SOON_DAYS)
    due = (
        Objective.objects.filter(project__archived_at__isnull=True, due_on__lte=horizon)
        .exclude(status__in=CLOSED_OBJECTIVE_STATUSES)
        .select_related("project")
        .prefetch_related("assignees__member__user")
    )
    sent = 0
    for objective in due:
        overdue = objective.due_on < today
        kind = NotificationKind.OBJECTIVE_OVERDUE if overdue else NotificationKind.OBJECTIVE_DUE_SOON
        title = (
            f"ریزهدف «{objective.title}» از مهلت گذشته است"
            if overdue
            else f"ریزهدف «{objective.title}» نزدیک به مهلت است"
        )
        recipients = [assignee.member.user for assignee in objective.assignees.all()]
        created = services.notify_many(
            recipients,
            kind=kind,
            title=title,
            body=objective.project.name,
            url=f"/projects/{objective.project_id}",
            dedupe_key=f"objective:{objective.pk}:{kind}:{today.isoformat()}",
        )
        sent += len(created)
    return sent


@shared_task(name="notifications.check_stalled_documents")
def check_stalled_documents() -> int:
    """A مستند sitting in AWAITING_CONFIRMATION/AWAITING_APPROVAL longer than
    `DOCUMENT_STALL_DAYS` gets its eligible people one nudge per calendar day — not an
    escalation, not a status change, just the same reminder `workflow.submit`/`confirm` already
    send, repeated so it is not lost in an inbox."""
    from apps.core.constants import DocumentStatus
    from apps.documents import authority as document_authority
    from apps.documents.models import Document

    today = timezone.localdate()
    threshold = timezone.now() - timezone.timedelta(days=settings.DOCUMENT_STALL_DAYS)
    stalled = Document.objects.filter(
        status__in=[DocumentStatus.AWAITING_CONFIRMATION, DocumentStatus.AWAITING_APPROVAL],
        updated_at__lte=threshold,
    ).select_related("owner_node")

    sent = 0
    for document in stalled:
        recipients = (
            document_authority.confirm_eligible_users(document)
            if document.status == DocumentStatus.AWAITING_CONFIRMATION
            else document_authority.approve_eligible_users()
        )
        created = services.notify_many(
            recipients,
            kind=NotificationKind.DOCUMENT_STALLED,
            title=f"«{document.full_code}» مدتی است منتظر مانده",
            body=document.title,
            url=f"/documents/{document.pk}/edit",
            dedupe_key=f"document:{document.pk}:stalled:{today.isoformat()}",
        )
        sent += len(created)
    return sent


@shared_task(name="notifications.check_due_actions")
def check_due_actions() -> int:
    """Corrective actions (Phase 18) that are due soon or overdue, one reminder per day to the
    assignee — the same cadence and dedupe as `check_due_objectives`. Only an action the assignee still
    has to do (TODO / IN_PROGRESS) on a record that is still being worked: a DONE action is waiting on
    a verifier, and a closed or rejected record has nothing left to chase."""
    from apps.quality.models import OPEN_ACTION_STATUSES, CorrectiveAction, NcStatus

    today = timezone.localdate()
    horizon = today + timezone.timedelta(days=settings.INBOX_DUE_SOON_DAYS)
    due = CorrectiveAction.objects.filter(
        status__in=OPEN_ACTION_STATUSES, due_on__lte=horizon, nc__status=NcStatus.IN_PROGRESS
    ).select_related("assignee", "nc")
    sent = 0
    for action in due:
        overdue = action.due_on < today
        kind = NotificationKind.CAPA_OVERDUE if overdue else NotificationKind.CAPA_DUE_SOON
        created = services.notify(
            action.assignee,
            kind=kind,
            title=f"اقدام «{action.title}» از مهلت گذشته است" if overdue else f"اقدام «{action.title}» نزدیک به مهلت است",
            body=f"{action.nc.code}: {action.nc.title}",
            url=f"/quality/{action.nc_id}",
            dedupe_key=f"capa:{action.pk}:{kind}:{today.isoformat()}",
        )
        sent += 1 if created else 0
    return sent


@shared_task(name="notifications.check_risk_reviews")
def check_risk_reviews() -> int:
    """A risk's review date (Phase 18) that is near or past, **one reminder per review date** — the
    `dedupe_key` carries the date, so a re-run is a no-op and a *new* date after a review is a new
    reminder. It goes to the named owner, or to the node chain's leads when nobody is named. A closed
    risk has nothing to review; an accepted one still does."""
    from apps.quality import services as quality
    from apps.quality.models import RiskItem, RiskStatus

    today = timezone.localdate()
    horizon = today + timezone.timedelta(days=settings.INBOX_DUE_SOON_DAYS)
    due = (
        RiskItem.objects.filter(review_on__isnull=False, review_on__lte=horizon)
        .exclude(status=RiskStatus.CLOSED)
        .select_related("owner", "owner_node")
    )
    sent = 0
    for risk in due:
        overdue = risk.review_on < today
        created = services.notify_many(
            quality.risk_review_recipients(risk),
            kind=NotificationKind.RISK_REVIEW_DUE,
            title=f"زمان بازنگری ریسک «{risk.title}» گذشته است" if overdue else f"زمان بازنگری ریسک «{risk.title}» نزدیک است",
            body=f"{risk.code}: {risk.owner_node.name}",
            url=f"/quality/risks/{risk.pk}",
            dedupe_key=f"risk:{risk.pk}:review:{risk.review_on.isoformat()}",
        )
        sent += len(created)
    return sent
