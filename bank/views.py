import re
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render

from core.decorators import owner_required
from core.models import CompanySettings
from documents.forms import BelegUploadForm
from documents.models import Beleg
from ledger.models import Account
from ledger.services import book_bewegung
from vat.models import VatCode

from .forms import BewegungBookingForm, CSVImportForm
from .models import BankAccount, Bewegung
from .services import import_csv

ALLOWED_SORT_FIELDS = {
    "booking_date": "booking_date",
    "amount": "amount",
    "description": "description",
    "status": "status",
}

# Bewegungen mit gleichem Buchungstext werden nur zu einer Gruppe zusammen-
# gefasst, wenn es davon MEHR als so viele gibt -- bei wenigen Treffern lohnt
# sich eine eigene Gruppe nicht.
GROUP_MIN_COUNT = 5

_WHITESPACE_RE = re.compile(r"\s+")


def _build_sort_url(request, field, current_sort, current_order):
    params = request.GET.copy()
    new_order = "asc" if (current_sort != field or current_order == "desc") else "desc"
    params["sort"] = field
    params["order"] = new_order
    return f"?{params.urlencode()}"


def _normalize_description(description):
    return _WHITESPACE_RE.sub(" ", description.strip()).lower()


def _group_bewegungen(bewegungen):
    """Fasst Bewegungen mit gleichem Buchungstext zu Gruppen zusammen, wenn es
    davon mehr als GROUP_MIN_COUNT gibt. Reihenfolge innerhalb einer Gruppe
    entspricht der bereits angewendeten Sortierung, Gruppen selbst werden
    alphabetisch nach Beschreibung geordnet."""
    by_description = defaultdict(list)
    for bewegung in bewegungen:
        by_description[_normalize_description(bewegung.description)].append(bewegung)

    groups = []
    ungrouped = []
    for items in by_description.values():
        if len(items) > GROUP_MIN_COUNT:
            groups.append({"label": items[0].description, "count": len(items), "items": items})
        else:
            ungrouped.extend(items)

    groups.sort(key=lambda g: g["label"].lower())
    return groups, ungrouped


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

    bewegungen = list(qs[:500])
    group_by = request.GET.get("gruppieren") == "1"
    groups, ungrouped = _group_bewegungen(bewegungen) if group_by else (None, None)

    context = {
        "bewegungen": bewegungen,
        "group_by": group_by,
        "groups": groups,
        "ungrouped": ungrouped,
        "group_min_count": GROUP_MIN_COUNT,
        "bank_accounts": BankAccount.objects.filter(is_active=True),
        "status_choices": Bewegung.Status.choices,
        "missing_quittung_count": missing_quittung_count,
        "missing_bankbeleg_count": missing_bankbeleg_count,
        "current_sort": sort,
        "current_order": order,
        "sort_links": sort_links,
        "filters": request.GET,
        "gegenkonto_choices": Account.objects.filter(is_active=True, is_bank_account=False),
        "vat_code_choices": VatCode.objects.filter(active=True),
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
                        vat_code=booking_form.cleaned_data.get("vat_code"),
                        user=request.user,
                    )
                    messages.success(request, "Bewegung wurde verbucht.")
                    return redirect("bewegung_detail", pk=pk)
                except ValidationError as exc:
                    for error in exc.messages:
                        messages.error(request, error)
        elif action == "book_private" and can_book:
            privatkonto = CompanySettings.load().privatkonto or Account.objects.filter(code="2850").first()
            if not privatkonto:
                messages.error(
                    request,
                    "Kein Privatkonto konfiguriert. Bitte in den Einstellungen ein Privatkonto festlegen.",
                )
            else:
                try:
                    book_bewegung(bewegung, gegenkonto=privatkonto, vat_code=None, user=request.user)
                    bewegung.quittung_erforderlich = False
                    bewegung.save(update_fields=["quittung_erforderlich"])
                    messages.success(request, "Bewegung wurde als privat verbucht.")
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
        "document_type_choices": Beleg.DocumentType.choices,
    }
    return render(request, "bank/bewegung_detail.html", context)


@login_required
@owner_required
def bewegung_edit_description(request, pk):
    bewegung = get_object_or_404(Bewegung, pk=pk)
    if request.method == "POST":
        if bewegung.journal_entry_id and bewegung.journal_entry.is_locked:
            messages.error(
                request,
                "Diese Bewegung ist gesperrt (Geschäftsjahr abgeschlossen) und kann nicht mehr bearbeitet werden.",
            )
            return redirect("bewegung_detail", pk=pk)

        description = request.POST.get("description", "").strip()
        if not description:
            messages.error(request, "Beschreibung darf nicht leer sein.")
            return redirect("bewegung_detail", pk=pk)

        bewegung.description = description
        bewegung.save(update_fields=["description"])
        # Bereits verbuchte Bewegungen haben eine eigene Kopie des Texts auf
        # der Buchung -- ohne diese mitzuziehen bliebe der Fehler in Journal
        # und Export bestehen.
        if bewegung.journal_entry_id:
            bewegung.journal_entry.description = description[:255]
            bewegung.journal_entry.save(update_fields=["description"])
        messages.success(request, "Beschreibung wurde geändert.")
    return redirect("bewegung_detail", pk=pk)


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
def bewegung_bulk_book(request):
    if request.method == "POST":
        ids = request.POST.getlist("selected")
        gegenkonto_id = request.POST.get("gegenkonto")
        vat_code_id = request.POST.get("vat_code")

        if not ids:
            messages.error(request, "Keine Bewegung ausgewählt.")
            return redirect("bewegung_list")
        if not gegenkonto_id:
            messages.error(request, "Bitte ein Gegenkonto für die Sammelverbuchung auswählen.")
            return redirect("bewegung_list")

        gegenkonto = get_object_or_404(Account, pk=gegenkonto_id, is_active=True, is_bank_account=False)
        vat_code = get_object_or_404(VatCode, pk=vat_code_id, active=True) if vat_code_id else None

        candidates = Bewegung.objects.filter(pk__in=ids, status=Bewegung.Status.OFFEN)
        skipped_not_offen = len(ids) - candidates.count()

        booked = 0
        errors = []
        for bewegung in candidates:
            try:
                book_bewegung(bewegung, gegenkonto, vat_code, request.user)
                booked += 1
            except ValidationError as exc:
                errors.append(f"{bewegung.booking_date:%d.%m.%Y} {bewegung.description}: {'; '.join(exc.messages)}")

        if booked:
            messages.success(request, f"{booked} Bewegung(en) verbucht.")
        for error in errors[:5]:
            messages.error(request, error)
        if skipped_not_offen:
            messages.info(
                request,
                f"{skipped_not_offen} Bewegung(en) übersprungen (nicht mehr offen).",
            )
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
