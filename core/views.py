from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef
from django.shortcuts import render

from bank.models import Bewegung
from documents.models import Beleg
from ledger.models import FiscalYear, JournalEntry


@login_required
def dashboard(request):
    beleg_exists = Exists(Beleg.objects.filter(bewegung_id=OuterRef("pk")))
    bewegungen = Bewegung.objects.annotate(has_beleg=beleg_exists)

    context = {
        "offen_count": bewegungen.filter(status=Bewegung.Status.OFFEN).count(),
        "missing_beleg_count": bewegungen.filter(has_beleg=False)
        .exclude(status=Bewegung.Status.IGNORED)
        .count(),
        "booked_count": bewegungen.filter(status=Bewegung.Status.BOOKED).count(),
        "current_fiscal_year": FiscalYear.objects.filter(is_closed=False).order_by("-start_date").first(),
        "recent_entries": JournalEntry.objects.select_related("fiscal_year").order_by("-created_at")[:10],
    }
    return render(request, "core/dashboard.html", context)
