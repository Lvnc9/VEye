"""Shared fixtures for the tests that need an org chart with leads (Phase 14).

    شرکت
     ├─ IT (حوزه) ─┬─ هوش مصنوعی (واحد) ─┬─ RAG (بخش)
     │             │                     └─ LLM (بخش)
     │             └─ توسعه (واحد) ────── Backend (بخش)
     ├─ فروش (حوزه) ─ بستن معاملات (واحد) ─ نقد (بخش)
     └─ مدیریت سیستم‌ها (واحد, straight under the company) ─ کیفیت (بخش)
"""
from types import SimpleNamespace

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.organization import memberships, tree
from apps.organization.models import Company

_counter = [0]


def make_person(code=None, roll=AccessRoll.GUILD, level=AccessLevel.LEVEL_3, **extra):
    """A user. Roll × level only sets the سمت now — what a person may do with documents comes from
    where they lead."""
    if code is None:
        _counter[0] += 1
        code = f"88{_counter[0]:08d}"
    return User.objects.create_user(
        national_code=code, password="pw-for-tests-123", full_name=f"کاربر {code}",
        access_roll=roll, access_level=level, **extra,
    )


def make_managing_director(code=None):
    return make_person(code, AccessRoll.EMPLOYER, AccessLevel.LEVEL_1)


def make_org():
    root = tree.create_root(name="شرکت")
    Company.objects.create(pk=1, root=root)
    node = lambda kind, name, parent: tree.create_node(kind=kind, name=name, parent=parent)
    it = node("DOMAIN", "IT", root)
    sales = node("DOMAIN", "فروش", root)
    ai = node("UNIT", "هوش مصنوعی", it)
    dev = node("UNIT", "توسعه", it)
    deals = node("UNIT", "بستن معاملات", sales)
    qms = node("UNIT", "مدیریت سیستم‌ها", root)
    return SimpleNamespace(
        root=root, it=it, sales=sales, ai=ai, dev=dev, deals=deals, qms=qms,
        rag=node("SECTION", "RAG", ai), llm=node("SECTION", "LLM", ai),
        backend=node("SECTION", "Backend", dev),
        cash=node("SECTION", "نقد", deals),
        quality=node("SECTION", "کیفیت", qms),
    )


def lead_of(user, node, **kwargs):
    """Make `user` a مسئول of `node`."""
    return memberships.add_membership(user=user, node=node, is_lead=True, **kwargs)


def member_of(user, node, **kwargs):
    """Make `user` a plain member of `node` (not a مسئول)."""
    return memberships.add_membership(user=user, node=node, is_lead=False, **kwargs)
