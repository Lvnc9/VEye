from django.core.management.base import BaseCommand

from apps.core.constants import DocumentStatus


class Command(BaseCommand):
    help = (
        "Phase 21: ask the audience to read documents already in force that were never distributed "
        "(approved before read acknowledgment existed). Dry run unless --apply."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="write the rows and send the notifications")

    def handle(self, *args, apply=False, **options):
        from apps.distribution import services
        from apps.documents.models import Document

        documents = Document.objects.filter(status=DocumentStatus.UNDER_CONTROL, read_acknowledgments__isnull=True)
        total = 0
        for document in documents.distinct():
            count = services.distribute(document) if apply else len(services.audience(document))
            total += count
            self.stdout.write(f"{document.full_code}: {count}")
        verb = "asked" if apply else "would ask (dry run; add --apply)"
        self.stdout.write(self.style.SUCCESS(f"{verb}: {total} reader(s)"))
