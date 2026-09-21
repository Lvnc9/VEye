"""The first-run wizard's bookmark (`Company.setup_step`).

Kept in its own tiny module because the writers that move it — tree.py, memberships.py,
services.py — must not import bootstrap.py (which imports them). The bookmark says where the
wizard last was, not how far it may go: there is deliberately no ordering guard, since going
back to add another حوزه is legitimate. It is updated by the very write that moved the wizard,
in the same transaction, so a refresh, a crash or another browser resumes at the right step from
`GET /setup/status/` + `GET /org/tree/` — there is no draft table and no session state.
"""
from django.utils import timezone

from .models import Company, OrgNodeKind, SetupStep

STEP_FOR_NODE_KIND = {
    OrgNodeKind.DOMAIN: SetupStep.DOMAINS,
    OrgNodeKind.UNIT: SetupStep.UNITS,
    OrgNodeKind.SECTION: SetupStep.SECTIONS,
}


def advance_step(step: str) -> None:
    """Move the bookmark — but only while setup is unfinished, and as one conditional UPDATE
    (a no-op once complete, or before a company exists)."""
    Company.objects.filter(pk=1, setup_completed_at__isnull=True).update(
        setup_step=step, updated_at=timezone.now()
    )
