from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import DefaultPagination
from apps.documents.models import Document

from . import services
from .access import can_view_coverage
from .models import ReadAcknowledgment


def _document_brief(document) -> dict:
    return {
        "id": document.pk,
        "full_code": document.full_code,
        "title": document.title,
        "status": document.status,
        "group_label": document.get_group_display(),
    }


class PendingView(APIView):
    """«برای مطالعه»: the approved documents I have been asked to read and have not yet acknowledged."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(services.pending_for(request.user), request, view=self)
        return paginator.get_paginated_response(
            [{"document": _document_brief(row.document), "asked_at": row.created_at} for row in page]
        )


class DocumentReadingView(APIView):
    """For the designer header: am I asked to read this revision (and have I), and may I see the coverage."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        document = get_object_or_404(Document, pk=pk)
        mine = ReadAcknowledgment.objects.filter(document=document, user=request.user).first()
        stats = ReadAcknowledgment.objects.filter(document=document).aggregate(
            total=Count("id"), acknowledged=Count("id", filter=Q(acknowledged_at__isnull=False))
        )
        can_view = can_view_coverage(request, document)
        return Response(
            {
                "mine": {"acknowledged_at": mine.acknowledged_at} if mine else None,
                "can_view_coverage": can_view,
                "total": stats["total"] if can_view else None,
                "acknowledged": stats["acknowledged"] if can_view else None,
            }
        )


class AcknowledgeView(APIView):
    """«مطالعه کردم»."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        row = services.acknowledge(user=request.user, document_id=pk)
        return Response({"acknowledged_at": row.acknowledged_at})


class CoverageView(APIView):
    """Who has read a revision and who has not, grouped by where they were placed when it was distributed."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        document = get_object_or_404(Document, pk=pk)
        if not can_view_coverage(request, document):
            raise PermissionDenied("فقط نویسندگان این مستند و دارندگان دسترسی گزارش‌ها پوشش مطالعه را می‌بینند.")
        rows = ReadAcknowledgment.objects.filter(document=document).select_related("user")
        groups: dict[str, list] = {}
        for row in rows:
            groups.setdefault(row.node_name, []).append(
                {"name": row.user.full_name, "title": row.user.title, "acknowledged_at": row.acknowledged_at}
            )
        total = len(rows)
        acknowledged = sum(1 for row in rows if row.acknowledged_at)
        return Response(
            {
                "document": _document_brief(document),
                "total": total,
                "acknowledged": acknowledged,
                "percent": round(100 * acknowledged / total) if total else None,
                "groups": [{"node_name": name, "people": people} for name, people in groups.items()],
            }
        )
