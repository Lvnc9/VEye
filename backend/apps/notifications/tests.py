from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, User

from . import services
from .models import Notification, NotificationKind

_counter = [0]


def make_user(**extra) -> User:
    _counter[0] += 1
    return User.objects.create_user(
        national_code=f"87{_counter[0]:08d}",
        password="pw-for-tests-123",
        full_name=f"کاربر {_counter[0]}",
        access_roll=AccessRoll.GUILD,
        access_level=AccessLevel.LEVEL_3,
        **extra,
    )


class NotifyTests(TestCase):
    def test_notify_creates_a_row_addressed_to_one_person(self):
        user = make_user()
        notification = services.notify(user, kind=NotificationKind.DOCUMENT_APPROVED, title="عنوان", body="متن", url="/x")
        self.assertEqual(notification.recipient_id, user.pk)
        self.assertEqual(notification.title, "عنوان")
        self.assertIsNone(notification.read_at)

    def test_without_a_dedupe_key_every_call_is_a_new_row(self):
        user = make_user()
        services.notify(user, kind=NotificationKind.DOCUMENT_APPROVED, title="یک")
        services.notify(user, kind=NotificationKind.DOCUMENT_APPROVED, title="یک")
        self.assertEqual(Notification.objects.filter(recipient=user).count(), 2)

    def test_a_dedupe_key_makes_a_repeat_call_a_no_op(self):
        user = make_user()
        first = services.notify(user, kind=NotificationKind.OBJECTIVE_DUE_SOON, title="یک", dedupe_key="obj:1:today")
        second = services.notify(user, kind=NotificationKind.OBJECTIVE_DUE_SOON, title="دو", dedupe_key="obj:1:today")
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(Notification.objects.filter(recipient=user).count(), 1)
        self.assertEqual(Notification.objects.get(recipient=user).title, "یک")  # the first call's row, untouched

    def test_the_same_dedupe_key_is_fine_for_two_different_people(self):
        a, b = make_user(), make_user()
        services.notify(a, kind=NotificationKind.OBJECTIVE_DUE_SOON, title="یک", dedupe_key="obj:1:today")
        services.notify(b, kind=NotificationKind.OBJECTIVE_DUE_SOON, title="یک", dedupe_key="obj:1:today")
        self.assertEqual(Notification.objects.count(), 2)

    def test_notify_many_sends_once_per_person_even_with_duplicate_recipients(self):
        a, b = make_user(), make_user()
        created = services.notify_many([a, b, a], kind=NotificationKind.DOCUMENT_APPROVED, title="عنوان")
        self.assertEqual(len(created), 2)
        self.assertEqual(Notification.objects.filter(recipient=a).count(), 1)


class ReadTests(TestCase):
    def test_mark_read_sets_the_timestamp_once(self):
        user = make_user()
        notification = services.notify(user, kind=NotificationKind.DOCUMENT_APPROVED, title="عنوان")
        self.assertEqual(services.unread_count(user), 1)
        services.mark_read(notification)
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)
        self.assertEqual(services.unread_count(user), 0)

    def test_mark_read_twice_does_not_move_the_timestamp(self):
        user = make_user()
        notification = services.notify(user, kind=NotificationKind.DOCUMENT_APPROVED, title="عنوان")
        services.mark_read(notification)
        first = Notification.objects.get(pk=notification.pk).read_at
        services.mark_read(Notification.objects.get(pk=notification.pk))
        self.assertEqual(Notification.objects.get(pk=notification.pk).read_at, first)

    def test_mark_all_read_only_touches_one_persons_rows(self):
        a, b = make_user(), make_user()
        services.notify(a, kind=NotificationKind.DOCUMENT_APPROVED, title="یک")
        services.notify(a, kind=NotificationKind.DOCUMENT_APPROVED, title="دو")
        services.notify(b, kind=NotificationKind.DOCUMENT_APPROVED, title="سه")
        updated = services.mark_all_read(a)
        self.assertEqual(updated, 2)
        self.assertEqual(services.unread_count(a), 0)
        self.assertEqual(services.unread_count(b), 1)


class NotificationApiTests(TestCase):
    def client_for(self, user) -> APIClient:
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_requires_authentication(self):
        self.assertEqual(APIClient().get(reverse("notification-list")).status_code, 401)

    def test_only_sees_their_own(self):
        a, b = make_user(), make_user()
        services.notify(a, kind=NotificationKind.DOCUMENT_APPROVED, title="مال من")
        services.notify(b, kind=NotificationKind.DOCUMENT_APPROVED, title="مال دیگری")
        results = self.client_for(a).get(reverse("notification-list")).data["results"]
        self.assertEqual([row["title"] for row in results], ["مال من"])

    def test_reading_someone_elses_notification_is_not_found(self):
        a, b = make_user(), make_user()
        theirs = services.notify(b, kind=NotificationKind.DOCUMENT_APPROVED, title="مال دیگری")
        response = self.client_for(a).post(reverse("notification-read", args=[theirs.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertIsNone(Notification.objects.get(pk=theirs.pk).read_at)

    def test_read_marks_one_row(self):
        user = make_user()
        notification = services.notify(user, kind=NotificationKind.DOCUMENT_APPROVED, title="عنوان")
        response = self.client_for(user).post(reverse("notification-read", args=[notification.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_read"])

    def test_read_all_marks_every_unread_row(self):
        user = make_user()
        services.notify(user, kind=NotificationKind.DOCUMENT_APPROVED, title="یک")
        services.notify(user, kind=NotificationKind.DOCUMENT_APPROVED, title="دو")
        response = self.client_for(user).post(reverse("notification-read-all"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["updated"], 2)
        self.assertEqual(services.unread_count(user), 0)
