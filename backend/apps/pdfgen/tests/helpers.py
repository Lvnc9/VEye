"""Build the shared cases (cases.py) as real rows in Postgres."""
import zoneinfo
from datetime import datetime
from pathlib import Path

from django.core.files.base import ContentFile

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.core.constants import (
    RESPONSIBILITY_ROLE_ORDER,
    DocumentCategory,
    DocumentStatus,
    SectionType,
)
from apps.documents.models import (
    AttachmentReference,
    ChangeTableRow,
    Document,
    ResponsibilityRow,
    Section,
    SignOff,
)

from . import cases as C

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LOCMEM_CACHE = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "veye-pdfgen-tests"}
}
TEHRAN = zoneinfo.ZoneInfo("Asia/Tehran")


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def make_author(national_code="7000000001"):
    return User.objects.create_user(
        national_code=national_code,
        password="pw-for-tests-123",
        full_name="نویسنده آزمون",
        access_roll=AccessRoll.GUILD,
        access_level=AccessLevel.LEVEL_2,
    )


def _saved_at(day):
    return datetime(day.year, day.month, day.day, 12, 0, tzinfo=TEHRAN)


def _add_sections(document, sections, created, author=None):
    for position, section in enumerate(sections):
        kind = section[0]
        if kind == "short":
            Section.objects.create(
                document=document, position=position, type=SectionType.SHORT_EXPLANATION,
                content={"lines": section[1]},
            )
        elif kind == "long":
            Section.objects.create(
                document=document, position=position, type=SectionType.LONG_EXPLANATION,
                content={"heading": section[1], "body": section[2], "extra_boxes": []},
            )
        elif kind == "responsibilities":
            row_section = Section.objects.create(
                document=document, position=position, type=SectionType.RESPONSIBILITIES
            )
            rows = [
                ResponsibilityRow(section=row_section, position=i, role=role, post=post, supervisor=sup, text=text)
                for i, (role, (post, sup, text)) in enumerate(zip(RESPONSIBILITY_ROLE_ORDER, section[1]))
            ]
            rows += [
                ResponsibilityRow(section=row_section, position=len(rows) + i, text=note)
                for i, note in enumerate(section[2])
            ]
            ResponsibilityRow.objects.bulk_create(rows)
        elif kind == "changes":
            change_section = Section.objects.create(
                document=document, position=position, type=SectionType.CHANGES_TABLE
            )
            ChangeTableRow.objects.bulk_create(
                ChangeTableRow(section=change_section, position=i, date=day, text=text)
                for i, (day, text) in enumerate(section[1])
            )
        elif kind == "attachments":
            attach_section = Section.objects.create(
                document=document, position=position, type=SectionType.ATTACHMENT
            )
            AttachmentReference.objects.bulk_create(
                AttachmentReference(
                    section=attach_section, position=i, caption=caption, target=create_case(key, created, author)
                )
                for i, (caption, key) in enumerate(section[1])
            )


def create_case(key: str, created: dict, author=None) -> Document:
    """The Document for `cases.CASES[key]` (memoized in `created`, so an
    attachment target is created once and shared)."""
    if key in created:
        return created[key]
    case = C.CASES[key]
    author = author or User.objects.filter(national_code="7000000001").first() or make_author()

    previous = None
    if case["revision"] > 1:
        previous = Document.objects.create(
            category=DocumentCategory.INSIDE, title=case["title"], group=case["group"],
            number=case["number"], revision=case["revision"] - 1, status=DocumentStatus.UNDER_CONTROL,
            content_saved_at=_saved_at(case["previous_changes"][0][0]), created_by=author,
        )
        _add_sections(previous, [("changes", case["previous_changes"])], created, author)

    document = Document.objects.create(
        category=DocumentCategory.INSIDE, title=case["title"], group=case["group"], number=case["number"],
        revision=case["revision"], status=case["status"], previous_revision=previous,
        content_saved_at=_saved_at(case["day"]), footnote1=case["footnotes"][0],
        footnote2=case["footnotes"][1], created_by=author,
    )
    created[key] = document

    if case["logo"]:
        document.logo.save("logo.png", ContentFile(fixture_bytes("logo.png")), save=True)
    for role in case["signers"]:
        name, position = C.SIGNERS[role]
        signoff = SignOff(document=document, role=role, name=name, position=position, signed_date=case["day"])
        signoff.signature.save(f"{role}.png", ContentFile(fixture_bytes(f"sign_{role}.png")), save=False)
        signoff.save()

    _add_sections(document, case["sections"], created, author)
    return document
