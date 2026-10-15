"""One search box for the whole app (Phase 22, ⌘K). Each provider answers for one kind of record with the
same visibility the record's own list uses — nothing reaches the palette that its screen would hide — and at
most `LIMIT` hits. Text is compared after `normalize_search_term` on both sides (Arabic ي/ك, digits, case),
in SQL, so it does not matter whether a field was stored normalised."""
import re

from django.db.models import Q

from apps.core.text import normalize_search_term
from apps.organization.queries import normalized_name_expression

LIMIT = 5


def _matches(queryset, term: str, *fields: str):
    """Rows where any of `fields`, normalised in SQL, contains the (already normalised) term."""
    query = Q()
    for index, field in enumerate(fields):
        alias = f"_search_{index}"
        queryset = queryset.annotate(**{alias: normalized_name_expression(field)})
        query |= Q(**{f"{alias}__icontains": term})
    return queryset.filter(query)


def _by_code(raw: str, prefix: str) -> int | None:
    """`NC-0042`, `nc-42` or `42` → 42 for a record id typed into the box."""
    match = re.fullmatch(rf"(?:{prefix}-?)?0*(\d{{1,9}})", raw.strip(), flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def documents(request, raw, term):
    from apps.documents import queries
    from apps.documents.models import Document

    rows = queries.search(Document.objects.all(), raw).order_by("-updated_at", "-id")[:LIMIT]
    return [
        {"id": d.pk, "title": f"{d.full_code} — {d.title}", "subtitle": d.get_status_display(), "url": f"/documents/{d.pk}/edit"}
        for d in rows
    ]


def projects(request, raw, term):
    from apps.projects.access import visible_projects

    rows = visible_projects(request).filter(name_key__icontains=term).order_by("-updated_at", "-id")[:LIMIT]
    return [{"id": p.pk, "title": p.name, "subtitle": p.get_status_display(), "url": f"/projects/{p.pk}"} for p in rows]


def _quality(queryset, raw, term, prefix, url, *fields):
    query_set = _matches(queryset, term, *fields)
    number = _by_code(raw, prefix)
    if number is not None:
        query_set = query_set | queryset.filter(pk=number)
    rows = query_set.distinct().order_by("-id")[:LIMIT]
    return [
        {"id": row.pk, "title": f"{row.code} — {row.title}", "subtitle": row.get_status_display(), "url": url.format(id=row.pk)}
        for row in rows
    ]


def nonconformances(request, raw, term):
    from apps.quality.access import visible_nonconformances

    return _quality(visible_nonconformances(request), raw, term, "NC", "/quality/{id}", "title", "description")


def audits(request, raw, term):
    from apps.quality.access import visible_audits

    return _quality(visible_audits(request), raw, term, "AU", "/quality/audits/{id}", "title")


def risks(request, raw, term):
    from apps.quality.access import visible_risks

    return _quality(visible_risks(request), raw, term, "RK", "/quality/risks/{id}", "title", "description")


def announcements(request, raw, term):
    from apps.announcements.access import visible_announcements

    # A withdrawn notice stays readable to its author on its own screen, but is not something to find here.
    current = visible_announcements(request).filter(withdrawn_at__isnull=True)
    rows = _matches(current, term, "title", "body").order_by("-id")[:LIMIT]
    return [{"id": a.pk, "title": a.title, "subtitle": a.author.full_name, "url": "/announcements"} for a in rows]


def people(request, raw, term):
    from apps.accounts.models import User
    from apps.organization.queries import search_people

    rows = search_people(User.objects.filter(is_active=True, is_developer=False), raw).order_by("full_name")[:LIMIT]
    return [{"id": u.pk, "title": u.full_name, "subtitle": u.title, "url": f"/organization?person={u.pk}"} for u in rows]


def org_nodes(request, raw, term):
    from apps.organization.models import OrgNode

    rows = OrgNode.objects.filter(is_active=True, name_key__icontains=term).order_by("depth", "name")[:LIMIT]
    return [{"id": n.pk, "title": n.name, "subtitle": n.get_kind_display(), "url": f"/organization?node={n.pk}"} for n in rows]


#: In the order the palette shows them.
PROVIDERS = (
    ("documents", "مستندات", documents),
    ("projects", "پروژه‌ها", projects),
    ("nonconformances", "عدم‌انطباق‌ها", nonconformances),
    ("audits", "ممیزی‌ها", audits),
    ("risks", "ریسک‌ها", risks),
    ("announcements", "اطلاعیه‌ها", announcements),
    ("people", "افراد", people),
    ("org_nodes", "ساختار سازمان", org_nodes),
)


def search_all(request, raw: str) -> list[dict]:
    term = normalize_search_term(raw)
    if len(term) < 2:
        return []
    groups = []
    for kind, label, provider in PROVIDERS:
        items = provider(request, raw, term)
        if items:
            groups.append({"type": kind, "label": label, "items": items})
    return groups
