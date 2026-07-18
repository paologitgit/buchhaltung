import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections


class Command(BaseCommand):
    help = (
        "Stellt ein Backup (Datenbank + Belege) wieder her. Ohne Argument werden "
        "die verfügbaren Backups aufgelistet. ACHTUNG: Überschreibt alle aktuellen "
        "Daten -- vorher wird automatisch ein Sicherheits-Backup erstellt."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "archive",
            nargs="?",
            help="Pfad zum Backup-Archiv (backup_*.tar.gz). Weglassen, um verfügbare Backups aufzulisten.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Bestätigt, dass alle aktuellen Daten mit dem Backup überschrieben werden sollen.",
        )
        parser.add_argument(
            "--no-safety-backup",
            action="store_true",
            help="Kein Sicherheits-Backup des aktuellen Stands vor der Wiederherstellung erstellen.",
        )

    def handle(self, *args, **options):
        if not options["archive"]:
            self._list_backups()
            return

        archive_path = Path(options["archive"])
        if not archive_path.exists():
            # Auch relative Angabe im Backup-Ordner erlauben (nur Dateiname).
            candidate = Path(settings.BACKUP_DIR) / archive_path.name
            if candidate.exists():
                archive_path = candidate
            else:
                raise CommandError(f"Archiv nicht gefunden: {options['archive']}")

        if not options["yes"]:
            raise CommandError(
                "Wiederherstellen überschreibt ALLE aktuellen Daten (Datenbank und Belege). "
                "Zum Bestätigen den Befehl mit --yes erneut ausführen.\n"
                f"  python manage.py restore {archive_path} --yes"
            )

        if not options["no_safety_backup"]:
            self.stdout.write("Erstelle Sicherheits-Backup des aktuellen Stands ...")
            call_command("backup", "--no-upload")

        with tempfile.TemporaryDirectory(dir=settings.BACKUP_DIR) as tmp:
            extract_dir = Path(tmp)
            self.stdout.write(f"Entpacke {archive_path.name} ...")
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(extract_dir, filter="data")

            # Archivinhalt liegt in einem Unterordner backup_<timestamp>/
            subdirs = [d for d in extract_dir.iterdir() if d.is_dir()]
            if len(subdirs) != 1:
                raise CommandError(f"Unerwartete Archivstruktur: {[d.name for d in extract_dir.iterdir()]}")
            content_dir = subdirs[0]

            dump_path = content_dir / "database.sql"
            if not dump_path.exists():
                raise CommandError("Archiv enthält keine database.sql -- kein gültiges Backup.")

            self._restore_database(dump_path)
            self._restore_belege(content_dir / "belege")

        self.stdout.write(self.style.SUCCESS("Wiederherstellung abgeschlossen."))
        self.stdout.write(
            "Hinweis: Vorschau-Cache wurde geleert; Vorschauen werden beim ersten Aufruf neu erzeugt."
        )

    def _list_backups(self):
        backup_dir = Path(settings.BACKUP_DIR)
        backups = sorted(backup_dir.glob("backup_*.tar.gz"))
        if not backups:
            self.stdout.write("Keine Backups gefunden in " + str(backup_dir))
            return
        self.stdout.write("Verfügbare Backups:")
        for b in backups:
            size_mb = b.stat().st_size / (1024 * 1024)
            self.stdout.write(f"  {b.name}  ({size_mb:.1f} MB)")
        self.stdout.write("")
        self.stdout.write("Wiederherstellen mit:")
        self.stdout.write(f"  python manage.py restore {backups[-1].name} --yes")

    def _restore_database(self, dump_path):
        self.stdout.write("Stelle Datenbank wieder her ...")
        db = settings.DATABASES["default"]
        env = os.environ.copy()
        env["PGPASSWORD"] = db["PASSWORD"]
        host = db["HOST"] or "localhost"
        port = str(db["PORT"] or 5432)

        # Offene Django-Verbindungen schliessen, damit das Neuerstellen des
        # Schemas nicht an einer eigenen Session scheitert.
        connections.close_all()

        # Bestehendes Schema komplett ersetzen, damit auch Tabellen/Zeilen
        # verschwinden, die es zum Backup-Zeitpunkt noch nicht gab.
        reset_sql = "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
        result = subprocess.run(
            ["psql", "-h", host, "-p", port, "-U", db["USER"], "-d", db["NAME"], "-c", reset_sql],
            env=env, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise CommandError(f"Zurücksetzen des Schemas fehlgeschlagen: {result.stderr}")

        result = subprocess.run(
            ["psql", "-h", host, "-p", port, "-U", db["USER"], "-d", db["NAME"],
             "-v", "ON_ERROR_STOP=1", "-f", str(dump_path)],
            env=env, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise CommandError(f"Einspielen des Datenbank-Dumps fehlgeschlagen: {result.stderr}")

    def _restore_belege(self, belege_src):
        media_root = Path(settings.MEDIA_ROOT)
        belege_dst = media_root / "belege"
        thumbs_dst = media_root / "belege_thumbnails"

        self.stdout.write("Stelle Belege wieder her ...")
        if belege_dst.exists():
            shutil.rmtree(belege_dst)
        if belege_src.exists():
            shutil.copytree(belege_src, belege_dst)
        else:
            self.stdout.write(self.style.WARNING("Archiv enthält keine Belege (Ordner fehlt)."))

        # Thumbnails passen nach dem Restore nicht mehr zwingend zu den
        # Dateien (gleiche pk, anderer Inhalt) -- Cache leeren.
        if thumbs_dst.exists():
            shutil.rmtree(thumbs_dst)
