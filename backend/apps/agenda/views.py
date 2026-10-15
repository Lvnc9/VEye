from datetime import date

from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .items import gather, leads_anything

MAX_DAYS = 62


def _date(request, name) -> date:
    raw = request.query_params.get(name, "")
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValidationError({name: ["تاریخ را به شکل YYYY-MM-DD بفرستید."]})


class AgendaView(APIView):
    """GET /agenda/?from=&to=&team=1 — my dated work in a window of at most 62 days (a Jalali month and its
    edges); `team=1` adds the leave of the people under the nodes I lead (ignored for someone who leads
    nothing)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        start, end = _date(request, "from"), _date(request, "to")
        if end < start:
            raise ValidationError({"to": ["پایان بازه پیش از آغاز آن است."]})
        if (end - start).days >= MAX_DAYS:
            raise ValidationError({"to": [f"بازه نباید بیش از {MAX_DAYS} روز باشد."]})
        is_lead = leads_anything(request)
        team = request.query_params.get("team") in ("1", "true") and is_lead
        return Response({"from": start, "to": end, "is_lead": is_lead, "team": team, "items": gather(request, start, end, team=team)})
