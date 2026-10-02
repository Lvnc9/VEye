"""The chart's change history — the one place that writes an `OrgEvent` (Phase 16).

Called by `tree.py`, `memberships.py` and `delegations.py` from inside the transaction of the
change they record. `actor=None` (a bootstrap, a management command, a test fixture) is recorded as
«سیستم» rather than skipped: a change nobody can attribute is exactly what an audit log is for.
"""
from .models import OrgEvent

SYSTEM_ACTOR = "سیستم"


def record(kind, *, actor=None, node=None, subject=None, from_value="", to_value="", note="") -> OrgEvent:
    return OrgEvent.objects.create(
        kind=kind,
        actor=actor,
        actor_name=actor.full_name if actor is not None else SYSTEM_ACTOR,
        actor_title=actor.title if actor is not None else "",
        node=node,
        node_name=node.name if node is not None else "",
        subject=subject,
        subject_name=subject.full_name if subject is not None else "",
        from_value=from_value,
        to_value=to_value,
        note=note,
    )
