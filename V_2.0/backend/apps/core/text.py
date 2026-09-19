"""Persian text normalization.

Persian data in the wild mixes Arabic and Persian letterforms: V_1.0's own
generated filenames contain both, e.g. «روش اجرايي کنترل مستندات» has an
*Arabic* yeh (U+064A) in «اجرايي» next to a *Persian* keheh (U+06A9) in «کنترل».
Keyboards, copy-paste from Word, and phone IMEs all produce either. Without
normalizing, "the same title" typed two ways is two different titles — so it
would get two different document numbers, and search would miss one of them.
"""
import re

# Arabic letterforms -> their Persian equivalents.
#   U+064A ي  -> U+06CC ی   (yeh)
#   U+0649 ى  -> U+06CC ی   (alef maqsura, used as yeh on some keyboards)
#   U+0643 ك  -> U+06A9 ک   (kaf)
_LETTERS = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک"})

# Persian (U+06F0-06F9) and Arabic-Indic (U+0660-0669) digits -> ASCII.
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

_WHITESPACE = re.compile(r"\s+")


def normalize_letters(text: str) -> str:
    """Unify Arabic/Persian letterforms. Digits are left as typed."""
    return text.translate(_LETTERS)


def to_latin_digits(text: str) -> str:
    return text.translate(_DIGITS)


def normalize_title(text: str) -> str:
    """Canonical form for storing a document title: unified letterforms,
    trimmed, internal whitespace collapsed. ZWNJ (U+200C) is deliberately
    preserved — it is meaningful in Persian orthography («می‌شود»)."""
    return _WHITESPACE.sub(" ", normalize_letters(text)).strip()


def normalize_search_term(text: str) -> str:
    """Canonical form for a search box term: everything normalize_title does,
    plus ASCII digits (people type «۰۱» on a Persian keyboard but codes are
    stored as «PO-01-01») and case-folding."""
    return to_latin_digits(normalize_title(text)).casefold()
