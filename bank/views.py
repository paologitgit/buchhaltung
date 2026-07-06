from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render

from core.decorators import owner_required
from documents.forms import BelegUploadForm
from documents.models import Beleg
from ledger.services import book_bewegung

from .forms import BewegungBookingForm, CSVImportForm
from .models import BankAccount, Bewegung
from .services import import_csv

ALLOWED_SORT_FIELDS = {
    "booking_date": "booking_date",
    "amount": "amount",
    "description": "description",
    "status": "status",
}


def _build_sort_url(request, field, current_sort, current_order):
    params = request.GET.copy()
    new_order = "asc" if (current_sort != field or current_order == "desc") else "desc"
    params["sort"] = field
    params["order"] = new_order
    return f"?{params.urlencode()}"


def _beleg_exists(document_type):
    return Exists(Beleg.objects.filter(bewegung_id=OuterRef("pk"), document_type=document_type))


@login_required
def bewegung_list(request):
    bankbeleg_exists = _beleg_exists(Beleg.DocumentType.BANKBELEG)
    quittung_exists = _beleg_exists(Beleg.DocumentType.QUITTUNG)
    qs = Bewegung.objects.select_related("bank_account", "assigned_account", "vat_code").annotate(
        has_bankbeleg=bankbeleg_exists, has_quittung=quittung_exists
    )

    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)

    if request.GET.get("fehlende_quittung") == "1":
        qs = qs.filter(quittung_erforderlich=True, has_quittung=False)
    if request.GET.get("fehlender_bankbeleg") == "1":
        qs = qs.filter(has_bankbeleg=False)

    bank_account_id = request.GET.get("bank_account")
    if bank_account_id:
        qs = qs.filter(bank_account_id=bank_account_id)

    date_from = request.GET.get("von")
    if date_from:
        qs = qs.filter(booking_date__gte=date_from)
    date_to = request.GET.get("bis")
    if date_to:
        qs = qs.filter(booking_date__lte=date_to)

    search = request.GET.get("q")
    if search:
        qs = qs.filter(description__icontains=search)

    sort = request.GET.get("sort", "booking_date")
    order = request.GET.get("order", "desc")
    sort_field = ALLOWED_SORT_FIELDS.get(sort, "booking_date")
    qs = qs.order_by(sort_field if order == "asc" else f"-{sort_field}", "-id")

    active_bewegungen = Bewegung.objects.exclude(status=Bewegung.Status.IGNORED)
    missing_quittung_count = (
        active_bewegungen.annotate(has_quittung=quittung_exists)
        .filter(quittung_erforderlich=True, has_quittung=False)
        .count()
    )
    missing_bankbeleg_count = (
        active_bewegungen.annotate(has_bankbeleg=bankbeleg_exists).filter(has_bankbeleg=False).count()
    )

    sort_links = {
        field: _build_sort_url(request, field, sort, order) for field in ALLOWED_SORT_FIELDS
    }

    context = {
        "bewegungen": qs[:500],
        "bank_accounts": BankAccount.objects.filter(is_active=True),
        "status_choices": Bewegung.Status.choices,
        "missing_quittung_count": missing_quittung_count,
        "missing_bankbeleg_count": missing_bankbeleg_count,
        "current_sort": sort,
        "current_order": order,
        "sort_links": sort_links,
        "filters": request.GET,
    }
    return render(request, "bank/bewegung_list.html", context)


@login_required
def bewegung_detail(request, pk):
    bewegung = get_object_or_404(
        Bewegung.objects.select_related("bank_account", "assigned_account", "vat_code", "journal_entry"),
        pk=pk,
    )
    belege = bewegung.belege.all()
    has_quittung = any(b.document_type == Beleg.DocumentType.QUITTUNG for b in belege)
    has_bankbeleg = any(b.document_type == Beleg.DocumentType.BANKBELEG for b in belege)
    can_book = request.user.has_write_access() and bewegung.status == Bewegung.Status.OFFEN

    booking_form = BewegungBookingForm() if can_book else None
    upload_form = BelegUploadForm() if request.user.has_write_access() else None

    if request.method == "POST" and request.user.has_write_access():
        action = request.POST.get("action")
        if action == "book" and can_book:
            booking_form = BewegungBookingForm(request.POST)
            if booking_form.is_valid():
                try:
                    book_bewegung(
                        bewegung,
                        gegenkonto=booking_form.cleaned_data["gegenkonto"],
                        vat_code=booking_form.cleaned_data["vat_code"],
                        user=request.user,
                    )
                    messages.success(request, "Bewegung wurde verbucht.")
                    return redirect("bewegung_detail", pk=pk)
                except ValidationError as exc:
                    for error in exc.messages:
                        messages.error(request, error)
        elif action == "ignore" and bewegung.status == Bewegung.Status.OFFEN:
            bewegung.status = Bewegung.Status.IGNORED
            bewegung.save(update_fields=["status"])
            messages.info(request, "Bewegung als ignoriert markiert.")
            return redirect("bewegung_detail", pk=pk)
        elif action == "toggle_quittung_required":
            bewegung.quittung_erforderlich = not bewegung.quittung_erforderlich
            bewegung.save(update_fields=["quittung_erforderlich"])
            if bewegung.quittung_erforderlich:
                messages.info(request, "Quittung ist für diese Bewegung wieder erforderlich.")
            else:
                messages.info(request, "Für diese Bewegung wird keine Quittung mehr verlangt.")
            return redirect("bewegung_detail", pk=pk)

    context = {
        "bewegung": bewegung,
        "belege": belege,
        "has_quittung": has_quittung,
        "has_bankbeleg": has_bankbeleg,
        "booking_form": booking_form,
        "upload_form": upload_form,
        "can_book": can_book,
    }
    return render(request, "bank/bewegung_detail.html", context)


@login_required
@owner_required
def bewegung_delete(request, pk):
    bewegung = get_object_or_404(Bewegung, pk=pk)
    if request.method == "POST":
        if bewegung.status == Bewegung.Status.BOOKED:
            messages.error(
                request,
                "Verbuchte Bewegungen können hier nicht gelöscht werden "
                "(die zugehörige Buchung müsste sonst zusätzlich entfernt werden).",
            )
            return redirect("bewegung_detail", pk=pk)
        bewegung.delete()
        messages.success(request, "Bewegung gelöscht.")
        return redirect("bewegung_list")
    return redirect("bewegung_detail", pk=pk)


@login_required
@owner_required
def bewegung_bulk_delete(request):
    if request.method == "POST":
        ids = request.POST.getlist("selected")
        qs = Bewegung.objects.filter(pk__in=ids)
        skipped = qs.filter(status=Bewegung.Status.BOOKED).count()
        deletable = qs.exclude(status=Bewegung.Status.BOOKED)
        deleted_count = deletable.count()
        deletable.delete()
        if deleted_count:
            messages.success(request, f"{deleted_count} Bewegung(en) gelöscht.")
        if skipped:
            messages.error(
                request,
                f"{skipped} bereits verbuchte Bewegung(en) wurden übersprungen (nicht gelöscht).",
            )
        if not deleted_count and not skipped:
            messages.info(request, "Keine Bewegung ausgewählt.")
    return redirect("bewegung_list")


@login_required
@owner_required
def import_view(request):
    if request.method == "POST":
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                batch = import_csv(
                    form.cleaned_data["bank_account"], form.cleaned_data["csv_file"], request.user
                )
                messages.success(
                    request,
                    f"Import abgeschlossen: {batch.created_count} neue Bewegungen, "
                    f"{batch.duplicate_count} Duplikate übersprungen ({batch.row_count} Zeilen gelesen).",
                )
                return redirect("bewegung_list")
            except ValidationError as exc:
                messages_list = exc.messages if hasattr(exc, "messages") else [str(exc)]
                for error in messages_list:
                    messages.error(request, error)
    else:
        form = CSVImportForm()
    return render(request, "bank/import_form.html", {"form": form})
