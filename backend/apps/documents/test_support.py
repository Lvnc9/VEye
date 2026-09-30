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
from apps.organization.models import Company, OrgNode

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


def ensure_org():
    """The sample chart, made once per test: a second call (another fixture in the same test) finds the
    nodes by name instead of failing on the company's unique root."""
    existing = {node.name: node for node in OrgNode.objects.all()}
    if "شرکت" in existing:
        get = lambda name: existing[name]
    else:
        root = tree.create_root(name="شرکت")
        Company.objects.create(pk=1, root=root)
        made = {"شرکت": root}

        def node(kind, name, parent):
            made[name] = tree.create_node(kind=kind, name=name, parent=made[parent])

        node("DOMAIN", "IT", "شرکت")
        node("DOMAIN", "فروش", "شرکت")
        node("UNIT", "هوش مصنوعی", "IT")
        node("UNIT", "توسعه", "IT")
        node("UNIT", "بستن معاملات", "فروش")
        node("UNIT", "مدیریت سیستم‌ها", "شرکت")
        node("SECTION", "RAG", "هوش مصنوعی")
        node("SECTION", "LLM", "هوش مصنوعی")
        node("SECTION", "Backend", "توسعه")
        node("SECTION", "نقد", "بستن معاملات")
        node("SECTION", "کیفیت", "مدیریت سیستم‌ها")
        get = lambda name: made[name]
    return SimpleNamespace(
        root=get("شرکت"), it=get("IT"), sales=get("فروش"), ai=get("هوش مصنوعی"), dev=get("توسعه"),
        deals=get("بستن معاملات"), qms=get("مدیریت سیستم‌ها"), rag=get("RAG"), llm=get("LLM"),
        backend=get("Backend"), cash=get("نقد"), quality=get("کیفیت"),
    )


def make_org():
    return ensure_org()


def place_by_roll(user):
    """A compatibility shim for the older tests, which built people by roll: a صفی leads the بخش «RAG»
    (writes its documents), a ستادی leads the واحد «هوش مصنوعی» above it (writes and confirms them),
    a کارفرمایی has no chart authority — only the مدیر عامل (کارفرمایی لول ۱) acts, on everything.
    Tests that are *about* who may do what place people explicitly instead."""
    org = ensure_org()
    if user.access_roll == AccessRoll.GUILD:
        lead_of(user, org.rag)
    elif user.access_roll == AccessRoll.HEADQUARTERS:
        lead_of(user, org.ai)
    return user


def default_node():
    """Where `new_doc` puts a document unless told otherwise: the بخش «RAG» of the sample chart."""
    return ensure_org().rag


def lead_of(user, node, **kwargs):
    """Make `user` a مسئول of `node`."""
    return memberships.add_membership(user=user, node=node, is_lead=True, **kwargs)


def member_of(user, node, **kwargs):
    """Make `user` a plain member of `node` (not a مسئول)."""
    return memberships.add_membership(user=user, node=node, is_lead=False, **kwargs)
