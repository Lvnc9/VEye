from django.http import FileResponse, Http404
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Capability
from apps.core.permissions import HasCapability
from apps.documents.models import Document

from . import services, storage
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
