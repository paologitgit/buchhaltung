from django.core.management.base import BaseCommand

from documents.models import Beleg
from documents.text_extraction import update_extracted_text


class Command(BaseCommand):
    help = (
        "Extrahiert den Textinhalt (PDF-Text bzw. OCR) für bestehende Belege, "
        "damit die Volltextsuche auch alte Uploads findet. Standardmässig nur "
        "Belege ohne bereits extrahierten Text; mit --all werden alle neu gelesen."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Auch Belege neu verarbeiten, die schon extrahierten Text haben.",
        )

    def handle(self, *args, **options):
        belege = Beleg.objects.all()
        if not options["all"]:
            belege = belege.filter(extracted_text="")

        total = belege.count()
        done = 0
        empty = 0
        failed = []
        self.stdout.write(f"{total} Beleg(e) zu verarbeiten ...")

        for beleg in belege.iterator():
            try:
                text = update_extracted_text(beleg)
            except Exception as exc:
                failed.append(f"#{beleg.pk} {beleg.original_filename}: {exc}")
                continue
            done += 1
            if not text:
                empty += 1
            if done % 20 == 0:
                self.stdout.write(f"  {done}/{total} verarbeitet ...")

        self.stdout.write(
            self.style.SUCCESS(
                f"Fertig: {done} Beleg(e) verarbeitet, davon {empty} ohne erkennbaren Text."
            )
        )
        for line in failed:
            self.stdout.write(self.style.ERROR(f"Fehlgeschlagen: {line}"))
