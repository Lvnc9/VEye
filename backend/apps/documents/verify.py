"""The public verify page's data (Phase 5): what a printed QR code resolves to.

V_1.0's QR encoded a *predicted static S3 URL of the PDF*, built from a label's
text (poster_01.py:1094), so a printed copy kept "proving" validity forever — an
obsolete revision's QR still served the old PDF still saying معتبر. Here the QR
points at `/verify/{code}-{revision}`, which answers from the database *now*.

Public and unauthenticated (the person scanning is not signed in), so it is rate
limited per IP and discloses as little as it can: nothing at all about a document
that has not been approved beyond the fact that it is not yet valid, and never any
internal id.
"""
import re

from django.conf import settings
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.constants import GROUP_CODE_PREFIX, DocumentStatus, SignOffRole

from .models import Document

CODE_PATTERN = re.compile(r"^([A-Z]{2})-(\d{2,})-(\d{2})$")
PREFIX_TO_GROUP = {prefix: group for group, prefix in GROUP_CODE_PREFIX.items()}

NOT_FOUND = {
    "found": False,
    "detail": "مستندی با این کد یافت نشد. کد را بررسی کنید.",
}
STATES = {
    "valid": ("معتبر", "این مستند معتبر و تحت کنترل است."),
    "obsolete": ("منسوخ", "این مستند منسوخ شده و دیگر معتبر نیست. از آخرین بازنگری استفاده کنید."),
    "pending": ("در دست بررسی", "این مستند هنوز به تصویب نرسیده و معتبر نیست."),
}


def find_document(code: str) -> Document | None:
    match = CODE_PATTERN.match((code or "").strip().upper())
    if not match:
        return None
    prefix, number, revision = match.groups()
    group = PREFIX_TO_GROUP.get(prefix)
    if group is None:
        return None
    return Document.objects.filter(group=group, number=int(number), revision=int(revision)).first()


def verification(document: Document) -> dict:
    if document.status == DocumentStatus.UNDER_CONTROL:
        state = "valid"
    elif document.status == DocumentStatus.OBSOLETE:
        state = "obsolete"
    else:
        state = "pending"
    label, message = STATES[state]

    payload = {
        "found": True,
        "full_code": document.full_code,
        "revision_display": document.revision_display,
        "state": state,
        "state_label": label,
        "message": message,
    }
    if state == "pending":
        return payload  # nothing else about an unapproved document is public

    payload["title"] = document.title
    payload["group_label"] = document.get_group_display()
    payload["signers"] = [
        {"role_label": SignOffRole(signoff.role).label, "name": signoff.name, "position": signoff.position,
         "signed_date": signoff.signed_date}
        for signoff in sorted(
            document.signoffs.all(),
            key=lambda s: [SignOffRole.CREATER, SignOffRole.CONFIRMER, SignOffRole.APPROVER].index(s.role),
        )
    ]
    payload["current_revision"] = None
    if state == "obsolete":
        # Point whoever holds an old printed copy at the revision in force.
        current = (
            Document.objects.filter(
                group=document.group,
                number=document.number,
                revision__gt=document.revision,
                status=DocumentStatus.UNDER_CONTROL,
            )
            .order_by("-revision")
            .first()
        )
        if current is not None:
            payload["current_revision"] = {"full_code": current.full_code, "revision_display": current.revision_display}
    return payload


class VerifyView(APIView):
    authentication_classes = []  # public: never look at (or be confused by) cookies
    permission_classes = [AllowAny]

    # A callable, so the rate is read per request (and can be overridden in tests).
    @method_decorator(
        ratelimit(key="ip", rate=lambda group, request: settings.VERIFY_RATELIMIT_RATE, method="GET", block=True)
    )
    def get(self, request, code):
        document = find_document(code)
        if document is None:
            return Response(NOT_FOUND, status=404)
        response = Response(verification(document))
        # A verdict must never be served stale by a cache between the scanner and us.
        response["Cache-Control"] = "no-store"
        return response
