from django.db.models import Case, CharField, Exists, OuterRef, Prefetch, Q, Subquery, Value, When
from django.db.models.functions import Cast, Concat
from django.http import FileResponse, Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Capability
from apps.core.constants import (
    GROUP_CODE_PREFIX,
    DocumentCategory,
    DocumentGroup,
    DocumentStatus,
    SectionType,
)
from apps.core.pagination import DefaultPagination
from apps.core.permissions import HasCapability, capability_required
from apps.core.text import normalize_letters, normalize_search_term

from . import content as content_service
from . import services, workflow
from .content_serializers import ContentInputSerializer, content_payload, file_payload
from apps.pdfgen.models import PdfBuild, PdfKind

from .models import Document, DocumentFile, Section
from .serializers import (
    DocumentCreateSerializer,
    DocumentDetailSerializer,
    DocumentEventSerializer,
    DocumentSerializer,
)

_official_build = PdfBuild.objects.filter(document=OuterRef("pk"), kind=PdfKind.OFFICIAL)


def _zero_pad_2(field: str):
    """SQL for f"{value:02d}". Not LPad: LPad *truncates* to the target length
    (Postgres lpad('100', 2, '0') is '10'), which would mangle numbers >= 100
    that the Python-side `code` property renders in full."""
    as_text = Cast(field, CharField())
    return Case(
        When(**{f"{field}__lt": 10}, then=Concat(Value("0"), as_text)),
        default=as_text,
        output_field=CharField(),
    )


def _full_code_expression():
    """SQL equivalent of Document.full_code, so search can match the printed
    identifier ("PO-01-01") — including its revision part, which V_1.0's search
    could not: it matched the raw stored "0-1" rather than the displayed "01"
    (documents_01.py:872)."""
    prefix = Case(
        *[When(group=group, then=Value(prefix)) for group, prefix in GROUP_CODE_PREFIX.items()],
        output_field=CharField(),
    )
    return Concat(
        prefix,
        Value("-"),
        _zero_pad_2("number"),
        Value("-"),
        _zero_pad_2("revision"),
        output_field=CharField(),
    )


def _labels_containing(choices, term: str) -> list[str]:
    return [value for value, label in choices if term in normalize_letters(str(label)).casefold()]


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
        ).annotate(
            has_next_revision=Exists(Document.objects.filter(previous_revision=OuterRef("pk"))),
            # State of the issued PDF, for the register's چاپ button. A subquery
            # on the build table — no PDF is opened or rendered to answer this.
            pdf_status_value=Subquery(_official_build.values("status")[:1]),
            pdf_built_at_value=Subquery(_official_build.values("built_at")[:1]),
        )

        # Exact-match filters. An unknown value simply matches nothing rather
        # than erroring — it can only come from a stale link or a hand-edited URL.
        for param, allowed in (
            ("group", DocumentGroup.values),
            ("category", DocumentCategory.values),
            ("status", DocumentStatus.values),
        ):
            value = params.get(param)
            if value:
                qs = qs.filter(**{param: value}) if value in allowed else qs.none()

        term = normalize_search_term(params.get("search", ""))
        if term:
            qs = qs.annotate(full_code_text=_full_code_expression()).filter(
                Q(title__icontains=term)
                | Q(full_code_text__icontains=term)
                | Q(category__in=_labels_containing(DocumentCategory.choices, term))
                | Q(group__in=_labels_containing(DocumentGroup.choices, term))
            )

        return qs

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
