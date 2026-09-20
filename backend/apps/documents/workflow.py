"""The sign-off workflow (Phase 5): تدوین → تایید → تصویب, and مرجوع.

    DRAFT --submit--> AWAITING_CONFIRMATION --confirm--> AWAITING_APPROVAL --approve--> UNDER_CONTROL
       ^                       |                                  |
       +-------- return -------+----------------------------------+      (reason required, sign-offs cleared)

V_1.0 had none of this: one person filled every panel, typing any name and post into
a dialog; `status` was never written; مرجوع was wired to the ویرایش handler and did
nothing. Here the signer is the signed-in user, each step needs a different person,
every transition is one transaction under a row lock (two simultaneous confirms
cannot both win), and every step lands in the audit trail (`DocumentEvent`).

Approving a revision also supersedes the previous one (→ OBSOLETE) and queues the
PDF builds, so a printed QR code resolves to a status that is true.
"""
import logging

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.models import Capability
from apps.core.constants import DocumentEventKind, DocumentStatus, SignOffRole
from apps.core.exceptions import ConflictError

from .files import normalize_signature
from .models import Document, DocumentEvent, SignOff

logger = logging.getLogger("veye")

REASON_MAX_LENGTH = 1000

#: What each awaiting status is waiting for.
STEP_FOR_STATUS = {
    DocumentStatus.DRAFT: "submit",
    DocumentStatus.AWAITING_CONFIRMATION: "confirm",
    DocumentStatus.AWAITING_APPROVAL: "approve",
}
STEP_LABELS = {
    "submit": "ارسال برای تایید",
    "confirm": "تایید",
    "approve": "تصویب",
}
CAPABILITY_FOR_STEP = {
    "submit": Capability.CREATE_DOCUMENT,
    "confirm": Capability.CONFIRM_DOCUMENT,
    "approve": Capability.APPROVE_DOCUMENT,
}

SAME_PERSON_MESSAGES = {
    "confirm": "شما تدوین‌کننده این مستند هستید و نمی‌توانید آن را تایید کنید.",
    "approve": "شما در تدوین یا تایید این مستند نقش داشته‌اید و نمی‌توانید آن را تصویب کنید.",
    "return": "شما تدوین‌کننده این مستند هستید و نمی‌توانید آن را مرجوع کنید.",
}


def earlier_signers(document: Document, step: str) -> set[int]:
    """User ids that signed a step *before* `step` in the current round — the
    people barred from taking `step` too. Works on prefetched sign-offs (the
    register list computes this for every row without a query)."""
    by_role = {signoff.role: signoff for signoff in document.signoffs.all()}
    barred_roles = {
        "confirm": [SignOffRole.CREATER],
        "approve": [SignOffRole.CREATER, SignOffRole.CONFIRMER],
        "return": [SignOffRole.CREATER],
    }.get(step, [])
    return {
        by_role[role].signed_by_id for role in barred_roles if role in by_role and by_role[role].signed_by_id
    }


def next_step_for(document: Document, user) -> dict:
    """What `user` can do with `document` right now — the register's buttons.

    `blocked` is a Persian reason when the user holds the capability but is barred
    as a previous signer; the UI shows the button disabled with it as a tooltip."""
    result = {"step": STEP_FOR_STATUS.get(document.status), "can_act": False, "can_return": False, "blocked": None}
    step = result["step"]
    if step is None or user is None or not getattr(user, "is_authenticated", False):
        return result
    if step == "submit" and document.content_saved_at is None:
        result["step"] = None  # nothing to submit yet: the row still says تکمیل
        return result
    if not user.has_capability(CAPABILITY_FOR_STEP[step]):
        return result

    if user.pk in earlier_signers(document, step):
        result["blocked"] = SAME_PERSON_MESSAGES[step]
        return result
    result["can_act"] = True
    result["can_return"] = step in ("confirm", "approve")
    return result


# -- helpers ---------------------------------------------------------------


def _locked(document_id: int) -> Document:
    try:
        return Document.objects.select_for_update().get(pk=document_id)
    except Document.DoesNotExist:
        raise NotFound("مستند یافت نشد.")


def _require_status(document: Document, expected: str, verb: str) -> None:
    if document.status != expected:
        raise ConflictError(
            f"این مستند در وضعیت «{document.get_status_display()}» است و نمی‌توان آن را {verb}.",
            code="wrong_status",
            status=document.status,
        )


def _record(document, *, kind, to_status, user, reason="") -> DocumentEvent:
    event = DocumentEvent.objects.create(
        document=document,
        kind=kind,
        from_status=document.status,
        to_status=to_status,
        actor=user,
        actor_name=user.full_name,
        actor_title=user.title,
        reason=reason,
    )
    document.status = to_status
    document.save(update_fields=["status", "updated_at"])  # save(), not update(): the dashboard cache listens to post_save
    return event


def _delete_storage_on_commit(field_file) -> None:
    if field_file and field_file.name:
        name, storage = field_file.name, field_file.storage
        transaction.on_commit(lambda: storage.delete(name))


def _sign(document: Document, role: str, user, upload) -> SignOff:
    """Record `user`'s signature. The stored name and post come from the session,
    never from the request."""
    png = normalize_signature(upload)
    signoff = SignOff(
        document=document,
        role=role,
        name=user.full_name,
        position=user.title,
        signed_date=timezone.localdate(),
        signed_by=user,
    )
    signoff.signature.save("signature.png", png, save=False)
    try:
        signoff.save()
    except BaseException:
        signoff.signature.storage.delete(signoff.signature.name)  # don't orphan the file
        raise
    return signoff


def _no_double_signing(document: Document, step: str, user) -> None:
    if user.pk in earlier_signers(document, step):
        raise ConflictError(SAME_PERSON_MESSAGES[step], code="same_person")


# -- the transitions -------------------------------------------------------


@transaction.atomic
def submit(*, user, document_id: int, signature) -> Document:
    """تدوین: the author signs and sends the document for confirmation. The body
    is locked from here on (it is only editable while DRAFT)."""
    document = _locked(document_id)
    _require_status(document, DocumentStatus.DRAFT, "برای تایید ارسال کرد")
    if document.content_saved_at is None:
        raise ConflictError("ابتدا محتوای مستند را طراحی و ذخیره کنید.", code="content_missing")

    _sign(document, SignOffRole.CREATER, user, signature)
    _record(document, kind=DocumentEventKind.SUBMITTED, to_status=DocumentStatus.AWAITING_CONFIRMATION, user=user)
    return document


@transaction.atomic
def confirm(*, user, document_id: int, signature) -> Document:
    """تایید."""
    document = _locked(document_id)
    _require_status(document, DocumentStatus.AWAITING_CONFIRMATION, "تایید کرد")
    _no_double_signing(document, "confirm", user)

    _sign(document, SignOffRole.CONFIRMER, user, signature)
    _record(document, kind=DocumentEventKind.CONFIRMED, to_status=DocumentStatus.AWAITING_APPROVAL, user=user)
    return document


@transaction.atomic
def approve(*, user, document_id: int, signature) -> Document:
    """تصویب: the document goes under control, the revision it replaces becomes
    منسوخ, and the PDFs are (re)built — the new one so it exists, the old one so
    it stops saying «معتبر»."""
    document = _locked(document_id)
    _require_status(document, DocumentStatus.AWAITING_APPROVAL, "تصویب کرد")
    _no_double_signing(document, "approve", user)

    _sign(document, SignOffRole.APPROVER, user, signature)
    _record(document, kind=DocumentEventKind.APPROVED, to_status=DocumentStatus.UNDER_CONTROL, user=user)

    superseded = _supersede_previous(document, user)
    _queue_pdf_builds(user, document, superseded)
    return document


def _supersede_previous(document: Document, user) -> Document | None:
    previous_id = document.previous_revision_id
    if previous_id is None:
        return None
    previous = Document.objects.select_for_update().get(pk=previous_id)
    if previous.status != DocumentStatus.UNDER_CONTROL:
        return None  # already obsolete (or never issued): nothing to supersede
    _record(
        previous,
        kind=DocumentEventKind.SUPERSEDED,
        to_status=DocumentStatus.OBSOLETE,
        user=user,
        reason=f"جایگزین شده با بازنگری {document.revision_display} ({document.full_code})",
    )
    return previous


def _queue_pdf_builds(user, approved: Document, superseded: Document | None) -> None:
    """Build the approved revision's PDF; rebuild the superseded one's if it ever
    had one (a PDF that was never built can't be stale). Neither may fail the
    approval: they are queued on commit and a problem is only logged."""
    from apps.pdfgen import services as pdf
    from apps.pdfgen.models import PdfBuild, PdfKind

    targets = [approved.pk]
    if superseded is not None and PdfBuild.objects.filter(document=superseded, kind=PdfKind.OFFICIAL).exists():
        targets.append(superseded.pk)
    for document_id in targets:
        try:
            with transaction.atomic():
                pdf.request_build(user=user, document_id=document_id, kind=PdfKind.OFFICIAL)
        except ConflictError:
            # A build of this document is already running — it started before this
            # approval, so it may print the old validity. Rare; noted, not fatal.
            logger.warning("PDF build for document %s already running at approval", document_id)


@transaction.atomic
def return_document(*, user, document_id: int, reason: str) -> Document:
    """مرجوع: the reviewer sends the document back to DRAFT with a reason. All
    sign-offs are cleared — the author edits and the whole chain starts again —
    and the return is recorded in the audit trail."""
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": ["دلیل مرجوع کردن را بنویسید."]})
    if len(reason) > REASON_MAX_LENGTH:
        raise ValidationError({"reason": [f"دلیل نباید بیش از {REASON_MAX_LENGTH} نویسه باشد."]})

    document = _locked(document_id)
    step = STEP_FOR_STATUS.get(document.status)
    if step not in ("confirm", "approve"):
        raise ConflictError(
            f"این مستند در وضعیت «{document.get_status_display()}» است و نمی‌توان آن را مرجوع کرد.",
            code="wrong_status",
            status=document.status,
        )
    if not user.has_capability(CAPABILITY_FOR_STEP[step]):
        raise PermissionDenied("شما دسترسی لازم برای مرجوع کردن این مستند را ندارید.")
    _no_double_signing(document, "return", user)

    for signoff in document.signoffs.all():
        _delete_storage_on_commit(signoff.signature)
        signoff.delete()
    _record(document, kind=DocumentEventKind.RETURNED, to_status=DocumentStatus.DRAFT, user=user, reason=reason)
    return document
