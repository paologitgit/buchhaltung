import logging
import re
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.db.models import Exists, OuterRef
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render

from bank.models import Bewegung
from documents.models import Beleg
from ledger.models import FiscalYear, JournalEntry

from .decorators import owner_required

logger = logging.getLogger(__name__)

BACKUP_FILENAME_RE = re.compile(r"^backup_\d{8}_\d{6}\.tar\.gz$")


@login_required
def dashboard(request):
    bankbeleg_exists = Exists(
        Beleg.objects.filter(bewegung_id=OuterRef("pk"), document_type=Beleg.DocumentType.BANKBELEG)
    )
    quittung_exists = Exists(
        Beleg.objects.filter(bewegung_id=OuterRef("pk"), document_type=Beleg.DocumentType.QUITTUNG)
    )
    bewegungen = Bewegung.objects.annotate(has_bankbeleg=bankbeleg_exists, has_quittung=quittung_exists)
    active_bewegungen = bewegungen.exclude(status=Bewegung.Status.IGNORED)

    context = {
        "offen_count": bewegungen.filter(status=Bewegung.Status.OFFEN).count(),
        "missing_quittung_count": active_bewegungen.filter(
            quittung_erforderlich=True, has_quittung=False
        ).count(),
        "missing_bankbeleg_count": active_bewegungen.filter(has_bankbeleg=False).count(),
        "posteingang_count": Beleg.objects.filter(bewegung__isnull=True).count(),
        "booked_count": bewegungen.filter(status=Bewegung.Status.BOOKED).count(),
        "current_fiscal_year": FiscalYear.objects.filter(is_closed=False).order_by("-start_date").first(),
        "recent_entries": JournalEntry.objects.select_related("fiscal_year").order_by("-created_at")[:10],
    }
    return render(request, "core/dashboard.html", context)


@login_required
@owner_required
def backup_list(request):
    backup_dir = Path(settings.BACKUP_DIR)
    backups = []
    if backup_dir.exists():
        for f in sorted(backup_dir.glob("backup_*.tar.gz"), reverse=True):
            backups.append({"name": f.name, "size_mb": round(f.stat().st_size / 1024 / 1024, 1)})
    return render(
        request,
        "core/backup_list.html",
        {"backups": backups, "rclone_remotes": settings.BACKUP_RCLONE_REMOTES},
    )


@login_required
@owner_required
def backup_create(request):
    if request.method == "POST":
        out = StringIO()
        try:
            call_command("backup", stdout=out)
            messages.success(request, "Backup wurde erstellt.")
        except Exception:
            logger.exception("Backup fehlgeschlagen")
            messages.error(request, "Backup ist fehlgeschlagen. Details siehe Server-Log.")
        for line in out.getvalue().splitlines():
            if line:
                messages.info(request, line)
    return redirect("backup_list")


@login_required
@owner_required
def backup_download(request, filename):
    if not BACKUP_FILENAME_RE.match(filename):
        raise Http404
    path = Path(settings.BACKUP_DIR) / filename
    if not path.is_file():
        raise Http404
    response = FileResponse(open(path, "rb"), content_type="application/gzip")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
