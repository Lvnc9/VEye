"""The org-chart side of the Responsibilities block (owner's redesign, 2026-09-30).

A row names a حوزه (only when the company has any), a واحد and what the واحد is responsible for.
This module is the *only* place under `apps/documents` that reads the org tree for it: it checks
what the client sent against `OrgNode` and returns the rows the block stores, each with the
**snapshot** names that get printed (a printed document must not change when a node is renamed,
archived or deleted — `ResponsibilityRow.domain` / `unit` are `SET_NULL`).

`legacy_text` is the one rule for turning the block's old shape (four fixed roles with a سمت and a
ناظر, plus free notes) into a free line of text; the V_1.0 importer uses it, and migration 0008
carries its own copy of the rule so it never depends on this module.
"""
from __future__ import annotations

from apps.organization.models import OrgNode, OrgNodeKind

MAX_ROWS = 100


class RowError(Exception):
    """One or more Persian messages, each already prefixed with its row number."""

    def __init__(self, messages: list[str]):
        super().__init__("; ".join(messages))
        self.messages = messages


#: The letters the old block printed beside its four fixed rows (V_1.0's الف/ب/ج/د).
LEGACY_LETTERS = ("الف", "ب", "ج", "د")


def legacy_text(index: int, post: str, supervisor: str, text: str) -> str:
    """One old fixed row as a free line: «الف:  سمت: X    ناظر: Y», then its description on the next
    line. Empty when the old row said nothing at all."""
    post, supervisor, text = (post or "").strip(), (supervisor or "").strip(), (text or "").strip()
    if not (post or supervisor or text):
        return ""
    letter = LEGACY_LETTERS[index] if 0 <= index < len(LEGACY_LETTERS) else ""
    parts = ([f"سمت: {post}"] if post else []) + ([f"ناظر: {supervisor}"] if supervisor else [])
    head = (f"{letter}:  " if letter else "") + "    ".join(parts)
    if not parts:
        return f"{head}{text}"
    return f"{head}\n{text}" if text else head


def stored_node_ids(document) -> set[int]:
    """The حوزه / واحد ids the document's Responsibilities rows already hold — an archived node the
    rows already name may stay; a new choice must be an active one."""
    from .models import ResponsibilityRow

    ids: set[int] = set()
    for domain_id, unit_id in ResponsibilityRow.objects.filter(section__document=document).values_list(
        "domain_id", "unit_id"
    ):
        ids.update(i for i in (domain_id, unit_id) if i)
    return ids


def resolve(rows: list[dict], *, kept: set[int] = frozenset()) -> list[dict]:
    """Check `rows` ({domain, unit, domain_name, unit_name, text}) against the org tree and return
    what to store: real names copied from the chart wherever an id is given, the client's own
    snapshot (a node deleted since) otherwise, the حوزه filled in from a واحد that has one, empty
    rows dropped. Raises `RowError`."""
    ids = {i for row in rows for i in (row.get("domain"), row.get("unit")) if i}
    nodes = {node.pk: node for node in OrgNode.objects.filter(pk__in=ids).select_related("parent")} if ids else {}

    messages: list[str] = []
    stored: list[dict] = []
    for number, row in enumerate(rows, start=1):
        where = f"ردیف {number}"
        domain_id, unit_id = row.get("domain"), row.get("unit")
        domain, unit = nodes.get(domain_id) if domain_id else None, nodes.get(unit_id) if unit_id else None
        problems: list[str] = []

        if domain_id and domain is None:
            problems.append("حوزهٔ انتخاب‌شده پیدا نشد.")
        elif domain is not None and domain.kind != OrgNodeKind.DOMAIN:
            problems.append("گرهٔ انتخاب‌شده حوزه نیست.")
        if unit_id and unit is None:
            problems.append("واحد انتخاب‌شده پیدا نشد.")
        elif unit is not None and unit.kind != OrgNodeKind.UNIT:
            problems.append("گرهٔ انتخاب‌شده واحد نیست.")

        if not problems and unit is not None:
            parent = unit.parent
            if domain is None and parent is not None and parent.kind == OrgNodeKind.DOMAIN:
                domain = parent  # a واحد names its حوزه: never print one without the other
            if domain is not None and unit.parent_id != domain.pk:
                problems.append(f"واحد «{unit.name}» به حوزهٔ «{domain.name}» تعلق ندارد.")
        if not problems:
            for node in (domain, unit):
                if node is not None and not node.is_active and node.pk not in kept:
                    problems.append(f"«{node.name}» بایگانی شده و قابل انتخاب نیست.")

        text = row.get("text", "")
        domain_name = domain.name if domain is not None else (row.get("domain_name") or "").strip()
        unit_name = unit.name if unit is not None else (row.get("unit_name") or "").strip()
        if not problems and domain_id and unit is None and not unit_name:
            problems.append("واحد را انتخاب کنید.")
        if problems:
            messages.extend(f"{where}: {problem}" for problem in problems)
            continue
        if not (unit_name or domain_name or text.strip()):
            continue  # a row left blank in the editor
        stored.append(
            {
                "domain": domain.pk if domain is not None else None,
                "unit": unit.pk if unit is not None else None,
                "domain_name": domain_name,
                "unit_name": unit_name,
                "text": text,
            }
        )
    if messages:
        raise RowError(messages)
    return stored
