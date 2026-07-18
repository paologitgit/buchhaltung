from django.core.management.base import BaseCommand

from documents.models import Beleg
from documents.services import compute_file_hash


class Command(BaseCommand):
    help = (
        "Berechnet die Datei-Prüfsumme (SHA-256) für bestehende Belege, damit "
        "die Duplikat-Erkennung auch alte Uploads erfasst. Standardmässig nur "
        "Belege ohne Prüfsumme; mit --all werden alle neu berechnet."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Auch Belege neu verarbeiten, die schon eine Prüfsumme haben.",
        )

    def handle(self, *args, **options):
        belege = Beleg.objects.all()
        if not options["all"]:
            belege = belege.filter(file_hash="")

        total = belege.count()
        done = 0
        failed = []
        self.stdout.write(f"{total} Beleg(e) zu verarbeiten ...")

        for beleg in belege.iterator():
            try:
                with beleg.file.open("rb") as f:
                    beleg.file_hash = compute_file_hash(f)
                beleg.save(update_fields=["file_hash"])
            except Exception as exc:
                failed.append(f"#{beleg.pk} {beleg.original_filename}: {exc}")
                continue
            done += 1
            if done % 20 == 0:
                self.stdout.write(f"  {done}/{total} verarbeitet ...")

        self.stdout.write(self.style.SUCCESS(f"Fertig: {done} Beleg(e) verarbeitet."))
        for line in failed:
            self.stdout.write(self.style.ERROR(f"Fehlgeschlagen: {line}"))
