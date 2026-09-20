"""The Document History screen (سوابق مستندات, Phase 6).

V_1.0's «Document History» button was dead (`main.py:909` called a handler with no
arguments and raised TypeError), so this is a new feature with two read-only views:

* **revisions** — every revision of every document, newest family first, with its
  status, signers and PDF state; filterable, and narrowable to one family's chain.
* **activity** — the workflow audit trail across all documents (who submitted,
  confirmed, approved, returned or superseded what, and why).

Both are plain Postgres reads open to any signed-in user (like the register). Neither
opens or renders a PDF; the PDF column only reads the build table.
"""
import re
from datetime import timedelta

from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.core.constants import (
    GROUP_CODE_PREFIX,
    DocumentEventKind,
    SignOffRole,
)
from apps.core.pagination import DefaultPagination
from apps.core.text import normalize_search_term

from . import queries
from .models import Document, DocumentEvent, SignOff

FAMILY_PATTERN = re.compile(r"^([A-Z]{2})-(\d{2,})$")
PREFIX_TO_GROUP = {prefix: group for group, prefix in GROUP_CODE_PREFIX.items()}
MAX_DAYS = 3650


def _int_param(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class RevisionHistorySerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True)
    revision_display = serializers.CharField(read_only=True)
    full_code = serializers.CharField(read_only=True)
    group_label = serializers.CharField(source="get_group_display", read_only=True)
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    signoffs = serializers.SerializerMethodField()
    pdf_status = serializers.SerializerMethodField()
    pdf_built_at = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id", "code", "revision", "revision_display", "full_code", "title",
            "group", "group_label", "category", "category_label",
            "status", "status_label", "signoffs", "pdf_status", "pdf_built_at",
            "content_saved_at", "created_at",
        ]
        read_only_fields = fields

    def get_signoffs(self, obj: Document):
        by_role = {s.role: s for s in obj.signoffs.all()}
        return {
            role: (
                {"name": by_role[role].name, "position": by_role[role].position,
                 "signed_date": by_role[role].signed_date}
                if role in by_role
                else None
            )
            for role in SignOffRole.values
        }

    def get_pdf_status(self, obj: Document) -> str:
        return obj.pdf_status_value or "none"

    def get_pdf_built_at(self, obj: Document):
        return obj.pdf_built_at_value


class RevisionHistoryView(ListAPIView):
    """GET /history/revisions/ — every revision of every document.

    Filters: `search` (same box as the register), `group`, `category`, `status`
    (an unknown value matches nothing), `family` (e.g. `PR-01`: the whole revision
    chain of one document). Ordered by the printed family code (FR, PO, PR, WI…), newest revision first.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = DefaultPagination
    serializer_class = RevisionHistorySerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = Document.objects.prefetch_related(
            Prefetch("signoffs", queryset=SignOff.objects.order_by("id"))
        )
        qs = queries.with_official_pdf(qs)

        qs = queries.apply_filters(qs, params)

        family = params.get("family", "").strip().upper()
        if family:
            match = FAMILY_PATTERN.match(family)
            group = PREFIX_TO_GROUP.get(match.group(1)) if match else None
            qs = qs.filter(group=group, number=int(match.group(2))) if group else qs.none()

        return qs.annotate(family_prefix=queries.prefix_expression()).order_by("family_prefix", "number", "-revision")


class ActivityDocumentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_code = serializers.CharField()
    title = serializers.CharField()


class ActivityEventSerializer(serializers.ModelSerializer):
    document = ActivityDocumentSerializer(read_only=True)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    from_status_label = serializers.CharField(source="get_from_status_display", read_only=True)
    to_status_label = serializers.CharField(source="get_to_status_display", read_only=True)

    class Meta:
        model = DocumentEvent
        fields = [
            "id", "document", "kind", "kind_label", "from_status", "from_status_label",
            "to_status", "to_status_label", "actor_name", "actor_title", "reason", "created_at",
        ]
        read_only_fields = fields


class ActivityFeedView(ListAPIView):
    """GET /history/activity/ — the audit trail across all documents, newest first.

    Filters: `kind` (unknown → nothing), `document` (a document id), `q` (title /
    printed code of the document, same search as the register), `actor` (name
    contains), `days` (only the last N days).
    """

    permission_classes = [IsAuthenticated]
    pagination_class = DefaultPagination
    serializer_class = ActivityEventSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = DocumentEvent.objects.select_related("document")

        kind = params.get("kind")
        if kind:
            qs = qs.filter(kind=kind) if kind in DocumentEventKind.values else qs.none()

        if params.get("document"):
            document_id = _int_param(params["document"])
            qs = qs.filter(document_id=document_id) if document_id is not None else qs.none()

        if params.get("q", "").strip():
            qs = qs.filter(document__in=queries.search(Document.objects.all(), params["q"]).values("pk"))

        actor = normalize_search_term(params.get("actor", ""))
        if actor:
            qs = qs.filter(actor_name__icontains=actor)

        if params.get("days"):
            days = _int_param(params["days"])
            if days is None or days < 1:
                return qs.none()
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=min(days, MAX_DAYS)))

        return qs.order_by("-created_at", "-id")
