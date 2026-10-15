from django.conf import settings
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .providers import search_all


class SearchView(APIView):
    """GET /search/?q= — the ⌘K palette (Phase 22): up to five hits per kind of record, each kind scoped
    exactly as its own screen scopes it. Fewer than two letters return nothing (no wildcard listing)."""

    permission_classes = [IsAuthenticated]

    @method_decorator(
        ratelimit(key="user", rate=lambda group, request: settings.SEARCH_RATELIMIT_RATE, method="GET", block=True)
    )
    def get(self, request):
        raw = (request.query_params.get("q") or "").strip()[:100]
        return Response({"query": raw, "groups": search_all(request, raw)})
