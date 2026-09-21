"""Query helpers for finding people.

`User.full_name` is stored raw — the V_1.0 importer deliberately keeps Arabic yeh/kaf
(docs/07-known-gaps item 16) — so a plain `full_name__icontains` misses «علی رضايي» when
someone types «رضایی». Rather than add a normalised copy of the column (which needs a
backfill, and a data migration this project avoids), the name is normalised *in SQL* with
translate() at query time, the same idea documents/queries.py uses to search a printed code
that is never stored. A functional index, if it is ever needed, is a schema migration.

The character tables come from core.text's own functions, and a test compares the SQL with
`normalize_search_term` on a corpus, so the two cannot drift apart.
"""
from django.db.models import CharField, Func, Value
from django.db.models.functions import Lower

from apps.core.text import normalize_letters, normalize_search_term, to_latin_digits

#: Python's `\s` (what normalize_title collapses) is Unicode-aware; Postgres's is not — a no-break
#: space pasted from Word would normalise differently in SQL. So the SQL class spells out the
#: Unicode White_Space characters. SearchExpressionTests compares the two on such a name.
_WHITESPACE = r"[\s\u001c-\u001f\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+"
_LETTERS_FROM = "يىك"
_DIGITS_FROM = "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩"


class _Translate(Func):
    function = "translate"
    output_field = CharField()


class _RegexpReplace(Func):
    function = "regexp_replace"
    output_field = CharField()


def normalized_name_expression(field: str = "full_name"):
    """SQL equivalent of `normalize_search_term(<field>)`: unified letterforms, ASCII digits,
    whitespace collapsed and trimmed, case-folded."""
    text = _Translate(field, Value(_LETTERS_FROM), Value(normalize_letters(_LETTERS_FROM)))
    text = _Translate(text, Value(_DIGITS_FROM), Value(to_latin_digits(_DIGITS_FROM)))
    text = _RegexpReplace(text, Value(_WHITESPACE), Value(" "), Value("g"))
    text = Func(text, function="btrim")
    return Lower(text, output_field=CharField())


def search_people(queryset, raw_term: str):
    """Filter a User queryset by a free-text name search."""
    term = normalize_search_term(raw_term or "")
    if not term:
        return queryset
    return queryset.annotate(name_key=normalized_name_expression()).filter(name_key__icontains=term)
