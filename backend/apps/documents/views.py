from django.db.models import Exists, OuterRef, Prefetch
from django.http import FileResponse, Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Capability
from apps.core.constants import SectionType
from apps.core.pagination import DefaultPagination
from apps.core.permissions import HasCapability, capability_required

from . import content as content_service
from . import queries, services, workflow
from .content_serializers import ContentInputSerializer, content_payload, file_payload
from .models import Document, DocumentFile, Section
from .serializers import (
    DocumentCreateSerializer,
    DocumentDetailSerializer,
    DocumentEventSerializer,
    DocumentSerializer,
)


class DocumentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """The document register (ساخت مستند).

    Reads are plain Postgres queries — the register never opens or renders a
    PDF. Anyone signed in can browse it; registering documents and starting new
    revisions needs the create_document capability (تدوین).
    """

    permission_classes = [IsAuthenticated, HasCapability]
    write_capability = Capability.CREATE_DOCUMENT
    pagination_class = DefaultPagination

    def get_queryset(self):
        params = self.request.query_params
        qs = Document.objects.prefetch_related(
            "signoffs",
            # The register's حسابکش / پاسخ خواه / پاسخگو columns are read from the
            # Responsibilities section; fetching it here keeps that to two queries
            # for the whole page rather than two per row.
            Prefetch(
                "sections",
                queryset=Section.objects.filter(type=SectionType.RESPONSIBILITIES)
                .order_by("position", "id")
                .prefetch_related("responsibility_rows"),
                to_attr="responsibility_sections",
            ),
        ).annotate(has_next_revision=Exists(Document.objects.filter(previous_revision=OuterRef("pk"))))
        # State of the issued PDF, for the register's چاپ button (subqueries only).
        qs = queries.with_official_pdf(qs)

        return queries.apply_filters(qs, params)

    def get_serializer_class(self):
        if self.action == "create":
            return DocumentCreateSerializer
        return DocumentDetailSerializer if self.action == "retrieve" else DocumentSerializer

    def create(self, request, *args, **kwargs):
        serializer = DocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = services.create_document(user=request.user, **serializer.validated_data)
        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def revise(self, request, pk=None):
        self.get_object()  # 404 for an unknown id before doing any work
        document = services.create_revision(user=request.user, document_id=pk)
        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    # -- the sign-off workflow (Phase 5) -------------------------------------
    #
    # Each step needs its own capability (the viewset's class-level one is the
    # authoring one), so they carry their own permission classes. Signing is a
    # multipart POST: `signature` is the PNG exported from the web pad. Name, post
    # and date come from the session.

    def _workflow_response(self, document, request):
        # Re-read through the register queryset so the response carries the same
        # annotations and prefetches as a list row.
        fresh = self.get_queryset().get(pk=document.pk)
        return Response(DocumentDetailSerializer(fresh, context={"request": request}).data)

    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser],
        permission_classes=[IsAuthenticated, capability_required(Capability.CREATE_DOCUMENT)],
    )
    def submit(self, request, pk=None):
        document = workflow.submit(user=request.user, document_id=pk, signature=request.FILES.get("signature"))
        return self._workflow_response(document, request)

    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser],
        permission_classes=[IsAuthenticated, capability_required(Capability.CONFIRM_DOCUMENT)],
    )
    def confirm(self, request, pk=None):
        document = workflow.confirm(user=request.user, document_id=pk, signature=request.FILES.get("signature"))
        return self._workflow_response(document, request)

    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser],
        permission_classes=[IsAuthenticated, capability_required(Capability.APPROVE_DOCUMENT)],
    )
    def approve(self, request, pk=None):
        document = workflow.approve(user=request.user, document_id=pk, signature=request.FILES.get("signature"))
        return self._workflow_response(document, request)

    @action(detail=True, methods=["post"], url_path="return", permission_classes=[IsAuthenticated])
    def return_to_draft(self, request, pk=None):
        """مرجوع. The needed capability depends on the state (the confirmer returns
        while awaiting confirmation, the approver while awaiting approval), so the
        service checks it."""
        document = workflow.return_document(
            user=request.user, document_id=pk, reason=request.data.get("reason", "")
        )
        return self._workflow_response(document, request)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        """The audit trail: who submitted, confirmed, approved, returned (and why)."""
        document = self.get_object()
        events = document.events.all()
        return Response(DocumentEventSerializer(events, many=True).data)

    # -- the designer -------------------------------------------------------

    @action(detail=True, methods=["get", "put"], url_path="content")
    def content(self, request, pk=None):
        """GET the whole body for the designer; PUT to save it.

        Writes need the create_document capability (تدوین) — enforced by
        HasCapability for the non-safe method — and a draft document.
        """
        document = self.get_object()
        if request.method == "GET":
            return Response(content_payload(document, request))

        serializer = ContentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        saved = content_service.save_content(user=request.user, document_id=document.pk, data=serializer.validated_data)
        return Response(content_payload(saved, request))

    @action(detail=True, methods=["post"], url_path="files", parser_classes=[MultiPartParser])
    def upload_file(self, request, pk=None):
        document = self.get_object()
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": ["فایلی ارسال نشده است."]})
        record, created = content_service.add_file(user=request.user, document_id=document.pk, upload=upload)
        return Response(
            file_payload(document, record, request),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path=r"files/(?P<file_id>\d+)/download")
    def download_file(self, request, pk=None, file_id=None):
        """Attachments are served through the API, not as public media URLs:
        V_1.0's files sat in a public bucket, so anyone holding a link could read
        them. Here every download needs a signed-in user."""
        document = self.get_object()
        try:
            record = DocumentFile.objects.get(pk=file_id, document=document)
            handle = record.file.open("rb")
        except (DocumentFile.DoesNotExist, FileNotFoundError, ValueError):
            raise Http404
        return FileResponse(handle, as_attachment=True, filename=record.original_name)

    @action(detail=True, methods=["get", "post", "delete"], url_path="logo", parser_classes=[MultiPartParser])
    def logo(self, request, pk=None):
        document = self.get_object()

        if request.method == "GET":
            if not document.logo:
                raise Http404
            try:
                handle = document.logo.open("rb")
            except FileNotFoundError:
                raise Http404
            response = FileResponse(handle, content_type="image/png")
            response["Cache-Control"] = "private, max-age=3600"
            return response

        if request.method == "POST":
            upload = request.FILES.get("logo")
            if upload is None:
                raise ValidationError({"logo": ["تصویری ارسال نشده است."]})
            document = content_service.set_logo(document_id=document.pk, upload=upload)
        else:
            document = content_service.remove_logo(document_id=document.pk)
        return Response(content_payload(document, request))
