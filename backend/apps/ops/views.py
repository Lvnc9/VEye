from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import ConflictError

from . import backup
from .access import can_manage_backups
from .models import BackupRun, BackupStatus, BackupTrigger

NOT_ALLOWED = "فقط مدیر عامل و حساب توسعه‌دهنده به پشتیبان‌گیری دسترسی دارند."


def _run_payload(run: BackupRun) -> dict:
    return {
        "id": run.id,
        "status": run.status,
        "status_label": run.get_status_display(),
        "trigger": run.trigger,
        "trigger_label": run.get_trigger_display(),
        "requested_by": run.requested_by.full_name if run.requested_by_id else "",
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "db_file": run.db_file,
        "media_file": run.media_file,
        "size_bytes": run.size_bytes,
        "error": run.error,
        "pruned": run.pruned,
    }


class BackupListView(APIView):
    """«پشتیبان‌گیری» in تنظیمات (Phase 20): the latest runs and the policy that produced them."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can_manage_backups(request.user):
            raise PermissionDenied(NOT_ALLOWED)
        backup.mark_stale_runs()
        runs = BackupRun.objects.select_related("requested_by")[: settings.BACKUP_KEEP]
        return Response(
            {
                "runs": [_run_payload(run) for run in runs],
                "keep": settings.BACKUP_KEEP,
                "schedule": settings.BACKUP_SCHEDULE_LABEL,
            }
        )


class BackupRunView(APIView):
    """«پشتیبان‌گیری الان»: queue one now. One at a time (409 while another is running)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not can_manage_backups(request.user):
            raise PermissionDenied(NOT_ALLOWED)
        from .tasks import run_backup

        with transaction.atomic():
            backup.mark_stale_runs()
            if BackupRun.objects.select_for_update().filter(status=BackupStatus.RUNNING).exists():
                raise ConflictError("یک پشتیبان‌گیری در حال انجام است.", code="backup_running")
            run = BackupRun.objects.create(trigger=BackupTrigger.MANUAL, requested_by=request.user)
            transaction.on_commit(lambda: run_backup.delay(run.pk))
        return Response(_run_payload(run), status=202)
