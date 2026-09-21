"""The company profile: its details and its logo. (The tree itself is tree.py.)"""
from django.db import transaction

from apps.core.text import normalize_title, to_latin_digits
from apps.documents.files import normalize_logo

from . import tree
from .models import Company, SetupStep
from .setup_state import advance_step


def _delete_storage_on_commit(field_file) -> None:
    """Remove a stored file only once the surrounding transaction has committed — a
    rollback must not leave a database row pointing at nothing."""
    if field_file and field_file.name:
        name, storage = field_file.name, field_file.storage
        transaction.on_commit(lambda: storage.delete(name))


def _locked(company_id: int) -> Company:
    return Company.objects.select_for_update().select_related("root").get(pk=company_id)


@transaction.atomic
def update_company(
    company: Company, *, name: str | None = None, legal_name: str | None = None, national_id: str | None = None
) -> Company:
    """Any subset of the profile. The display name is the root node's name."""
    company = _locked(company.pk)
    if name is not None:
        tree.rename_node(company.root, name)
    if legal_name is not None:
        company.legal_name = normalize_title(legal_name)
    if national_id is not None:
        # Persian digits become ASCII, and any whitespace typed into the number is dropped.
        company.national_id = "".join(to_latin_digits(national_id).split())
    company.save(update_fields=["legal_name", "national_id", "updated_at"])
    advance_step(SetupStep.COMPANY)
    return _locked(company.pk)


@transaction.atomic
def set_logo(company: Company, *, upload) -> Company:
    company = _locked(company.pk)
    png = normalize_logo(upload)
    _delete_storage_on_commit(company.logo)
    company.logo.save("logo.png", png, save=False)
    company.save(update_fields=["logo", "updated_at"])
    advance_step(SetupStep.COMPANY)
    return company


@transaction.atomic
def remove_logo(company: Company) -> Company:
    company = _locked(company.pk)
    _delete_storage_on_commit(company.logo)
    company.logo = ""
    company.save(update_fields=["logo", "updated_at"])
    advance_step(SetupStep.COMPANY)
    return company
