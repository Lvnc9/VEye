"""Registry business rules: allocating document numbers and creating revisions.

Ported from V_1.0 `Documents.check_code` (other_folder/documents_01.py:677-787).
The two paths there — "new title" and "new revision of an existing title" — are
split into two explicit operations here instead of being inferred from whether
the typed title happens to exist.
"""
from django.db import transaction
from rest_framework.exceptions import NotFound

from apps.core.exceptions import ConflictError
from apps.core.text import normalize_title

from . import content
from .models import MAX_REVISION, Document, DocumentSequence


def _allocate_number(group: str) -> int:
    # The row lock is what serializes concurrent creators in the same group.
    # get_or_create so no seeding migration is needed (and none can be lost to a
    # test-suite table flush).
    sequence, _ = DocumentSequence.objects.select_for_update().get_or_create(group=group)
    sequence.last_number += 1
    sequence.save(update_fields=["last_number"])
    return sequence.last_number


@transaction.atomic
def create_document(*, user, category: str, title: str, group: str) -> Document:
    """Register a brand-new document: revision 1 with the next number in its group.

    Everything runs in one transaction, so a rejected request rolls the number
    allocation back too — numbers stay gapless.
    """
    title = normalize_title(title)

    # Take the group lock *before* checking for an existing title, so two
    # people creating the same title at once can't both pass the check.
    number = _allocate_number(group)

    existing = Document.objects.filter(group=group, title=title).order_by("-revision").first()
    if existing is not None:
        # V_1.0 silently turned this into a new revision (locater(), :691). Here
        # it is reported, and the client is told which document it collided with.
        # The advice depends on whether a revision is actually possible: the
        # «بازنگری جدید» action only exists once the latest revision is finished.
        if existing.is_finalized:
            advice = "برای ایجاد نسخه جدید از «بازنگری جدید» استفاده کنید."
        else:
            advice = "ابتدا آن مستند را تکمیل کنید."
        raise ConflictError(
            f"مستندی با این عنوان در این گروه وجود دارد. {advice}",
            code="title_exists",
            existing_id=existing.pk,
        )

    return Document.objects.create(
        category=category,
        title=title,
        group=group,
        number=number,
        revision=1,
        created_by=user,
    )


@transaction.atomic
def create_revision(*, user, document_id: int) -> Document:
    """Create the next revision of a document.

    Rules, from V_1.0 documents_01.py:735-761:
      * the previous revision must be finished — V_1.0 refused with
        "First finish your previous document!" while `valid == "unknown"`.
      * the new revision inherits title, group, number and category, and starts
        with a copy of the previous revision's body (see content.copy_content).
    Added here: it must be the *latest* revision, and the revision counter is
    capped rather than wrapping from 99 back to 00.
    """
    try:
        # Locking the row serializes two people revising the same document; the
        # loser then sees the winner's row below.
        previous = Document.objects.select_for_update().get(pk=document_id)
    except Document.DoesNotExist:
        raise NotFound("مستند یافت نشد.")

    if Document.objects.filter(previous_revision=previous).exists():
        raise ConflictError(
            "این بازنگری، آخرین بازنگری مستند نیست.", code="not_latest_revision"
        )

    if not previous.is_finalized:
        raise ConflictError(
            "ابتدا مستند قبلی را تکمیل کنید.", code="previous_not_finished"
        )

    if previous.revision >= MAX_REVISION:
        raise ConflictError(
            f"حداکثر تعداد بازنگری ({MAX_REVISION}) برای این مستند ثبت شده است.",
            code="revision_limit",
        )

    revision = Document.objects.create(
        category=previous.category,
        title=previous.title,
        group=previous.group,
        number=previous.number,
        revision=previous.revision + 1,
        previous_revision=previous,
        created_by=user,
    )
    # V_1.0 opened a blank designer for every revision, so authors retyped the
    # whole document. A new revision now starts as a copy of the one it replaces.
    content.copy_content(previous, revision)
    return revision
