import threading

from django.core.cache import cache
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from rest_framework.exceptions import NotFound
from rest_framework.test import APIClient

from apps.accounts.models import AccessLevel, AccessRoll, User
from apps.core.constants import (
    DocumentCategory,
    DocumentGroup,
    DocumentStatus,
    SignOffRole,
)
from apps.core.exceptions import ConflictError as DocumentConflict
from apps.core.text import normalize_search_term, normalize_title

from . import services
from .models import MAX_REVISION, Document, DocumentSequence, SignOff

LOCMEM_CACHE = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "veye-doc-tests"}
}

INSIDE = DocumentCategory.INSIDE
OUTSIDE = DocumentCategory.OUTSIDE


def make_user(national_code="1000000001", roll=AccessRoll.GUILD, level=AccessLevel.LEVEL_3):
    return User.objects.create_user(
        national_code=national_code,
        password="pw-for-tests-123",
        full_name=f"کاربر {national_code}",
        access_roll=roll,
        access_level=level,
    )


def new_doc(user, title="عنوان", group=DocumentGroup.POSTER, category=INSIDE):
    return services.create_document(user=user, category=category, title=title, group=group)


def finalize(doc, status=DocumentStatus.UNDER_CONTROL):
    Document.objects.filter(pk=doc.pk).update(status=status)
    doc.refresh_from_db()
    return doc


class TextNormalizationTests(TestCase):
    def test_arabic_yeh_and_kaf_become_persian(self):
        # The exact spelling in V_1.0's own PDF filename: Arabic ي in «اجرايي».
        self.assertEqual(normalize_title("روش اجرايي"), "روش اجرایی")
        self.assertEqual(normalize_title("كتاب"), "کتاب")

    def test_whitespace_is_collapsed_and_trimmed(self):
        self.assertEqual(normalize_title("  a   b \t c  "), "a b c")

    def test_zwnj_is_preserved(self):
        self.assertEqual(normalize_title("می‌شود"), "می‌شود")

    def test_search_term_uses_ascii_digits_and_casefold(self):
        self.assertEqual(normalize_search_term("PO-۰۱-٠٢"), "po-01-02")


class NumberingTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_first_document_in_a_group(self):
        doc = new_doc(self.user)
        self.assertEqual((doc.number, doc.revision), (1, 1))
        self.assertEqual(doc.code, "PO-01")
        self.assertEqual(doc.full_code, "PO-01-01")
        self.assertEqual(doc.status, DocumentStatus.DRAFT)
        self.assertIsNone(doc.previous_revision)

    def test_group_to_prefix_mapping_is_ported_literally(self):
        """documents_01.py:699-706. روش اجرایی -> PR and دستورالعمل -> WI are
        deliberately crossed relative to a transliteration."""
        expected = {
            DocumentGroup.POSTER: "PO",
            DocumentGroup.PROCEDURE: "PR",
            DocumentGroup.INSTRUCTION: "WI",
            DocumentGroup.FORM: "FR",
        }
        for group, prefix in expected.items():
            doc = new_doc(self.user, title=f"t-{group}", group=group)
            self.assertEqual(doc.code, f"{prefix}-01", group)
        self.assertEqual(DocumentGroup.PROCEDURE.label, "روش اجرایی")
        self.assertEqual(DocumentGroup.INSTRUCTION.label, "دستورالعمل")

    def test_numbers_are_independent_per_group(self):
        a = new_doc(self.user, "الف", DocumentGroup.POSTER)
        b = new_doc(self.user, "ب", DocumentGroup.FORM)
        c = new_doc(self.user, "ج", DocumentGroup.POSTER)
        self.assertEqual((a.code, b.code, c.code), ("PO-01", "FR-01", "PO-02"))

    def test_revising_does_not_corrupt_numbering(self):
        """V_1.0 bug: revision rows were always stored with simple_code "1"
        (documents_01.py:694 vs :780) and the next number was read from the last
        row in the group — so after a revision, the next new document was handed
        a number that already existed.
        """
        new_doc(self.user, "اول")
        second = new_doc(self.user, "دوم")
        finalize(second)
        services.create_revision(user=self.user, document_id=second.pk)

        third = new_doc(self.user, "سوم")
        self.assertEqual(third.code, "PO-03")
        codes = list(Document.objects.filter(group=DocumentGroup.POSTER).values_list("number", "revision"))
        self.assertEqual(len(codes), len(set(codes)), "duplicate (number, revision)")

    def test_duplicate_title_is_reported_not_silently_revised(self):
        """V_1.0 turned an existing title into a new revision without saying so."""
        first = new_doc(self.user, "تکراری")
        with self.assertRaises(DocumentConflict) as ctx:
            new_doc(self.user, "تکراری")
        self.assertEqual(ctx.exception.payload["code"], "title_exists")
        self.assertEqual(ctx.exception.payload["existing_id"], first.pk)

    def test_duplicate_title_advice_depends_on_whether_a_revision_is_possible(self):
        """«بازنگری جدید» only exists once a document is finished — pointing a user
        at a button that isn't there is worse than saying what to do first."""
        doc = new_doc(self.user, "تکراری")
        with self.assertRaises(DocumentConflict) as unfinished:
            new_doc(self.user, "تکراری")
        self.assertIn("ابتدا آن مستند را تکمیل کنید", unfinished.exception.payload["detail"])
        self.assertNotIn("بازنگری جدید", unfinished.exception.payload["detail"])

        finalize(doc)
        with self.assertRaises(DocumentConflict) as finished:
            new_doc(self.user, "تکراری")
        self.assertIn("بازنگری جدید", finished.exception.payload["detail"])

    def test_rejected_create_does_not_burn_a_number(self):
        new_doc(self.user, "تکراری")
        with self.assertRaises(DocumentConflict):
            new_doc(self.user, "تکراری")
        after = new_doc(self.user, "بعدی")
        self.assertEqual(after.code, "PO-02")
        self.assertEqual(DocumentSequence.objects.get(group=DocumentGroup.POSTER).last_number, 2)

    def test_same_title_in_another_group_is_a_different_document(self):
        a = new_doc(self.user, "مشترک", DocumentGroup.POSTER)
        b = new_doc(self.user, "مشترک", DocumentGroup.FORM)
        self.assertNotEqual(a.pk, b.pk)

    def test_arabic_and_persian_spellings_are_the_same_title(self):
        new_doc(self.user, "روش اجرایی کنترل")
        with self.assertRaises(DocumentConflict):
            new_doc(self.user, "روش  اجرايي کنترل ")

    def test_database_rejects_a_duplicate_code_even_if_the_service_is_bypassed(self):
        doc = new_doc(self.user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Document.objects.create(
                category=INSIDE, title="other", group=doc.group, number=doc.number,
                revision=doc.revision, created_by=self.user,
            )

    def test_database_rejects_a_duplicate_title_in_a_group(self):
        new_doc(self.user, "عنوان یکتا")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Document.objects.create(
                category=INSIDE, title="عنوان یکتا", group=DocumentGroup.POSTER, number=99,
                revision=1, created_by=self.user,
            )


class RevisionTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.doc = new_doc(self.user, "سند")

    def test_cannot_revise_an_unfinished_document(self):
        """V_1.0: 'First finish your previous document!' (documents_01.py:735)."""
        for status in (
            DocumentStatus.DRAFT,
            DocumentStatus.AWAITING_CONFIRMATION,
            DocumentStatus.AWAITING_APPROVAL,
        ):
            finalize(self.doc, status)
            with self.assertRaises(DocumentConflict) as ctx:
                services.create_revision(user=self.user, document_id=self.doc.pk)
            self.assertEqual(ctx.exception.payload["code"], "previous_not_finished", status)

    def test_revising_a_finalized_document(self):
        finalize(self.doc)
        rev = services.create_revision(user=self.user, document_id=self.doc.pk)
        self.assertEqual(rev.revision, 2)
        self.assertEqual(rev.number, self.doc.number)
        self.assertEqual(rev.full_code, "PO-01-02")
        self.assertEqual(rev.status, DocumentStatus.DRAFT)
        self.assertEqual(rev.previous_revision, self.doc)
        self.assertEqual((rev.title, rev.group, rev.category), (self.doc.title, self.doc.group, self.doc.category))
        self.assertEqual(self.doc.next_revision, rev)

    def test_an_obsolete_document_can_still_be_revised(self):
        # V_1.0's guard was `valid != "unknown"`, which includes "outdated".
        finalize(self.doc, DocumentStatus.OBSOLETE)
        self.assertEqual(services.create_revision(user=self.user, document_id=self.doc.pk).revision, 2)

    def test_only_the_latest_revision_can_be_revised(self):
        finalize(self.doc)
        services.create_revision(user=self.user, document_id=self.doc.pk)
        with self.assertRaises(DocumentConflict) as ctx:
            services.create_revision(user=self.user, document_id=self.doc.pk)
        self.assertEqual(ctx.exception.payload["code"], "not_latest_revision")

    def test_revision_is_capped_instead_of_wrapping(self):
        """V_1.0 wrapped 99 back to 00 (documents_01.py:752-759), reusing a number."""
        Document.objects.filter(pk=self.doc.pk).update(revision=MAX_REVISION, status=DocumentStatus.UNDER_CONTROL)
        with self.assertRaises(DocumentConflict) as ctx:
            services.create_revision(user=self.user, document_id=self.doc.pk)
        self.assertEqual(ctx.exception.payload["code"], "revision_limit")

    def test_revision_is_two_digits_at_ten(self):
        Document.objects.filter(pk=self.doc.pk).update(revision=9, status=DocumentStatus.UNDER_CONTROL)
        rev = services.create_revision(user=self.user, document_id=self.doc.pk)
        self.assertEqual((rev.revision, rev.full_code), (10, "PO-01-10"))

    def test_unknown_document(self):
        with self.assertRaises(NotFound):
            services.create_revision(user=self.user, document_id=999999)

    def test_database_rejects_out_of_range_revision(self):
        for bad in (0, MAX_REVISION + 1):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Document.objects.create(
                    category=INSIDE, title=f"x{bad}", group=DocumentGroup.FORM, number=1,
                    revision=bad, created_by=self.user,
                )


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class RegisterApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)
        self.author = make_user("2000000001", AccessRoll.GUILD, AccessLevel.LEVEL_3)
        self.employer = make_user("2000000002", AccessRoll.EMPLOYER, AccessLevel.LEVEL_2)  # رئیس هیئت مدیره: approver-only (the مدیر عامل, لول ۱, can do everything)
        self.list_url = reverse("document-list")

    def payload(self, **over):
        return {"category": INSIDE, "title": "روش اجرایی نمونه", "group": DocumentGroup.PROCEDURE, **over}

    # -- permissions -----------------------------------------------------

    def test_anonymous_is_rejected(self):
        self.assertEqual(self.client.get(self.list_url).status_code, 401)
        self.assertEqual(self.client.post(self.list_url, self.payload(), format="json").status_code, 401)

    def test_author_can_create(self):
        self.client.force_authenticate(self.author)
        response = self.client.post(self.list_url, self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["full_code"], "PR-01-01")
        self.assertEqual(response.data["group_label"], "روش اجرایی")
        self.assertEqual(response.data["status"], DocumentStatus.DRAFT)

    def test_employer_cannot_author_but_can_browse(self):
        """کارفرمایی approves; authoring is صفی/ستادی (the confirmed policy)."""
        self.client.force_authenticate(self.employer)
        self.assertEqual(self.client.get(self.list_url).status_code, 200)
        response = self.client.post(self.list_url, self.payload(), format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Document.objects.exists())

    def test_created_by_is_the_authenticated_user_not_client_supplied(self):
        self.client.force_authenticate(self.author)
        self.client.post(self.list_url, {**self.payload(), "created_by": self.employer.pk}, format="json")
        self.assertEqual(Document.objects.get().created_by, self.author)

    # -- validation ------------------------------------------------------

    def test_missing_fields_get_persian_messages(self):
        """V_1.0's "Pleas finish Category/Title/Group field" warnings."""
        self.client.force_authenticate(self.author)
        response = self.client.post(self.list_url, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["category"][0], "دسته بندی را انتخاب کنید.")
        self.assertEqual(response.data["title"][0], "عنوان را وارد کنید.")
        self.assertEqual(response.data["group"][0], "گروه را انتخاب کنید.")

    def test_blank_title_is_rejected(self):
        self.client.force_authenticate(self.author)
        response = self.client.post(self.list_url, self.payload(title="   "), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("title", response.data)

    def test_invalid_choices_are_rejected(self):
        self.client.force_authenticate(self.author)
        self.assertEqual(self.client.post(self.list_url, self.payload(group="NOPE"), format="json").status_code, 400)
        self.assertEqual(self.client.post(self.list_url, self.payload(category="NOPE"), format="json").status_code, 400)

    def test_duplicate_title_returns_409_with_the_existing_document(self):
        self.client.force_authenticate(self.author)
        first = self.client.post(self.list_url, self.payload(), format="json")
        again = self.client.post(self.list_url, self.payload(), format="json")
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.data["code"], "title_exists")
        self.assertEqual(again.data["existing_id"], first.data["id"])
        self.assertTrue(again.data["detail"])

    # -- revise ----------------------------------------------------------

    def test_revise_endpoint(self):
        doc = finalize(new_doc(self.author))
        self.client.force_authenticate(self.author)
        response = self.client.post(reverse("document-revise", args=[doc.pk]))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["full_code"], "PO-01-02")

    def test_revise_conflict_and_permission_and_404(self):
        draft = new_doc(self.author)
        self.client.force_authenticate(self.author)
        self.assertEqual(self.client.post(reverse("document-revise", args=[draft.pk])).status_code, 409)
        self.assertEqual(self.client.post(reverse("document-revise", args=[999999])).status_code, 404)

        self.client.force_authenticate(self.employer)
        finalize(draft)
        self.assertEqual(self.client.post(reverse("document-revise", args=[draft.pk])).status_code, 403)

    # -- list ------------------------------------------------------------

    def test_list_is_paginated_in_insertion_order(self):
        for i in range(30):
            new_doc(self.author, f"سند {i}", DocumentGroup.FORM)
        self.client.force_authenticate(self.author)
        response = self.client.get(self.list_url)
        self.assertEqual(response.data["count"], 30)
        self.assertEqual(len(response.data["results"]), 25)
        self.assertEqual(response.data["results"][0]["full_code"], "FR-01-01")
        page_two = self.client.get(self.list_url, {"page": 2})
        self.assertEqual(len(page_two.data["results"]), 5)

    def test_list_does_not_query_per_row(self):
        for i in range(12):
            doc = new_doc(self.author, f"سند {i}")
            SignOff.objects.create(document=doc, role=SignOffRole.CREATER, name="الف")
        self.client.force_authenticate(self.author)
        with self.assertNumQueries(4):  # count + page + sign-offs + responsibility sections
            self.assertEqual(len(self.client.get(self.list_url).data["results"]), 12)

    def test_filters(self):
        self.client.force_authenticate(self.author)
        new_doc(self.author, "الف", DocumentGroup.POSTER, INSIDE)
        b = new_doc(self.author, "ب", DocumentGroup.FORM, OUTSIDE)
        finalize(b)

        def titles(**params):
            return [r["title"] for r in self.client.get(self.list_url, params).data["results"]]

        self.assertEqual(titles(group=DocumentGroup.FORM), ["ب"])
        self.assertEqual(titles(category=INSIDE), ["الف"])
        self.assertEqual(titles(status=DocumentStatus.UNDER_CONTROL), ["ب"])
        self.assertEqual(titles(group="BOGUS"), [], "an unknown filter value matches nothing")

    def test_row_action(self):
        """documents_01.py:886-902: Print / Finish / Complete."""
        from django.utils import timezone

        complete = new_doc(self.author, "الف")
        finish = new_doc(self.author, "ب")
        Document.objects.filter(pk=finish.pk).update(content_saved_at=timezone.now())
        printed = finalize(new_doc(self.author, "ج"))

        self.client.force_authenticate(self.author)
        by_title = {r["title"]: r for r in self.client.get(self.list_url).data["results"]}
        self.assertEqual(by_title["الف"]["action"], "complete")
        self.assertEqual(by_title["ب"]["action"], "finish")
        self.assertEqual(by_title["ج"]["action"], "print")
        self.assertEqual(complete.action, "complete")
        self.assertEqual(printed.action, "print")

    def test_can_revise_flag(self):
        draft = new_doc(self.author, "الف")
        done = finalize(new_doc(self.author, "ب"))
        superseded = finalize(new_doc(self.author, "ج"))
        services.create_revision(user=self.author, document_id=superseded.pk)

        self.client.force_authenticate(self.author)
        flags = {(r["title"], r["revision"]): r["can_revise"] for r in self.client.get(self.list_url).data["results"]}
        self.assertFalse(flags[("الف", 1)], "draft")
        self.assertTrue(flags[("ب", 1)], "finalized and latest")
        self.assertFalse(flags[("ج", 1)], "finalized but already superseded")
        self.assertFalse(flags[("ج", 2)], "new draft revision")
        self.assertFalse(draft.is_finalized)
        self.assertTrue(done.is_finalized)

    def test_signoffs_and_responsibilities_in_payload(self):
        doc = new_doc(self.author)
        SignOff.objects.create(document=doc, role=SignOffRole.CREATER, name="علی رضایی", position="کارشناس")
        self.client.force_authenticate(self.author)
        row = self.client.get(reverse("document-detail", args=[doc.pk])).data
        self.assertEqual(row["signoffs"]["creater"]["name"], "علی رضایی")
        self.assertIsNone(row["signoffs"]["confirmer"])
        self.assertIsNone(row["signoffs"]["approver"])
        # Not assigned until the designer (Phase 3) can write Responsibilities.
        self.assertEqual(row["responsibilities"], {"accountant": None, "questioner": None, "responder": None})

    def test_retrieve_unknown_is_404(self):
        self.client.force_authenticate(self.author)
        self.assertEqual(self.client.get(reverse("document-detail", args=[999999])).status_code, 404)

    def test_documents_cannot_be_edited_or_deleted_over_the_api(self):
        doc = new_doc(self.author)
        self.client.force_authenticate(self.author)
        url = reverse("document-detail", args=[doc.pk])
        self.assertEqual(self.client.patch(url, {"title": "x"}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class SearchTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)
        self.user = make_user("3000000001")
        self.client.force_authenticate(self.user)
        self.url = reverse("document-list")

        self.control = new_doc(self.user, "روش اجرایی کنترل مستندات", DocumentGroup.PROCEDURE, INSIDE)
        self.poster = new_doc(self.user, "پوستر ایمنی", DocumentGroup.POSTER, OUTSIDE)
        finalize(self.control)
        self.control_r2 = services.create_revision(user=self.user, document_id=self.control.pk)

    def found(self, term):
        response = self.client.get(self.url, {"search": term})
        self.assertEqual(response.status_code, 200)
        return sorted(r["full_code"] for r in response.data["results"])

    def test_by_title_substring(self):
        self.assertEqual(self.found("ایمنی"), ["PO-01-01"])

    def test_arabic_letterforms_match_persian_titles(self):
        # Typed with an Arabic yeh, stored with a Persian one.
        self.assertEqual(self.found("اجرايي"), ["PR-01-01", "PR-01-02"])

    def test_by_family_code_case_insensitive(self):
        self.assertEqual(self.found("pr-01"), ["PR-01-01", "PR-01-02"])

    def test_by_full_code_including_revision(self):
        """V_1.0 searched the raw stored "0-1", so the *displayed* revision
        never matched (documents_01.py:872)."""
        self.assertEqual(self.found("PR-01-02"), ["PR-01-02"])
        self.assertEqual(self.found("pr-01-01"), ["PR-01-01"])

    def test_persian_digits_are_accepted(self):
        self.assertEqual(self.found("PR-۰۱-۰۲"), ["PR-01-02"])

    def test_by_group_label(self):
        self.assertEqual(self.found("پوستر"), ["PO-01-01"])

    def test_by_category_label(self):
        # The exact example in V_1.0's own placeholder (documents_01.py:1597) —
        # which could never match there, since V_1.0 stores the English strings.
        self.assertEqual(self.found("برون سازمانی"), ["PO-01-01"])

    def test_no_match(self):
        self.assertEqual(self.found("چیزی که وجود ندارد"), [])

    def test_blank_search_returns_everything(self):
        self.assertEqual(len(self.found("  ")), 3)

    def test_numbers_of_100_or_more_are_searchable(self):
        """Guards the SQL zero-padding: LPad would truncate '100' to '10'."""
        Document.objects.create(
            category=INSIDE, title="سند صدم", group=DocumentGroup.FORM, number=100, revision=1, created_by=self.user
        )
        doc = Document.objects.get(number=100)
        self.assertEqual(doc.full_code, "FR-100-01")
        self.assertEqual(self.found("fr-100-01"), ["FR-100-01"])
        self.assertEqual(self.found("fr-10-0"), [], "must not match a truncated FR-10")

    def test_percent_and_underscore_are_literal(self):
        self.assertEqual(self.found("%"), [])
        self.assertEqual(self.found("_"), [])


@override_settings(CACHES=LOCMEM_CACHE, RATELIMIT_ENABLE=False)
class DashboardMetricsTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)
        cache.clear()  # locmem outlives a test's DB rollback, which fires no invalidation signals
        self.user = make_user("4000000001")
        self.client.force_authenticate(self.user)
        self.url = reverse("dashboard-metrics")

    def row(self, data, group):
        return next(r for r in data["rows"] if r["group_value"] == group)

    def test_empty_register_has_stable_zero_rows(self):
        data = self.client.get(self.url).data
        self.assertEqual([r["group"] for r in data["rows"]], ["پوستر", "روش اجرایی", "دستورالعمل", "فرم"])
        self.assertTrue(all(r["total"] == 0 for r in data["rows"]))
        self.assertEqual(len(data["statuses"]), 5)

    def test_counts_are_real_and_the_cache_is_invalidated(self):
        self.client.get(self.url)  # warms the 60s cache with zeros
        new_doc(self.user, "الف", DocumentGroup.POSTER)
        done = finalize(new_doc(self.user, "ب", DocumentGroup.POSTER))

        data = self.client.get(self.url).data
        poster = self.row(data, DocumentGroup.POSTER)
        self.assertEqual(poster["total"], 2)
        self.assertEqual(poster["counts"][DocumentStatus.DRAFT], 1)
        self.assertEqual(poster["counts"][DocumentStatus.UNDER_CONTROL], 1)
        self.assertEqual(self.row(data, DocumentGroup.FORM)["total"], 0)

        Document.objects.filter(pk=done.pk).update(status=DocumentStatus.OBSOLETE)
        Document.objects.get(pk=done.pk).save()  # the signal path a real transition takes
        poster = self.row(self.client.get(self.url).data, DocumentGroup.POSTER)
        self.assertEqual(poster["counts"][DocumentStatus.OBSOLETE], 1)

    def test_every_revision_is_counted(self):
        doc = finalize(new_doc(self.user, "الف", DocumentGroup.FORM))
        services.create_revision(user=self.user, document_id=doc.pk)
        form = self.row(self.client.get(self.url).data, DocumentGroup.FORM)
        self.assertEqual(form["total"], 2)


@skipUnlessDBFeature("has_select_for_update")
class ConcurrencyTests(TransactionTestCase):
    """Real threads against a real database. Skipped on SQLite, which has no
    row locks; run in the compose backend container (Postgres)."""

    def setUp(self):
        self.user = make_user("5000000001")

    def run_concurrently(self, worker, n):
        results, barrier = [], threading.Barrier(n)

        def target(i):
            try:
                barrier.wait()
                results.append(("ok", worker(i)))
            except Exception as exc:  # noqa: BLE001 - we assert on the type below
                results.append(("err", exc))
            finally:
                connection.close()

        threads = [threading.Thread(target=target, args=(i,)) for i in range(n)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        return results

    def test_concurrent_creators_get_unique_gapless_numbers(self):
        n = 10
        results = self.run_concurrently(lambda i: new_doc(self.user, f"موازی {i}").number, n)
        self.assertEqual([r for r in results if r[0] == "err"], [])
        self.assertEqual(sorted(number for _, number in results), list(range(1, n + 1)))

    def test_concurrent_creators_of_the_same_title_yield_exactly_one_document(self):
        results = self.run_concurrently(lambda i: new_doc(self.user, "همنام"), 6)
        ok = [r for r in results if r[0] == "ok"]
        errors = [r[1] for r in results if r[0] == "err"]
        self.assertEqual(len(ok), 1)
        self.assertEqual(len(errors), 5)
        self.assertTrue(all(isinstance(e, DocumentConflict) for e in errors), errors)
        self.assertEqual(Document.objects.filter(title="همنام").count(), 1)
        # The five rejected attempts rolled their allocations back.
        self.assertEqual(DocumentSequence.objects.get(group=DocumentGroup.POSTER).last_number, 1)

    def test_concurrent_revisions_of_one_document_yield_exactly_one(self):
        doc = finalize(new_doc(self.user, "بازنگری"))
        results = self.run_concurrently(
            lambda i: services.create_revision(user=self.user, document_id=doc.pk).revision, 6
        )
        self.assertEqual(len([r for r in results if r[0] == "ok"]), 1)
        self.assertTrue(all(isinstance(r[1], DocumentConflict) for r in results if r[0] == "err"))
        self.assertEqual(Document.objects.filter(number=doc.number, group=doc.group).count(), 2)
