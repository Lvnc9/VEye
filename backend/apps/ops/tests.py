import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.notifications.models import Notification, NotificationKind

from . import backup
from .models import BackupRun, BackupStatus, BackupTrigger

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "ops-tests"}}


def person(code, roll=AccessRoll.GUILD, level=AccessLevel.LEVEL_2, **extra):
    return User.objects.create_user(
        national_code=code, password="pw-for-tests-123", full_name=f"کاربر {code}", access_roll=roll,
        access_level=level, **extra,
    )


def fake_pg_dump(command, **kwargs):
    """Stands in for pg_dump: writes a few bytes where `--file` points."""
    target = Path(command[command.index("--file") + 1])
    target.write_bytes(b"PGDMP fake dump")
    return subprocess.CompletedProcess(command, 0, b"", b"")


class OpsBase(TestCase):
    def setUp(self):
        self.backups = Path(tempfile.mkdtemp(prefix="veye-backups-"))
        self.media = Path(tempfile.mkdtemp(prefix="veye-media-"))
        (self.media / "pdfs").mkdir()
        (self.media / "pdfs" / "a.pdf").write_bytes(b"%PDF-1.4 test")
        self.addCleanup(shutil.rmtree, self.backups, True)
        self.addCleanup(shutil.rmtree, self.media, True)
        overrides = override_settings(BACKUP_DIR=str(self.backups), MEDIA_ROOT=str(self.media), BACKUP_KEEP=3, CACHES=LOCMEM)
        overrides.enable()
        self.addCleanup(overrides.disable)
        self.ceo = person("6100000001", AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)
        self.developer = person("6100000002", AccessRoll.GUILD, AccessLevel.LEVEL_3, is_developer=True)
        self.staff = person("6100000003")

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client


class PerformTests(OpsBase):
    def run_once(self):
        run = BackupRun.objects.create(trigger=BackupTrigger.SCHEDULE)
        with mock.patch("apps.ops.backup.subprocess.run", side_effect=fake_pg_dump):
            return backup.perform(run)

    def test_a_backup_writes_a_dump_and_a_media_archive(self):
        run = self.run_once()
        self.assertEqual(run.status, BackupStatus.SUCCEEDED)
        self.assertTrue((self.backups / run.db_file).exists())
        self.assertTrue((self.backups / run.media_file).exists())
        self.assertGreater(run.size_bytes, 0)
        self.assertIsNotNone(run.finished_at)
        import tarfile

        with tarfile.open(self.backups / run.media_file) as archive:
            self.assertIn("media/pdfs/a.pdf", archive.getnames())
        self.assertFalse(list(self.backups.glob("*.partial")))

    def test_pg_dump_is_told_where_and_how(self):
        run = BackupRun.objects.create(trigger=BackupTrigger.SCHEDULE)
        with mock.patch("apps.ops.backup.subprocess.run", side_effect=fake_pg_dump) as dump:
            backup.perform(run)
        command, kwargs = dump.call_args.args[0], dump.call_args.kwargs
        self.assertIn("--format=custom", command)
        self.assertIn("--no-owner", command)
        self.assertIn("PGPASSWORD", kwargs["env"])
        self.assertTrue(command[command.index("--file") + 1].endswith(".partial"))

    def test_only_the_newest_sets_are_kept(self):
        runs = []
        for _ in range(5):
            run = self.run_once()
            # distinct start times, oldest first
            BackupRun.objects.filter(pk=run.pk).update(started_at=timezone.now() - timezone.timedelta(days=10 - len(runs)))
            run.refresh_from_db()
            runs.append(run)
        backup.prune()
        kept = {run.pk for run in BackupRun.objects.filter(pruned=False, status=BackupStatus.SUCCEEDED)}
        self.assertEqual(kept, {runs[-1].pk, runs[-2].pk, runs[-3].pk})
        for run in runs[:2]:
            run.refresh_from_db()
            self.assertTrue(run.pruned)
            self.assertFalse((self.backups / run.db_file).exists())
            self.assertFalse((self.backups / run.media_file).exists())
        self.assertTrue((self.backups / runs[-1].db_file).exists())

    def test_a_failure_leaves_no_files_and_tells_the_people_responsible(self):
        run = BackupRun.objects.create(trigger=BackupTrigger.SCHEDULE)
        error = subprocess.CalledProcessError(1, ["pg_dump"], stderr=b"pg_dump: error: connection refused")
        with mock.patch("apps.ops.backup.subprocess.run", side_effect=error):
            run = backup.perform(run)
        self.assertEqual(run.status, BackupStatus.FAILED)
        self.assertIn("connection refused", run.error)
        self.assertEqual(list(self.backups.iterdir()), [])
        told = set(
            Notification.objects.filter(kind=NotificationKind.BACKUP_FAILED).values_list("recipient_id", flat=True)
        )
        self.assertEqual(told, {self.ceo.pk, self.developer.pk})

    def test_a_failure_after_the_dump_removes_the_dump_too(self):
        # Half a set is not a backup: the finished dump goes when the media archive fails.
        run = BackupRun.objects.create(trigger=BackupTrigger.SCHEDULE)
        with mock.patch("apps.ops.backup.subprocess.run", side_effect=fake_pg_dump), mock.patch(
            "apps.ops.backup.tarfile.open", side_effect=OSError("disk full")
        ):
            run = backup.perform(run)
        self.assertEqual(run.status, BackupStatus.FAILED)
        self.assertIn("disk full", run.error)
        self.assertEqual(list(self.backups.iterdir()), [])

    def test_a_missing_pg_dump_is_a_readable_failure(self):
        run = BackupRun.objects.create(trigger=BackupTrigger.SCHEDULE)
        with mock.patch("apps.ops.backup.subprocess.run", side_effect=FileNotFoundError()):
            run = backup.perform(run)
        self.assertEqual(run.status, BackupStatus.FAILED)
        self.assertIn("نصب نیست", run.error)

    def test_a_failed_run_does_not_count_against_the_kept_sets(self):
        good = self.run_once()
        failed = BackupRun.objects.create(trigger=BackupTrigger.SCHEDULE)
        with mock.patch("apps.ops.backup.subprocess.run", side_effect=FileNotFoundError()):
            backup.perform(failed)
        backup.prune(keep=1)
        good.refresh_from_db()
        self.assertFalse(good.pruned)

    def test_a_run_left_running_long_ago_is_marked_failed(self):
        stale = BackupRun.objects.create(trigger=BackupTrigger.SCHEDULE)
        BackupRun.objects.filter(pk=stale.pk).update(started_at=timezone.now() - timezone.timedelta(days=1))
        fresh = BackupRun.objects.create(trigger=BackupTrigger.MANUAL)
        backup.mark_stale_runs()
        stale.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual(stale.status, BackupStatus.FAILED)
        self.assertEqual(fresh.status, BackupStatus.RUNNING)

    def test_the_scheduled_task_creates_its_own_run(self):
        from .tasks import run_backup

        with mock.patch("apps.ops.backup.subprocess.run", side_effect=fake_pg_dump):
            self.assertEqual(run_backup(), BackupStatus.SUCCEEDED)
        self.assertEqual(BackupRun.objects.get().trigger, BackupTrigger.SCHEDULE)

    @mock.patch("apps.ops.backup.subprocess.run", side_effect=fake_pg_dump)
    def test_a_manual_task_skips_a_run_that_is_no_longer_pending(self, _):
        from .tasks import run_backup

        run = BackupRun.objects.create(trigger=BackupTrigger.MANUAL, status=BackupStatus.FAILED)
        self.assertEqual(run_backup(run.pk), "skipped")


class RealDumpTests(OpsBase):
    """One real pg_dump of the test database, so a broken command line cannot hide behind the mocks."""

    def test_pg_dump_produces_a_custom_format_archive(self):
        if shutil.which("pg_dump") is None:
            self.skipTest("pg_dump is not installed here")
        run = backup.perform(BackupRun.objects.create(trigger=BackupTrigger.MANUAL))
        self.assertEqual(run.status, BackupStatus.SUCCEEDED, run.error)
        self.assertEqual((self.backups / run.db_file).read_bytes()[:5], b"PGDMP")


class ApiTests(OpsBase):
    def test_only_the_managing_director_and_the_developer_see_backups(self):
        url = reverse("ops-backups")
        self.assertEqual(self.client_for(self.staff).get(url).status_code, 403)
        self.assertEqual(self.client_for(person("6100000004", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)).get(url).status_code, 403)
        for user in (self.ceo, self.developer):
            response = self.client_for(user).get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["keep"], 3)
        self.assertEqual(APIClient().get(url).status_code, 401)

    def test_the_list_is_newest_first_and_capped_at_the_kept_count(self):
        for _ in range(5):
            BackupRun.objects.create(trigger=BackupTrigger.SCHEDULE, status=BackupStatus.SUCCEEDED)
        runs = self.client_for(self.ceo).get(reverse("ops-backups")).data["runs"]
        self.assertEqual(len(runs), 3)
        self.assertGreater(runs[0]["id"], runs[1]["id"])

    def test_starting_one_now(self):
        with mock.patch("apps.ops.tasks.run_backup.delay") as queued, self.captureOnCommitCallbacks(execute=True):
            response = self.client_for(self.ceo).post(reverse("ops-backups-run"))
        self.assertEqual(response.status_code, 202)
        run = BackupRun.objects.get()
        self.assertEqual((run.status, run.trigger, run.requested_by_id), (BackupStatus.RUNNING, BackupTrigger.MANUAL, self.ceo.pk))
        queued.assert_called_once_with(run.pk)

    def test_one_at_a_time(self):
        BackupRun.objects.create(trigger=BackupTrigger.SCHEDULE)
        with mock.patch("apps.ops.tasks.run_backup.delay") as queued:
            response = self.client_for(self.developer).post(reverse("ops-backups-run"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "backup_running")
        queued.assert_not_called()

    def test_staff_cannot_start_one(self):
        with mock.patch("apps.ops.tasks.run_backup.delay") as queued:
            self.assertEqual(self.client_for(self.staff).post(reverse("ops-backups-run")).status_code, 403)
        queued.assert_not_called()
        self.assertFalse(BackupRun.objects.exists())
