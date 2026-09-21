"""Membership rules — the one place that writes Membership.

The invariant kept here: **a person with any membership has exactly one primary** (their
"home" node, what the chart and chat will use to say where someone sits). The partial unique
index in the schema is the net for "at most one"; "at least one" is this module's job:

  * a person's first membership is always primary;
  * making another membership primary demotes the old one in the same transaction;
  * the only primary cannot be unset — you make a different one primary instead;
  * removing the primary promotes the person's earliest remaining membership.

Every write first takes `SELECT … FOR UPDATE` on the *user* row, so two requests touching the
same person's memberships queue instead of both deciding "I am their first" (which the index
would then reject as a 500). A person's memberships are always locked user-first, node-second.

Who may write is decided in access.py and checked by the views. One rule cannot be checked
there, because it needs the locks taken here: making a membership primary **demotes the
person's primary elsewhere**, and a lead must never be able to alter a membership in a part of
the chart they do not run. Callers pass `may_touch(node) -> bool`; when the change would demote
a primary at a node it rejects, PermissionDenied is raised. (Removing a primary promotes the
next membership too, but that is bookkeeping to keep the invariant, not a choice the caller
makes, so it is not checked — otherwise a lead could not remove their own people.)
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.core.exceptions import ConflictError
from apps.core.text import normalize_title

from .models import Membership
from .tree import lock_node

User = get_user_model()


def _lock_user(pk: int):
    try:
        return User.objects.select_for_update().get(pk=pk)
    except User.DoesNotExist:
        raise NotFound("شخص یافت نشد.")


def _require_may_demote(user_id: int, may_touch) -> None:
    """Under the user lock: about to demote this person's current primary — may the caller
    touch the node it is in?"""
    current = Membership.objects.filter(user_id=user_id, is_primary=True).select_related("node").first()
    if current is not None and may_touch is not None and not may_touch(current.node):
        raise PermissionDenied(
            "برای تغییر گرهٔ اصلی این شخص باید مسئول گرهٔ اصلی فعلی او نیز باشید."
        )


def _lock_membership(pk: int) -> Membership:
    try:
        return Membership.objects.select_for_update().select_related("user", "node").get(pk=pk)
    except Membership.DoesNotExist:
        raise NotFound("عضویت یافت نشد.")


@transaction.atomic
def add_membership(
    *,
    user,
    node,
    is_lead: bool = False,
    is_primary: bool | None = None,
    position_label: str = "",
    added_by=None,
    may_touch=None,
) -> Membership:
    """Put a person into a node. `is_primary=None` means "not specified"; a person's first
    membership is primary whatever is asked."""
    user = _lock_user(user.pk)
    node = lock_node(node.pk)
    if not user.is_active:
        raise ConflictError(
            "این شخص غیرفعال است و نمی‌توان او را به گره‌ای افزود.", code="user_inactive", user_id=user.pk
        )
    if not node.is_active:
        raise ConflictError(
            "به گرهٔ بایگانی‌شده نمی‌توان عضو افزود. ابتدا آن را از بایگانی خارج کنید.",
            code="node_archived",
            node_id=node.pk,
        )
    existing = Membership.objects.filter(user=user, node=node).first()
    if existing is not None:
        raise ConflictError(
            "این شخص از قبل عضو این گره است.", code="already_member", existing_id=existing.pk
        )

    has_any = Membership.objects.filter(user=user).exists()
    primary = True if not has_any else bool(is_primary)
    if primary and has_any:
        _require_may_demote(user.pk, may_touch)
        Membership.objects.filter(user=user, is_primary=True).update(is_primary=False)

    return Membership.objects.create(
        user=user,
        node=node,
        is_primary=primary,
        is_lead=is_lead,
        position_label=normalize_title(position_label),
        added_by=added_by,
    )


@transaction.atomic
def update_membership(
    membership: Membership,
    *,
    is_lead: bool | None = None,
    is_primary: bool | None = None,
    position_label: str | None = None,
    may_touch=None,
) -> Membership:
    """Change what a membership says. Which person and which node are fixed — to move someone,
    remove the membership and add a new one, so there is never an ambiguous "before"."""
    _lock_user(membership.user_id)
    membership = _lock_membership(membership.pk)

    if is_primary is False and membership.is_primary:
        raise ConflictError(
            "هر شخص باید یک عضویت اصلی داشته باشد. به‌جای آن، عضویت دیگری را اصلی کنید.",
            code="primary_required",
        )
    if is_primary and not membership.is_primary:
        _require_may_demote(membership.user_id, may_touch)
        Membership.objects.filter(user_id=membership.user_id, is_primary=True).update(is_primary=False)
        membership.is_primary = True
    if is_lead is not None:
        membership.is_lead = is_lead
    if position_label is not None:
        membership.position_label = normalize_title(position_label)
    membership.save(update_fields=["is_primary", "is_lead", "position_label", "updated_at"])
    return membership


@transaction.atomic
def remove_membership(membership: Membership) -> None:
    _lock_user(membership.user_id)
    membership = _lock_membership(membership.pk)
    was_primary = membership.is_primary
    membership.delete()
    if was_primary:
        # Keep "any membership => exactly one primary": the earliest remaining one takes over.
        successor = Membership.objects.filter(user_id=membership.user_id).order_by("id").first()
        if successor is not None:
            Membership.objects.filter(pk=successor.pk).update(is_primary=True)
