import os
import shutil
import subprocess
import tarfile
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Erstellt ein Backup (Datenbank + Belege) und lädt es optional via rclone in die Cloud hoch."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-upload", action="store_true", help="Nur lokal erstellen, kein rclone-Upload."
        )

    def handle(self, *args, **options):
        backup_dir = Path(settings.BACKUP_DIR)
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        work_dir = backup_dir / f"_tmp_{timestamp}"
        work_dir.mkdir()

        try:
            self._dump_database(work_dir / "database.sql")

            media_src = Path(settings.MEDIA_ROOT) / "belege"
            if media_src.exists():
                shutil.copytree(media_src, work_dir / "belege", ignore=shutil.ignore_patterns("belege_thumbnails"))

            archive_name = f"backup_{timestamp}.tar.gz"
            archive_path = backup_dir / archive_name
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(work_dir, arcname=f"backup_{timestamp}")

            self.stdout.write(self.style.SUCCESS(f"Backup erstellt: {archive_path}"))

            if not options["no_upload"]:
                self._upload(archive_path)

            self._rotate_old_backups(backup_dir)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def _dump_database(self, dump_path):
        db = settings.DATABASES["default"]
        env = os.environ.copy()
        env["PGPASSWORD"] = db["PASSWORD"]
        cmd = [
            "pg_dump",
            "-h", db["HOST"] or "localhost",
            "-p", str(db["PORT"] or 5432),
            "-U", db["USER"],
            "-f", str(dump_path),
            db["NAME"],
        ]
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"pg_dump fehlgeschlagen: {result.stderr}")

    def _upload(self, archive_path):
        remotes = [r.strip() for r in settings.BACKUP_RCLONE_REMOTES if r.strip()]
        if not remotes:
            self.stdout.write("Kein rclone-Remote konfiguriert (BACKUP_RCLONE_REMOTES), Upload übersprungen.")
            return
        if shutil.which("rclone") is None:
            self.stdout.write(self.style.WARNING("rclone ist nicht installiert, Upload übersprungen."))
            return
        for remote in remotes:
            result = subprocess.run(
                ["rclone", "copy", str(archive_path), f"{remote}:buchhaltung-backups/"],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                self.stdout.write(self.style.ERROR(f"Upload zu '{remote}' fehlgeschlagen: {result.stderr}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Hochgeladen zu '{remote}'."))

    def _rotate_old_backups(self, backup_dir):
        cutoff = datetime.now() - timedelta(days=settings.BACKUP_RETENTION_DAYS)
        for f in backup_dir.glob("backup_*.tar.gz"):
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
