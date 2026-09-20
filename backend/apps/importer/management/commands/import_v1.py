"""Import V_1.0's documents into Postgres.

    # 1. Stage V_1.0's data next to docker-compose.yml (git-ignored), e.g.
    #      import_data/saves/…json   import_data/img/…png   import_data/rows.json
    #    (rows.json = `mongoexport --jsonArray` of the index collection), or supply a
    #    MongoDB connection string in an environment variable of the worker.
    # 2. Dry run (the default; writes nothing, prints what would happen):
    docker compose exec backend python manage.py import_v1 --index-file /import_data/rows.json
    # 3. Really import:
    docker compose exec backend python manage.py import_v1 --index-file /import_data/rows.json --commit

The job runs in Celery (`--sync` runs it inline). Collisions are skipped and reported, files are
read only from the local directory, and re-running is safe. See docs/10-phase-6.md.
"""
import json
import time
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.importer import sources, tasks
from apps.importer.models import ImportRun, ImportStatus

STALE_AFTER = timedelta(hours=2)
NOTE_MARK = {"error": "✗", "warning": "!", "info": "·"}


class Command(BaseCommand):
    help = "واردسازی مستندات نسخهٔ ۱ (MongoDB + saves/ + img/) به Postgres. پیش‌فرض: اجرای آزمایشی (بدون نوشتن)."

    def add_arguments(self, parser):
        source = parser.add_argument_group("منبع ردیف‌ها (یکی از دو)")
        source.add_argument("--index-file", help="فایل mongoexport (آرایهٔ JSON یا هر ردیف در یک خط)")
        source.add_argument(
            "--mongo-uri-env", metavar="NAME",
            help="نام متغیر محیطی که نشانی اتصال MongoDB در آن است (خودِ نشانی ذخیره یا چاپ نمی‌شود)")
        source.add_argument("--mongo-db", default=sources.DEFAULT_MONGO_DB)
        source.add_argument("--mongo-collection", default=sources.DEFAULT_MONGO_COLLECTION)
        parser.add_argument("--v1-dir", default="/import_data", help="پوشه‌ای که saves/ و img/ در آن است (پیش‌فرض /import_data)")
        parser.add_argument("--commit", action="store_true", help="واقعاً بنویس (بدون آن فقط اجرای آزمایشی است)")
        parser.add_argument("--sync", action="store_true", help="در همین فرایند اجرا کن، نه در Celery")
        parser.add_argument("--report-file", help="گزارش کامل را به‌صورت JSON در این فایل بنویس")
        parser.add_argument("--status", type=int, metavar="RUN_ID", help="گزارش یک اجرای قبلی را نشان بده")

    def handle(self, *args, **opts):
        if opts["status"]:
            run = ImportRun.objects.filter(pk=opts["status"]).first()
            if run is None:
                raise CommandError("اجرایی با این شماره یافت نشد.")
            return self.show(run, opts)

        if bool(opts["index_file"]) == bool(opts["mongo_uri_env"]):
            raise CommandError("دقیقاً یکی از --index-file یا --mongo-uri-env را بدهید.")
        if ImportRun.objects.filter(status=ImportStatus.RUNNING, started_at__gt=timezone.now() - STALE_AFTER).exists():
            raise CommandError("یک واردسازی دیگر در حال اجراست. پس از پایان آن دوباره تلاش کنید.")

        options = {"v1_dir": opts["v1_dir"]}
        if opts["index_file"]:
            options["index_file"] = opts["index_file"]
        else:
            # Only the *name* of the variable is kept; the URI is read where the job runs.
            options.update(mongo_uri_env=opts["mongo_uri_env"], mongo_db=opts["mongo_db"],
                           mongo_collection=opts["mongo_collection"])
        run = ImportRun.objects.create(dry_run=not opts["commit"], options=options)

        mode = "واقعی" if opts["commit"] else "آزمایشی (چیزی نوشته نمی‌شود)"
        self.stdout.write(f"واردسازی #{run.pk} — اجرای {mode}")
        if opts["sync"]:
            tasks.import_v1.apply(args=(run.pk,))
        else:
            tasks.import_v1.delay(run.pk)
            self.wait(run)
        run.refresh_from_db()
        self.show(run, opts)

    def wait(self, run):
        last = -1
        while True:
            run.refresh_from_db()
            if run.status in (ImportStatus.SUCCEEDED, ImportStatus.FAILED):
                return
            if run.processed != last:
                last = run.processed
                self.stdout.write(f"  {run.get_status_display()}… {run.processed}/{run.total or '؟'}")
            time.sleep(1)

    def show(self, run, opts):
        if run.status == ImportStatus.FAILED:
            raise CommandError(f"واردسازی #{run.pk} ناموفق بود: {run.error}")
        if run.status != ImportStatus.SUCCEEDED:
            self.stdout.write(f"واردسازی #{run.pk}: {run.get_status_display()} ({run.processed}/{run.total})")
            return

        for entry in run.report:
            notable = entry["action"] in ("skipped", "error") or any(n["level"] != "info" for n in entry["notes"])
            if not notable:
                continue
            self.stdout.write(f"[{entry['code'] or '؟'}] {entry['title']} — {entry['action']}")
            for note in entry["notes"]:
                self.stdout.write(f"    {NOTE_MARK.get(note['level'], '·')} {note['message']}")

        c = run.counts
        self.stdout.write("")
        self.stdout.write(
            f"ردیف‌ها: {c.get('total', 0)} · "
            + (f"ایجاد‌شده: {c.get('created', 0)}" if not run.dry_run else f"ایجاد می‌شد: {c.get('would_create', 0)}")
            + f" · ردشده: {c.get('skipped', 0)} · خطا: {c.get('errors', 0)} · هشدار: {c.get('warnings', 0)}"
            + f" · منسوخ‌شده هنگام واردسازی: {c.get('superseded', 0)}"
        )
        if run.dry_run:
            self.stdout.write("این یک اجرای آزمایشی بود. برای نوشتن واقعی همان دستور را با --commit اجرا کنید.")
        if opts.get("report_file"):
            with open(opts["report_file"], "w", encoding="utf-8") as handle:
                json.dump({"run": run.pk, "dry_run": run.dry_run, "counts": run.counts, "report": run.report},
                          handle, ensure_ascii=False, indent=2)
            self.stdout.write(f"گزارش کامل: {opts['report_file']}")
