"""Query helpers shared by the register and the history screen.

Extracted from views.py (Phase 6) so both screens search identically: by title,
by the *printed* code (including its revision part, which V_1.0's search could not
match), and by category / group label — with Arabic/Persian letters and digits
normalised.
"""
from django.db.models import Case, CharField, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Cast, Concat

from apps.core.constants import GROUP_CODE_PREFIX, DocumentCategory, DocumentGroup
from apps.core.text import normalize_letters, normalize_search_term


def zero_pad_2(field: str):
    """SQL for f"{value:02d}". Not LPad: LPad *truncates* to the target length
    (Postgres lpad('100', 2, '0') is '10'), which would mangle numbers >= 100
    that the Python-side `code` property renders in full."""
    as_text = Cast(field, CharField())
    return Case(
        When(**{f"{field}__lt": 10}, then=Concat(Value("0"), as_text)),
        default=as_text,
        output_field=CharField(),
    )


def prefix_expression():
    """SQL for the code prefix (PO / PR / WI / FR) — group *names* sort differently
    from the codes people read, so ordering by group would look shuffled."""
    return Case(
        *[When(group=group, then=Value(prefix)) for group, prefix in GROUP_CODE_PREFIX.items()],
        output_field=CharField(),
    )


def full_code_expression():
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
        zero_pad_2("number"),
        Value("-"),
        zero_pad_2("revision"),
        output_field=CharField(),
    )


def labels_containing(choices, term: str) -> list[str]:
    return [value for value, label in choices if term in normalize_letters(str(label)).casefold()]




def search(queryset, raw_term: str):
    """Filter a Document queryset by the register's free-text search box."""
    term = normalize_search_term(raw_term or "")
    if not term:
        return queryset
    return queryset.annotate(full_code_text=full_code_expression()).filter(
        Q(title__icontains=term)
        | Q(full_code_text__icontains=term)
        | Q(category__in=labels_containing(DocumentCategory.choices, term))
        | Q(group__in=labels_containing(DocumentGroup.choices, term))
    )


def with_official_pdf(queryset):
    """Annotate `pdf_status_value` / `pdf_built_at_value` (the issued PDF's state)
    with subqueries on the build table — no PDF is opened to answer this, and no
    query per row is added. Shared by the register and the history screen."""
    from apps.pdfgen.models import PdfBuild, PdfKind

    build = PdfBuild.objects.filter(document=OuterRef("pk"), kind=PdfKind.OFFICIAL)
    return queryset.annotate(
        pdf_status_value=Subquery(build.values("status")[:1]),
        pdf_built_at_value=Subquery(build.values("built_at")[:1]),
    )
