from django.conf import settings
from django.http import FileResponse, Http404
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, Throttled, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Capability
from apps.core.exceptions import ConflictError
from apps.core.permissions import HasCapability
from apps.documents import authority
from apps.documents.models import Document

from apps.documents.content_serializers import ContentInputSerializer

from . import bulk, live_preview, services, storage
from .models import PdfBuild, PdfKind, PdfStatus


def _kind(value: str) -> str:
    if value not in PdfKind.values:
        raise NotFound()
    return value


def build_payload(request, document_id: int, kind: str, build: PdfBuild | None) -> dict:
    """The state of one PDF as the UI needs it. `status` is "none" before the
    first request. A file can be downloadable while a *re*build runs or after
    one fails, so `download_url` follows the file, not the status."""
    has_file = bool(build and build.has_file)
    return {
        "kind": kind,
        "status": build.status if build else "none",
        "status_label": build.get_status_display() if build else "ساخته نشده",
        "requested_at": build.requested_at if build else None,
        "built_at": build.built_at if build else None,
        "size": build.size if has_file else None,
        "error": build.error if build else "",
        # A BUILDING row past the hard time limit no longer blocks a new request.
        "stale": bool(build and build.is_stale),
        "download_url": (
            request.build_absolute_uri(
                reverse("pdf-download", kwargs={"document_id": document_id, "kind": kind})
            )
            if has_file
            else None
        ),
    }


class PdfBuildView(APIView):
    """GET the state of a document's PDF; POST to (re)build it.

    `kind` is `official` (the issued PDF of a finalized revision) or `preview`
    (a watermarked copy of any revision). Building is an explicit action that
    queues a Celery task and returns 202 at once — the register list, and this
    GET, never render anything.
    """

    permission_classes = [IsAuthenticated, HasCapability]
    write_capability = Capability.PRINT_DOCUMENT

    def get(self, request, document_id, kind):
        kind = _kind(kind)
        if not Document.objects.filter(pk=document_id).exists():
            raise NotFound("مستند یافت نشد.")
        build = services.get_build(document_id, kind)
        return Response(build_payload(request, document_id, kind, build))

    def post(self, request, document_id, kind):
        kind = _kind(kind)
        build = services.request_build(user=request.user, document_id=document_id, kind=kind)
        return Response(
            build_payload(request, document_id, kind, build), status=status.HTTP_202_ACCEPTED
        )


class PdfDownloadView(APIView):
    """Serve the built file. Authenticated like every other read — the PDF is
    never a public media URL. Opens inline (for viewing/printing in the browser);
    `?download=1` forces a save dialog."""

    permission_classes = [IsAuthenticated]

    def get(self, request, document_id, kind):
        kind = _kind(kind)
        try:
            document = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            raise NotFound("مستند یافت نشد.")
        build = services.get_build(document_id, kind)
        if build is None or not build.has_file:
            raise Http404("PDF هنوز ساخته نشده است.")
        try:
            handle = storage.absolute_path(build.path).open("rb")
        except (FileNotFoundError, ValueError):
            raise Http404("فایل PDF یافت نشد.")

        response = FileResponse(
            handle,
            content_type="application/pdf",
            as_attachment=request.query_params.get("download") == "1",
            # V_1.0 named the file "<title>-<code>.pdf".
            filename=f"{document.title}-{document.full_code}.pdf",
        )
        response["Cache-Control"] = "private, no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class BulkPrintPreflightView(APIView):
    """GET /documents/bulk-print/preflight/ — what a bulk print would contain.

    Selection: `?ids=1,2,3`, or the register's filters (`search`, `group`,
    `category`, `status`; none = everything). Says how many PDFs are ready and which
    documents are not, with the reason. Reads only — nothing is built or zipped."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        plan = bulk.make_plan(bulk.selection(request.query_params))
        return Response(
            {
                "total": plan.total,
                "cap": plan.cap,
                "truncated": plan.truncated,
                "ready": len(plan.ready),
                "missing": plan.missing,
            }
        )


class BulkPrintView(APIView):
    """GET /documents/bulk-print/ — the ZIP of the ready, already-built official PDFs.

    Same selection as the preflight. Never renders. Capped at
    BULK_PRINT_MAX_FILES (the first N by printed code). 409 `nothing_to_print` when
    the selection has no built PDF. A GET so the browser can simply navigate to it
    with its cookie; the response is `Cache-Control: private, no-store`."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        plan = bulk.make_plan(bulk.selection(request.query_params))
        if not plan.ready:
            raise ConflictError(
                "هیچ PDF ساخته‌شده‌ای در این انتخاب نیست. ابتدا PDF مستندات را بسازید.",
                code="nothing_to_print",
                missing=len(plan.missing),
            )
        response = FileResponse(
            bulk.build_zip(plan),
            as_attachment=True,
            filename=f"documents-{timezone.localdate().isoformat()}.zip",
            content_type="application/zip",
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Bulk-Print-Count"] = str(len(plan.ready))
        response["X-Bulk-Print-Missing"] = str(len(plan.missing))
        return response


class LivePreviewView(APIView):
    """`POST /documents/{id}/live-preview/` — the designer's live paper (Phase 12).

    Body `{body?, known_hashes?}`. With `body` (the same JSON a content PUT
    takes) the pages show those unsaved edits — for someone who may edit the
    draft; without it, the stored document. Answers
    `{pages: [{hash, image?}], page_count, truncated}`; nothing is stored, no
    PdfBuild row, no file. Rate-limited per user (LIVE_PREVIEW_RATELIMIT_RATE)."""

    permission_classes = [IsAuthenticated]

    @method_decorator(
        ratelimit(key="user", rate=lambda group, request: settings.LIVE_PREVIEW_RATELIMIT_RATE, method="POST", block=False)
    )
    def post(self, request, document_id):
        if getattr(request, "limited", False):
            raise Throttled(detail="پیش‌نمایش بیش از حد درخواست شد؛ چند لحظه صبر کنید.")
        document = Document.objects.filter(pk=document_id).first()
        if document is None:
            raise NotFound("مستند یافت نشد.")

        known = request.data.get("known_hashes") or []
        if not isinstance(known, list):
            raise ValidationError({"known_hashes": ["فهرست نامعتبر است."]})
        known = {value for value in known[: live_preview.MAX_PAGES * 4] if isinstance(value, str)}

        body = request.data.get("body")
        if body is None:
            pdf = live_preview.render_stored(document.pk)
        else:
            if not authority.for_request(request).can_author(document):
                raise PermissionDenied("دسترسی ویرایش این مستند را ندارید.")
            serializer = ContentInputSerializer(data=body, context={"document": document})
            serializer.is_valid(raise_exception=True)
            pdf = live_preview.render_unsaved(user=request.user, document_id=document.pk, data=serializer.validated_data)

        result = live_preview.rasterise(pdf, known)
        response = Response({"pages": result.pages, "page_count": result.page_count, "truncated": result.truncated})
        response["Cache-Control"] = "no-store"
        return response
