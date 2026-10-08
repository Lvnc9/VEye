"""Every write to announcements goes through here (Phase 19)."""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.core.exceptions import ConflictError
from apps.core.text import normalize_title
from apps.notifications import services as notifications
from apps.notifications.models import NotificationKind
from apps.organization.access import OrgAccess
from apps.organization.tree import lock_node

from .access import audience_users, can_manage, can_publish_to
from .models import Announcement

TITLE_MAX, BODY_MAX = 255, 10000
NOT_ALLOWED = "شما نمی‌توانید برای این مخاطبان اطلاعیه منتشر یا ویرایش کنید."


def _clean(value, field, max_length):
    text = (value or "").strip()
    if not text:
        raise ValidationError({field: ["این فیلد الزامی است."]})
    if len(text) > max_length:
        raise ValidationError({field: [f"نباید بیش از {max_length} نویسه باشد."]})
    return text


def _require_future(expires_on):
    if expires_on is not None and expires_on < timezone.localdate():
        raise ConflictError("تاریخ پایان نمایش نمی‌تواند در گذشته باشد.", code="expires_in_past")


def _lock(pk) -> Announcement:
    try:
        return Announcement.objects.select_for_update(of=("self",)).select_related("audience_node").get(pk=pk)
    except Announcement.DoesNotExist:
        raise NotFound("اطلاعیه یافت نشد.")


@transaction.atomic
def publish(*, actor, title, body, audience_node=None, pinned=False, expires_on=None) -> Announcement:
    node = lock_node(audience_node.pk) if audience_node is not None else None
    if not can_publish_to(OrgAccess(actor), node):
        raise PermissionDenied(NOT_ALLOWED)
    if node is not None and not node.is_active:
        raise ConflictError("برای گرهٔ بایگانی‌شده نمی‌توان اطلاعیه منتشر کرد.", code="node_archived")
    _require_future(expires_on)
    announcement = Announcement.objects.create(
        title=normalize_title(_clean(title, "title", TITLE_MAX)), body=_clean(body, "body", BODY_MAX),
        author=actor, audience_node=node, pinned=bool(pinned), expires_on=expires_on,
    )
    notifications.notify_many(
        [person for person in audience_users(announcement) if person.pk != actor.pk],
        kind=NotificationKind.ANNOUNCEMENT,
        title=f"اطلاعیه: {announcement.title}",
        body=node.name if node else "همهٔ سازمان",
        url="/announcements",
    )
    return announcement


EDITABLE = {"title", "body", "pinned", "expires_on"}


@transaction.atomic
def edit(announcement: Announcement, *, actor, changes: dict) -> Announcement:
    """Title, text, pin and end date — the audience is fixed once published. Changing the words marks it
    «ویرایش‌شده»; nobody is notified again."""
    announcement = _lock(announcement.pk)
    if not can_manage(OrgAccess(actor), announcement):
        raise PermissionDenied(NOT_ALLOWED)
    if announcement.withdrawn_at is not None:
        raise ConflictError("این اطلاعیه برداشته شده است و ویرایش نمی‌شود.", code="withdrawn")
    unknown = set(changes) - EDITABLE
    if unknown:
        raise ValidationError({name: ["این فیلد قابل ویرایش نیست."] for name in sorted(unknown)})
    fields = []
    if "title" in changes:
        title = normalize_title(_clean(changes["title"], "title", TITLE_MAX))
        if title != announcement.title:
            announcement.title = title
            fields.append("title")
    if "body" in changes:
        body = _clean(changes["body"], "body", BODY_MAX)
        if body != announcement.body:
            announcement.body = body
            fields.append("body")
    if fields:
        announcement.edited_at = timezone.now()
        fields.append("edited_at")
    if "pinned" in changes and bool(changes["pinned"]) != announcement.pinned:
        announcement.pinned = bool(changes["pinned"])
        fields.append("pinned")
    if "expires_on" in changes and changes["expires_on"] != announcement.expires_on:
        _require_future(changes["expires_on"])
        announcement.expires_on = changes["expires_on"]
        fields.append("expires_on")
    if fields:
        announcement.save(update_fields=[*fields, "updated_at"])
    return announcement


@transaction.atomic
def withdraw(announcement: Announcement, *, actor) -> Announcement:
    announcement = _lock(announcement.pk)
    if not can_manage(OrgAccess(actor), announcement):
        raise PermissionDenied(NOT_ALLOWED)
    if announcement.withdrawn_at is not None:
        raise ConflictError("این اطلاعیه پیش‌تر برداشته شده است.", code="withdrawn")
    announcement.withdrawn_at, announcement.withdrawn_by = timezone.now(), actor
    announcement.save(update_fields=["withdrawn_at", "withdrawn_by", "updated_at"])
    return announcement
