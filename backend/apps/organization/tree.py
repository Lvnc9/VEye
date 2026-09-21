"""The organisation tree's rules — the one place that writes OrgNode.

A CHECK constraint cannot read another row, so everything that relates a node to its
parent lives here: `depth = parent.depth + 1`, `path = parent.path + own segment`,
`parent_kind = parent.kind`, the cycle check on a move, and the pre-flight for delete.
(A trigger would be a second home for the same policy — the reason `Capability` is
computed rather than mirrored into Django Groups.) The database still enforces what one
row can say for itself: the parent-kind table, the singleton root and sibling-unique
names. Those are checked here *first* so the caller gets a Persian message instead of an
IntegrityError, and stay in the schema as the net.

Locking: every write takes `SELECT … FOR UPDATE` on the rows whose stored path/depth it
reads, so a create under a node that is being moved waits for the move instead of
computing its path from the old one.
"""
from contextlib import contextmanager

from django.db import IntegrityError, transaction
from django.db.models import F, Value
from django.db.models.functions import Concat, Substr
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.core.exceptions import ConflictError
from apps.core.text import normalize_search_term, normalize_title

from .models import ALLOWED_PARENT_KINDS, NODE_NAME_CONSTRAINT, OrgNode, OrgNodeKind
from .setup_state import STEP_FOR_NODE_KIND, advance_step

PATH_SEGMENT_WIDTH = 10

_PARENT_KIND_MESSAGES = {
    OrgNodeKind.DOMAIN: "حوزه فقط زیر شرکت ساخته می‌شود.",
    OrgNodeKind.UNIT: "واحد زیر شرکت یا زیر یک حوزه ساخته می‌شود.",
    OrgNodeKind.SECTION: "بخش فقط زیر یک واحد ساخته می‌شود.",
}


def _segment(pk: int) -> str:
    return f"{pk:0{PATH_SEGMENT_WIDTH}d}/"


def _clean_name(name: str) -> tuple[str, str]:
    """(display form, sibling-uniqueness key)."""
    name = normalize_title(name or "")
    if not name:
        raise ValidationError({"name": ["نام نمی‌تواند خالی باشد."]})
    return name, normalize_search_term(name)


def lock_node(pk: int) -> OrgNode:
    try:
        return OrgNode.objects.select_for_update().get(pk=pk)
    except OrgNode.DoesNotExist:
        raise NotFound("گره یافت نشد.")


def _require_parent_kind(kind: str, parent: OrgNode | None) -> None:
    if parent is None or parent.kind not in ALLOWED_PARENT_KINDS[kind]:
        raise ValidationError({"parent": [_PARENT_KIND_MESSAGES[kind]]})


def _require_active(parent: OrgNode) -> None:
    if not parent.is_active:
        raise ConflictError(
            "این گره بایگانی شده است. ابتدا آن را از بایگانی خارج کنید.",
            code="parent_archived",
            parent_id=parent.pk,
        )


def _require_not_root(node: OrgNode, message: str) -> None:
    if node.kind == OrgNodeKind.COMPANY:
        raise ConflictError(message, code="root_immutable")


def _check_name_free(parent_id: int | None, name_key: str, *, exclude_pk: int | None = None) -> None:
    if parent_id is None:  # the root has no siblings
        return
    clashes = OrgNode.objects.filter(parent_id=parent_id, name_key=name_key)
    if exclude_pk is not None:
        clashes = clashes.exclude(pk=exclude_pk)
    clash = clashes.first()
    if clash is not None:
        raise ConflictError(
            "در همین محل گره‌ای با این نام وجود دارد.", code="duplicate_name", existing_id=clash.pk
        )


@contextmanager
def _name_collisions_as_conflicts(parent_id: int | None, name_key: str, *, exclude_pk: int | None = None):
    """Turn a lost race on the sibling-name constraint into the same 409 the pre-check
    gives. Only that constraint: any other IntegrityError is a bug and must stay loud."""
    try:
        with transaction.atomic():
            yield
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)
        if constraint != NODE_NAME_CONSTRAINT:
            raise
        _check_name_free(parent_id, name_key, exclude_pk=exclude_pk)
        raise


def _insert(*, kind: str, parent: OrgNode | None, name: str, key: str, created_by) -> OrgNode:
    node = OrgNode(
        parent=parent,
        kind=kind,
        parent_kind=parent.kind if parent else "",
        name=name,
        name_key=key,
        path="",  # needs the id, which only exists after the insert
        depth=parent.depth + 1 if parent else 0,
        created_by=created_by,
    )
    with _name_collisions_as_conflicts(parent.pk if parent else None, key):
        node.save()
    node.path = (parent.path if parent else "") + _segment(node.pk)
    node.save(update_fields=["path"])
    return node


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------


@transaction.atomic
def create_root(*, name: str, created_by=None) -> OrgNode:
    """The company's root node. Only bootstrap calls this. A second root violates
    `uniq_company_root_node` and raises IntegrityError — the caller maps it."""
    name, key = _clean_name(name)
    return _insert(kind=OrgNodeKind.COMPANY, parent=None, name=name, key=key, created_by=created_by)


@transaction.atomic
def create_node(*, kind: str, name: str, parent: OrgNode, created_by=None) -> OrgNode:
    if kind == OrgNodeKind.COMPANY:
        raise ValueError("the company root is made by create_root()")
    parent = lock_node(parent.pk)
    _require_parent_kind(kind, parent)
    _require_active(parent)
    name, key = _clean_name(name)
    _check_name_free(parent.pk, key)
    node = _insert(kind=kind, parent=parent, name=name, key=key, created_by=created_by)
    advance_step(STEP_FOR_NODE_KIND[kind])
    return node


@transaction.atomic
def rename_node(node: OrgNode, name: str) -> OrgNode:
    node = lock_node(node.pk)
    name, key = _clean_name(name)
    _check_name_free(node.parent_id, key, exclude_pk=node.pk)
    node.name, node.name_key = name, key
    with _name_collisions_as_conflicts(node.parent_id, key, exclude_pk=node.pk):
        node.save(update_fields=["name", "name_key", "updated_at"])
    return node


@transaction.atomic
def move_node(node: OrgNode, new_parent: OrgNode) -> OrgNode:
    """Re-parent a node together with its whole subtree.

    Every descendant's `path` and `depth` shift in one UPDATE. The kind table still
    applies (a بخش moves between واحدها, a واحد between حوزه or up to the company); the
    cycle check comes first because it is the answer that explains itself.
    """
    node = lock_node(node.pk)
    _require_not_root(node, "شرکت را نمی‌توان جابه‌جا کرد.")
    if new_parent.pk == node.parent_id:
        return node
    new_parent = lock_node(new_parent.pk)

    # A node's own path is a prefix of every path beneath it (and of nothing else), so this
    # catches "under itself" (equal paths) and "under one of its descendants" alike.
    if new_parent.path.startswith(node.path):
        raise ConflictError("یک گره را نمی‌توان زیر خودش یا زیرمجموعه‌اش برد.", code="cycle")
    _require_parent_kind(node.kind, new_parent)
    _require_active(new_parent)
    _check_name_free(new_parent.pk, node.name_key)

    # No subtree lock: only a واحد can move and its children are leaves, so a concurrent
    # create "under the subtree" is a create under `node`, which the lock above already
    # serialises (verified with real threads). If nodes below a movable node ever get
    # children of their own, lock `path__startswith=node.path` here.
    old_prefix = node.path
    new_prefix = new_parent.path + _segment(node.pk)
    depth_shift = new_parent.depth + 1 - node.depth

    node.parent, node.parent_kind = new_parent, new_parent.kind
    with _name_collisions_as_conflicts(new_parent.pk, node.name_key, exclude_pk=node.pk):
        node.save(update_fields=["parent", "parent_kind", "updated_at"])
    OrgNode.objects.filter(path__startswith=old_prefix).update(
        path=Concat(Value(new_prefix), Substr("path", len(old_prefix) + 1)),
        depth=F("depth") + depth_shift,
        updated_at=timezone.now(),
    )
    node.refresh_from_db()
    return node


@transaction.atomic
def update_node(node: OrgNode, *, name: str | None = None, parent: OrgNode | None = None) -> OrgNode:
    """A rename and/or a move as one unit: either both land or neither does."""
    if name is not None:
        node = rename_node(node, name)
    if parent is not None:
        node = move_node(node, parent)
    return node


@transaction.atomic
def archive_node(node: OrgNode) -> OrgNode:
    """The supported retirement for a node that has (or had) people and work.

    Refused while it still has active children, so an active node never sits under an
    archived one — the chart would otherwise show a live بخش inside a retired واحد."""
    node = lock_node(node.pk)
    _require_not_root(node, "شرکت را نمی‌توان بایگانی کرد.")
    if not node.is_active:
        return node
    active_children = node.children.filter(is_active=True).count()
    if active_children:
        raise ConflictError(
            "ابتدا زیرمجموعه‌های فعال این گره را بایگانی کنید.",
            code="has_active_children",
            active_children=active_children,
        )
    node.is_active = False
    node.save(update_fields=["is_active", "updated_at"])
    return node


@transaction.atomic
def unarchive_node(node: OrgNode) -> OrgNode:
    node = lock_node(node.pk)
    if node.is_active:
        return node
    if node.parent_id is not None:
        _require_active(lock_node(node.parent_id))
    node.is_active = True
    node.save(update_fields=["is_active", "updated_at"])
    return node


def node_blockers(node: OrgNode) -> dict[str, int]:
    """What stops a node being deleted, as counts. (Conversations join in Phase 9.)"""
    return {
        "children": node.children.count(),
        "members": node.memberships.count(),
        "projects": node.projects.count(),
    }


@transaction.atomic
def delete_node(node: OrgNode) -> None:
    """Delete an empty node. PROTECT on every inbound foreign key is the real net; this
    pre-flight exists to say *why* — an unhandled ProtectedError would be a 500."""
    node = lock_node(node.pk)
    _require_not_root(node, "شرکت را نمی‌توان حذف کرد.")
    blockers = node_blockers(node)
    if any(blockers.values()):
        raise ConflictError(
            "این گره خالی نیست و حذف نمی‌شود. ابتدا محتوای آن را جابه‌جا کنید یا آن را بایگانی کنید.",
            code="node_not_empty",
            **blockers,
        )
    node.delete()
