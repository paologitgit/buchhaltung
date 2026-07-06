from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef
from django.shortcuts import render

from bank.models import Bewegung
from documents.models import Beleg
from ledger.models import FiscalYear, JournalEntry


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
        "missing_quittung_count": active_bewegungen.filter(has_quittung=False).count(),
        "missing_bankbeleg_count": active_bewegungen.filter(has_bankbeleg=False).count(),
        "posteingang_count": Beleg.objects.filter(bewegung__isnull=True).count(),
        "booked_count": bewegungen.filter(status=Bewegung.Status.BOOKED).count(),
        "current_fiscal_year": FiscalYear.objects.filter(is_closed=False).order_by("-start_date").first(),
        "recent_entries": JournalEntry.objects.select_related("fiscal_year").order_by("-created_at")[:10],
    }
    return render(request, "core/dashboard.html", context)
