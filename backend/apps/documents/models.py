import os
import uuid

from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Index, Q, UniqueConstraint

from apps.core.constants import (
    GROUP_CODE_PREFIX,
    REGISTER_COLUMN_ROLE,
    DocumentCategory,
    DocumentGroup,
    DocumentStatus,
    FileKind,
    ResponsibilityRole,
    SectionType,
    SignOffRole,
)
from apps.core.models import TimeStampedModel

#: Revision is rendered as two digits everywhere (register, PDF header, file
#: names, the code printed on the QR), so it is capped at 99. V_1.0 instead
#: wrapped silently from 99 back to "00" (documents_01.py:752-759), which
#: reused an existing revision number.
MAX_REVISION = 99

#: A revision is "finalized" once it has been through sign-off. Only a
#: finalized revision may be superseded by a new one — V_1.0's guard was
#: `valid != "unknown"` (documents_01.py:735).
FINALIZED_STATUSES = frozenset({DocumentStatus.UNDER_CONTROL, DocumentStatus.OBSOLETE})


def logo_upload_to(instance, filename):
    # Always .png: uploads are normalized to PNG on the way in (see
    # apps/documents/files.py). The PDF renderer only draws a logo whose path
    # contains ".png" and paints a black box for anything else
    # (to_make_pdf.py:159-160), so a .jpg logo silently became a black square.
    return f"logos/{instance.pk}/{uuid.uuid4().hex}.png"


def document_file_upload_to(instance, filename):
    # A random name on disk; the name the author knew it by lives in
    # `original_name`. Nothing user-controlled ends up in a filesystem path.
    extension = os.path.splitext(filename)[1].lower()
    return f"document_files/{instance.document_id}/{uuid.uuid4().hex}{extension}"


class DocumentSequence(models.Model):
    """Per-group counter that allocates the next document number.

    V_1.0 derived the next number from the *last row in the group*
    (`group_grouth`, documents_01.py:658-675). That is racy, and it was also
    wrong: revision rows were always stored with simple_code "1" (the local
    variable is never reassigned on the revision path, :694 vs :780), so after
    any revision the next new document in that group was handed a number that
    already existed.

    Here the number is allocated under a row lock (`select_for_update`), inside
    the same transaction that inserts the document — so numbers are gapless and
    can never be issued twice, even with concurrent creators.
    """

    group = models.CharField(max_length=16, choices=DocumentGroup.choices, primary_key=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.group}: {self.last_number}"


class Document(TimeStampedModel):
    """One *revision* of a controlled document.

    A document "family" is identified by (group, number) — e.g. PO-01 — and each
    revision of it is its own row: PO-01-01, PO-01-02, ... This mirrors V_1.0,
    where every revision was a separate Mongo row sharing a `code`.

    The printed identifier is `<PREFIX>-<NN>-<RR>` where PREFIX comes from the
    group (see GROUP_CODE_PREFIX — deliberately not a transliteration).
    """

    category = models.CharField(max_length=16, choices=DocumentCategory.choices)
    title = models.CharField(max_length=255)
    group = models.CharField(max_length=16, choices=DocumentGroup.choices)
    number = models.PositiveIntegerField()
    revision = models.PositiveSmallIntegerField(default=1)

    status = models.CharField(
        max_length=24, choices=DocumentStatus.choices, default=DocumentStatus.DRAFT
    )

    # A OneToOne (not a FK) on purpose: a revision has at most one successor, so
    # the database itself rejects two concurrent "new revision" requests. The
    # reverse accessor `next_revision` is what V_1.0 lacked — there, an old
    # revision was never marked superseded and stayed valid alongside the new
    # one. It also replaces the `check/` directory of previous-revision JSON
    # that the PDF adapter used to fetch over HTTP.
    previous_revision = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="next_revision",
    )

    # Set by the designer whenever the body is saved. Replaces V_1.0's
    # `json_path != ""` test for "content exists" (documents_01.py:895). V_1.0 also
    # stamped the document date with *today* on every save (utils.py:511); that
    # date is derived from this timestamp rather than stored twice.
    content_saved_at = models.DateTimeField(null=True, blank=True)

    # Bumped on every designer save. A client must present the version it loaded;
    # a mismatch means someone else saved in between (optimistic concurrency —
    # V_1.0 was single-user desktop software and had no such problem).
    content_version = models.PositiveIntegerField(default=0)

    # سربرگ / پاورقی (poster_01.py:999-1250). V_1.0 stored the logo as a *local
    # filesystem path* on the author's machine (saves/<title>.txt) plus a public
    # S3 URL, and drew only PNGs.
    logo = models.ImageField(upload_to=logo_upload_to, blank=True)
    footnote1 = models.CharField(max_length=255, blank=True)
    footnote2 = models.CharField(max_length=255, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_documents"
    )

    class Meta:
        # V_1.0 listed documents in insertion order (`collection.find()`).
        ordering = ["id"]
        constraints = [
            UniqueConstraint(
                fields=["group", "number", "revision"], name="uniq_document_code_revision"
            ),
            # A title identifies one family per group. Creation is already
            # serialized by the sequence lock; this is the database-level net.
            UniqueConstraint(
                fields=["group", "title"],
                condition=Q(revision=1),
                name="uniq_document_title_per_group",
            ),
            CheckConstraint(
                check=Q(revision__gte=1) & Q(revision__lte=MAX_REVISION),
                name="document_revision_in_range",
            ),
        ]
        indexes = [
            Index(fields=["group", "title"]),
            Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.full_code} — {self.title}"

    # -- identifiers ---------------------------------------------------------

    @property
    def prefix(self) -> str:
        return GROUP_CODE_PREFIX[self.group]

    @property
    def code(self) -> str:
        """The family code, e.g. "PO-01" (V_1.0's `code`). Numbers of 100 or
        more simply grow a digit, as they did in the original."""
        return f"{self.prefix}-{self.number:02d}"

    @property
    def revision_display(self) -> str:
        return f"{self.revision:02d}"

    @property
    def full_code(self) -> str:
        """The document number printed on the PDF and QR, e.g. "PO-01-01"
        (V_1.0's `document_number`)."""
        return f"{self.code}-{self.revision_display}"

    # -- lifecycle -----------------------------------------------------------

    @property
    def is_finalized(self) -> bool:
        return self.status in FINALIZED_STATUSES

    @property
    def action(self) -> str:
        """The register's per-row action, from V_1.0 documents_01.py:886-902:

            finalized       -> "print"    (V_1.0: valid != "unknown")
            body saved      -> "finish"   (V_1.0: json_path != "")
            otherwise       -> "complete"

        The original's fourth case, "Select", is a mode of the register itself
        (picking a document to attach), not a property of the document.
        """
        if self.is_finalized:
            return "print"
        if self.content_saved_at is not None:
            return "finish"
        return "complete"

    @property
    def is_editable(self) -> bool:
        """The body can be edited only while the document is a draft. V_1.0 only
        ever let you into the designer before the first save; once a document is
        submitted for confirmation its content is locked until it is returned."""
        return self.status == DocumentStatus.DRAFT

    def responsibility_summary(self):
        """The حسابکش / پاسخ خواه / پاسخگو register columns.

        V_1.0 denormalized three [post, supervisor] pairs onto the index row so the
        register could render without loading document bodies. Here they are
        derived from the document's Responsibilities section, following the *row
        labels* (see REGISTER_COLUMN_ROLE). A value is None until the row has a
        post or a supervisor.

        The register list prefetches `responsibility_sections` so this costs no
        query per row; elsewhere it falls back to one query.
        """
        sections = getattr(self, "responsibility_sections", None)
        if sections is None:
            sections = list(
                self.sections.filter(type=SectionType.RESPONSIBILITIES)
                .order_by("position", "id")
                .prefetch_related("responsibility_rows")
            )

        summary = {column: None for column in REGISTER_COLUMN_ROLE}
        if not sections:
            return summary

        # A document has at most one Responsibilities block (enforced on save).
        rows = {row.role: row for row in sections[0].responsibility_rows.all() if row.role}
        for column, role in REGISTER_COLUMN_ROLE.items():
            row = rows.get(role)
            if row is not None and (row.post or row.supervisor):
                summary[column] = {"post": row.post, "supervisor": row.supervisor}
        return summary

    def previous_change_rows(self):
        """Change-table rows written in *earlier revisions* of this document,
        oldest first — the frozen history shown above the editable rows.

        V_1.0 got this by downloading the previous revision's JSON over HTTP and
        prepending its rows at PDF time (deliver_convert.py:163-197, which also
        only ever reached back one revision). Here it is one query over the
        revision family, so it is complete however many revisions there are.
        """
        return (
            ChangeTableRow.objects.filter(
                section__type=SectionType.CHANGES_TABLE,
                section__document__group=self.group,
                section__document__number=self.number,
                section__document__revision__lt=self.revision,
            )
            .select_related("section__document")
            .order_by("section__document__revision", "section__position", "position", "id")
        )


class SignOff(TimeStampedModel):
    """One signature slot on a document: تدوین کننده / تایید کننده / تصویب کننده.

    V_1.0 kept these in two inconsistent shapes: the Mongo row started as
    [name, role, signature_url] but was overwritten with [name, date], losing
    the role and signature (create_confirm_approval_statusControl.py:1800-1811),
    while the JSON file kept all three. This is the union, with the JSON as the
    source of truth.

    Only the model exists in Phase 2 (the register's تدوین/تائید/تصویب columns
    read from it); the sign-off workflow that writes it is Phase 5.
    """

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="signoffs")
    role = models.CharField(max_length=16, choices=SignOffRole.choices)
    name = models.CharField(max_length=255, blank=True)
    position = models.CharField(max_length=255, blank=True)
    signature = models.ImageField(upload_to="signatures/", blank=True)
    signed_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=["document", "role"], name="uniq_signoff_role_per_document")
        ]

    def __str__(self):
        return f"{self.document.full_code} {self.role}: {self.name}"


class DocumentFile(TimeStampedModel):
    """A file attached to a document's Long Explanation block.

    V_1.0 put every attachment in ONE shared S3 bucket under its bare filename
    and "deduplicated" by comparing names against *every object in the bucket*
    (utils.py:1690-1732): two documents attaching different files that were both
    called form.docx silently shared one of them, and `list_objects_v2` returns at
    most 1000 keys, so the check stopped working past that. Files here belong to
    one document and are deduplicated by content hash within it.
    """

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to=document_file_upload_to, max_length=255)
    original_name = models.CharField(max_length=255)
    kind = models.CharField(max_length=16, choices=FileKind.choices)
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            UniqueConstraint(fields=["document", "sha256"], name="uniq_document_file_content")
        ]

    def __str__(self):
        return f"{self.document.full_code}: {self.original_name}"


class Section(TimeStampedModel):
    """One block of a document's body, in page order (V_1.0 `dynamic_items`).

    `content` holds the plain-text shapes of the two text-only block types:
        Short Explanation -> {"lines": [str, ...]}
        Long Explanation  -> {"heading": str, "body": str, "extra_boxes": [str, ...]}
    The other three types are relational because they are read or joined
    elsewhere: ResponsibilityRow feeds the register, ChangeTableRow is walked
    across revisions, AttachmentReference is a real link to another document.

    Rich text inside `body` / `extra_boxes` keeps V_1.0's inline markers — **bold**,
    ~~italic~~, --underline-- — verbatim, because the PDF renderer parses exactly
    those (to_make_pdf.py:458-541).
    """

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="sections")
    position = models.PositiveSmallIntegerField()
    type = models.CharField(max_length=24, choices=SectionType.choices)
    content = models.JSONField(default=dict, blank=True)
    # Only meaningful for Long Explanation blocks (the upload stage).
    files = models.ManyToManyField(DocumentFile, blank=True, related_name="sections")

    class Meta:
        ordering = ["position", "id"]
        indexes = [Index(fields=["document", "position"])]

    def __str__(self):
        return f"{self.document.full_code} #{self.position} {self.type}"


class ResponsibilityRow(TimeStampedModel):
    """A row of a Responsibilities block.

    Four rows have a `role` and carry a سمت (post), a ناظر (supervisor) and a
    description. Any further rows have no role and are description-only notes,
    which the PDF prints under «توضیحات» (deliver_convert.py:99-114).

    `post` and `supervisor` are free text. V_1.0's dropdowns for them each held a
    single hardcoded placeholder ('Organiztion Post' / 'SuperVisor',
    utils.py:1452,1476), so no list of posts ever existed.
    """

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="responsibility_rows")
    position = models.PositiveSmallIntegerField()
    role = models.CharField(max_length=16, choices=ResponsibilityRole.choices, blank=True)
    post = models.CharField(max_length=255, blank=True)
    supervisor = models.CharField(max_length=255, blank=True)
    text = models.TextField(blank=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            UniqueConstraint(
                fields=["section", "role"],
                condition=~Q(role=""),
                name="uniq_responsibility_role_per_section",
            )
        ]


class ChangeTableRow(TimeStampedModel):
    """One line of a Changes Table.

    The edition number is not stored: it is the revision of the document the row
    was written in, so it can never disagree with it. (V_1.0 stored the row's own
    index, padded to two digits — utils.py:1320 — which was only ever the revision
    by coincidence.) `date` is set by the server when the row is first saved and
    never taken from the client, so the log's dates can't be edited after the fact.
    """

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="change_rows")
    position = models.PositiveSmallIntegerField()
    text = models.TextField()
    date = models.DateField()

    class Meta:
        ordering = ["position", "id"]


class AttachmentReference(TimeStampedModel):
    """A ضمیمه: a captioned link to another controlled document (V_1.0 stored
    [caption, "CODE-REV", qr_path] — a code string and a file path where a real
    relation belongs, utils.py:630-632). The PDF prints the caption, the
    referenced document's code, and its QR."""

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="attachment_items")
    position = models.PositiveSmallIntegerField()
    caption = models.CharField(max_length=255)
    target = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="referenced_by")

    class Meta:
        ordering = ["position", "id"]
