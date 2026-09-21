import uuid
from functools import reduce
from operator import or_

from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Index, Q, UniqueConstraint

from apps.core.models import TimeStampedModel


class OrgNodeKind(models.TextChoices):
    COMPANY = "COMPANY", "شرکت"
    DOMAIN = "DOMAIN", "حوزه"
    UNIT = "UNIT", "واحد"
    SECTION = "SECTION", "بخش"


class SetupStep(models.TextChoices):
    """Where the first-run wizard stands. A UI bookmark only — there is deliberately
    no ordering guard, because going back to add another حوزه is legitimate."""

    COMPANY = "COMPANY", "شرکت"
    DOMAINS = "DOMAINS", "حوزه‌ها"
    UNITS = "UNITS", "واحدها"
    SECTIONS = "SECTIONS", "بخش‌ها"
    PEOPLE = "PEOPLE", "افراد"
    DONE = "DONE", "پایان"


#: The parent-kind table: which kind of node a node of each kind may hang under.
#: "" stands for "no parent" — only the company root. A واحد hangs under a حوزه *or*
#: directly under the company (a company with no حوزه is a valid company), which is
#: exactly why a node's depth cannot be derived from its kind and is stored.
#: The database enforces this table (see OrgNode.Meta), and tree.py enforces it first
#: so the caller gets a Persian message rather than an IntegrityError.
ALLOWED_PARENT_KINDS = {
    OrgNodeKind.COMPANY: frozenset({""}),
    OrgNodeKind.DOMAIN: frozenset({OrgNodeKind.COMPANY}),
    OrgNodeKind.UNIT: frozenset({OrgNodeKind.COMPANY, OrgNodeKind.DOMAIN}),
    OrgNodeKind.SECTION: frozenset({OrgNodeKind.UNIT}),
}

#: Names of the constraints tree.py reacts to; kept here so the two cannot drift.
NODE_NAME_CONSTRAINT = "uniq_org_node_name_per_parent"
PRIMARY_MEMBERSHIP_CONSTRAINT = "uniq_primary_membership_per_user"


def company_logo_upload_to(instance, filename):
    # Always .png: uploads are normalized to PNG on the way in (apps/documents/files.py
    # normalize_logo). A random name — nothing user-controlled ends up in a path.
    return f"company/{uuid.uuid4().hex}.png"


def _parent_kind_rule() -> Q:
    return reduce(
        or_,
        (
            Q(kind=kind, parent_kind__in=sorted(parent_kinds))
            for kind, parent_kinds in ALLOWED_PARENT_KINDS.items()
        ),
    )


class OrgNode(TimeStampedModel):
    """One node of the company's structure: the company itself, a حوزه, a واحد or a بخش.

    A single self-referencing table with a `kind` discriminator, so anything that must
    point at "a node at any level" (memberships, projects, conversations — later
    slices) is one ordinary foreign key.

    `path` is materialised: "0000000001/0000000007/0000000042/", the ids of every
    ancestor and the node itself, root first, each zero-padded to a fixed width and
    slash-terminated so a prefix test always ends on a segment boundary
    (`path__startswith(ancestor.path)` is exactly "is a descendant of"). It gives the whole
    tree in one `ORDER BY path` (already pre-order depth-first) and answers "is X an
    ancestor of N?" from the row itself, with no query. `depth`, `path` and `parent_kind`
    are maintained only by apps/organization/tree.py: a CHECK cannot read another row.
    """

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        # PROTECT: deleting a واحد must never silently take its بخش‌ها, and everything
        # that later hangs off them, with it.
        on_delete=models.PROTECT,
        related_name="children",
    )
    #: Immutable after creation — it is what makes the parent-kind constraint sound.
    kind = models.CharField(max_length=8, choices=OrgNodeKind.choices)
    #: Denormalised copy of the parent's kind, so the parent-kind table can be a CHECK
    #: over two columns of one row.
    parent_kind = models.CharField(max_length=8, choices=OrgNodeKind.choices, blank=True)
    #: The display form (normalize_title: unified letterforms, ZWNJ kept).
    name = models.CharField(max_length=255)
    #: normalize_search_term(name) — what sibling uniqueness compares. Never client-settable.
    name_key = models.CharField(max_length=255)
    path = models.CharField(max_length=255)
    depth = models.PositiveSmallIntegerField()
    #: «بایگانی» — the supported way to retire a node that has history.
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["path"]
        constraints = [
            # The singleton root, in the database.
            UniqueConstraint(
                fields=["kind"], condition=Q(kind=OrgNodeKind.COMPANY), name="uniq_company_root_node"
            ),
            # parent IS NULL  <=>  kind = COMPANY
            CheckConstraint(
                check=(
                    Q(parent__isnull=True, kind=OrgNodeKind.COMPANY)
                    | (Q(parent__isnull=False) & ~Q(kind=OrgNodeKind.COMPANY))
                ),
                name="org_node_root_iff_company",
            ),
            CheckConstraint(check=_parent_kind_rule(), name="org_node_parent_kind_allowed"),
            # Sibling-scoped, on the normalised key: «واحد فروش» typed with an Arabic yeh
            # collides with the Persian-yeh one, while two different حوزه may each own a
            # «واحد فروش». (A NULL parent — the root — is never equal to another, which is
            # fine: uniq_company_root_node already allows only one root.)
            UniqueConstraint(fields=["parent", "name_key"], name=NODE_NAME_CONSTRAINT),
        ]
        indexes = [
            Index(fields=["path"], name="org_node_path_idx"),
            Index(fields=["kind", "is_active"], name="org_node_kind_active_idx"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.name}"


class Company(TimeStampedModel):
    """The single company of this deployment: its profile and the first-run state.

    The company's *name* lives on the root OrgNode, not here, so the chart and the page
    header can never disagree.

    `pk=1` is not decoration: inserting this row is what makes bootstrap impossible to run
    twice. Two concurrent bootstraps both insert pk=1; the loser blocks on the primary key
    until the winner commits, then fails. (A `select_for_update` on the users table could
    not do this — Postgres cannot lock rows that do not exist yet.)
    """

    root = models.OneToOneField(OrgNode, on_delete=models.PROTECT, related_name="company")
    legal_name = models.CharField(max_length=255, blank=True)
    #: شناسه ملی
    national_id = models.CharField(max_length=32, blank=True)
    logo = models.ImageField(upload_to=company_logo_upload_to, blank=True)
    setup_step = models.CharField(max_length=16, choices=SetupStep.choices, default=SetupStep.COMPANY)
    setup_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [CheckConstraint(check=Q(pk=1), name="company_is_singleton")]

    def __str__(self):
        return self.root.name


class Membership(TimeStampedModel):
    """A person's place in the structure. Several per person is what makes the real
    organisation expressible: مدیر عامل on the company, ستادی on a حوزه, صفی on a بخش.

    Two things here are the org-position axis and are *not* the roll × level matrix:
    `is_lead` (مسئول این گره — slice 7.3 lets a lead manage their own branch) and
    `position_label` (free text, «مدیر واحد فروش»). `User.title` stays the authoritative
    roll × level value for document sign-offs.

    Invariant, kept by memberships.py: a person with any membership has exactly one
    primary (their "home" node). The partial unique index below is the net for "at most
    one"; "at least one" is the service's job.

    No `ended_at`: leaving a node deletes the row, and history survives because feed
    entries snapshot the actor's name and title as text (the DocumentEvent device). A
    soft-ended membership would put a second "is this row live?" test on the
    access-control hot path.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="memberships")
    node = models.ForeignKey(OrgNode, on_delete=models.PROTECT, related_name="memberships")
    is_primary = models.BooleanField(default=False)
    is_lead = models.BooleanField(default=False)
    position_label = models.CharField(max_length=255, blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["node_id", "-is_lead", "id"]
        constraints = [
            UniqueConstraint(fields=["user", "node"], name="uniq_membership_user_node"),
            UniqueConstraint(
                fields=["user"], condition=Q(is_primary=True), name=PRIMARY_MEMBERSHIP_CONSTRAINT
            ),
        ]
        # (user is already indexed by its foreign key, and by the unique constraint above.)
        indexes = [Index(fields=["node", "is_lead"], name="membership_node_lead_idx")]

    def __str__(self):
        return f"{self.user.full_name} @ {self.node.name}"
