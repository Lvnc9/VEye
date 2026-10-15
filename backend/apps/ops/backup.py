"""Nightly backups (Phase 20): `pg_dump -Fc` of the database and a gzip tar of `media/`, side by side in
`BACKUP_DIR`. Runs on the Celery worker (which already mounts the media volume), never in a request.

Each file is written under a `.partial` name and renamed only when complete, so a set in the directory is
always whole. A failure deletes its partial files, records the reason and tells the مدیر عامل and the
developer account — a backup that silently stopped is worse than none. Restoring is a manual, documented
procedure (README «Back up»); nothing here ever writes to the live database."""
import logging
import os
import subprocess
import tarfile
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import BackupRun, BackupStatus

logger = logging.getLogger("veye")


class BackupError(Exception):
    pass


def backup_dir() -> Path:
    return Path(settings.BACKUP_DIR)


def _partial(path: Path) -> Path:
    return path.with_name(path.name + ".partial")


def _dump_database(target: Path) -> None:
    db = settings.DATABASES["default"]
    env = {**os.environ, "PGPASSWORD": str(db.get("PASSWORD") or "")}
    command = [
        settings.PG_DUMP_BIN,
        "--format=custom",
        "--no-owner",
        "--host", str(db.get("HOST") or "localhost"),
        "--port", str(db.get("PORT") or 5432),
        "--username", str(db.get("USER") or ""),
        "--dbname", str(db["NAME"]),
        "--file", str(_partial(target)),
    ]
    try:
        subprocess.run(command, env=env, check=True, capture_output=True, timeout=settings.BACKUP_TIMEOUT_SECONDS)
    except FileNotFoundError:
        raise BackupError(f"برنامهٔ {settings.PG_DUMP_BIN} روی سرور نصب نیست.")
    except subprocess.TimeoutExpired:
        raise BackupError("پشتیبان‌گیری از پایگاه داده بیش از حد طول کشید.")
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-3:]
        raise BackupError("pg_dump ناموفق بود: " + " | ".join(detail))
    _partial(target).rename(target)


def _archive_media(target: Path) -> None:
    media = Path(settings.MEDIA_ROOT)
    with tarfile.open(_partial(target), "w:gz") as archive:
        if media.exists():
            archive.add(media, arcname="media")
    _partial(target).rename(target)


def _remove(*paths: Path) -> None:
    for path in paths:
        for candidate in (path, _partial(path)):
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass


def prune(keep: int | None = None) -> int:
    """Delete the files of every successful set beyond the newest `keep`; returns how many sets went."""
    keep = settings.BACKUP_KEEP if keep is None else keep
    stale = BackupRun.objects.filter(status=BackupStatus.SUCCEEDED, pruned=False).order_by("-started_at", "-id")[keep:]
    count = 0
    for run in stale:
        _remove(*(backup_dir() / name for name in (run.db_file, run.media_file) if name))
        run.pruned = True
        run.save(update_fields=["pruned"])
        count += 1
    return count


def mark_stale_runs() -> None:
    """A run still «running» long after any backup could take (the worker was killed) is marked failed,
    so it neither blocks the next one nor reads as in progress forever."""
    horizon = timezone.now() - timezone.timedelta(seconds=settings.BACKUP_TIMEOUT_SECONDS * 2)
    BackupRun.objects.filter(status=BackupStatus.RUNNING, started_at__lt=horizon).update(
        status=BackupStatus.FAILED, finished_at=timezone.now(), error="پشتیبان‌گیری نیمه‌کاره ماند (فرایند قطع شد)."
    )


def perform(run: BackupRun) -> BackupRun:
    directory = backup_dir()
    stamp = timezone.localtime(run.started_at).strftime("%Y%m%d-%H%M%S")
    # The run id keeps two runs started in the same second from sharing (and pruning) one name.
    db_path = directory / f"veye-{stamp}-{run.pk}.dump"
    media_path = directory / f"veye-{stamp}-{run.pk}-media.tar.gz"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        _dump_database(db_path)
        _archive_media(media_path)
    except Exception as exc:  # anything at all: the run must end as failed, not stay «running»
        _remove(db_path, media_path)
        logger.exception("Backup %s failed", run.pk)
        run.status = BackupStatus.FAILED
        run.error = str(exc)[:2000] or exc.__class__.__name__
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error", "finished_at"])
        _notify_failure(run)
        return run

    run.status = BackupStatus.SUCCEEDED
    run.db_file = db_path.name
    run.media_file = media_path.name
    run.size_bytes = db_path.stat().st_size + media_path.stat().st_size
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "db_file", "media_file", "size_bytes", "finished_at"])
    prune()
    return run


def backup_admins():
    """Who sees backups and hears about a failed one: the مدیر عامل (and superusers) and the developer."""
    from django.db.models import Q

    from apps.documents.authority import approve_eligible_users
    from apps.accounts.models import User

    return User.objects.filter(is_active=True).filter(
        Q(pk__in=approve_eligible_users().values("pk")) | Q(is_developer=True)
    )


def _notify_failure(run: BackupRun) -> None:
    from apps.notifications import services as notifications
    from apps.notifications.models import NotificationKind

    with transaction.atomic():
        notifications.notify_many(
            list(backup_admins()),
            kind=NotificationKind.BACKUP_FAILED,
            title="پشتیبان‌گیری ناموفق بود",
            body=run.error[:500],
            url="/settings",
            dedupe_key=f"backup:{run.pk}",
        )
