import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from bank.models import BankAccount, Bewegung
from bank.services import _compute_hash
from core.decorators import owner_required

from .forms import BelegUploadForm, PosteingangBulkUploadForm, PosteingangUploadForm
from .matching import _amount_range_filter, bewegungen_matching_amount, find_matching_bewegung
from .models import Beleg
from .services import get_or_create_thumbnail_path, rotate_image_file, rotate_pdf_file
from .statement_parser import parse_statement

logger = logging.getLogger(__name__)

# Begrenzt die Anzahl gleichzeitig angeforderter Thumbnails pro Seitenaufruf:
# jede Vorschau wird beim ersten Abruf serverseitig gerendert (PDF -> PNG),
# zu viele auf einmal überlasten die wenigen gunicorn-Worker (WORKER TIMEOUT).
BELEG_LIST_PAGE_SIZE = 40

# Vorbelegter Zeitraum (in Tagen vor/nach dem Anker-Datum) für die
# Bewegungssuche beim Anhängen eines Belegs an eine weitere Bewegung.
BELEG_COPY_DATE_WINDOW_DAYS = 15


def _redirect_after_beleg_action(beleg):
    if beleg.bewegung_id:
        return redirect("bewegung_detail", pk=beleg.bewegung_id)
    return redirect("posteingang_list")


@login_required
def beleg_list(request):
    belege = Beleg.objects.select_related(
        "bewegung", "bewegung__bank_account", "uploaded_by"
    ).order_by("-uploaded_at")

    document_type = request.GET.get("typ")
    if document_type:
        belege = belege.filter(document_type=document_type)

    bank_account_id = request.GET.get("bank_account")
    if bank_account_id:
        belege = belege.filter(bewegung__bank_account_id=bank_account_id)

    search = request.GET.get("q")
    if search:
        belege = belege.filter(
            Q(original_filename__icontains=search)
            | Q(note__icontains=search)
            | Q(bewegung__description__icontains=search)
        )

    date_from = request.GET.get("von")
    if date_from:
        belege = belege.filter(uploaded_at__date__gte=date_from)
    date_to = request.GET.get("bis")
    if date_to:
        belege = belege.filter(uploaded_at__date__lte=date_to)

    if request.GET.get("ausblenden") == "1":
        belege = belege.exclude(hidden=True)

    paginator = Paginator(belege, BELEG_LIST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("seite"))
    page_obj.object_list = list(page_obj.object_list)

    _attach_group_members(page_obj.object_list)

    context = {
        "belege": page_obj,
        "page_obj": page_obj,
        "document_type_choices": Beleg.DocumentType.choices,
        "bank_accounts": BankAccount.objects.filter(is_active=True),
        "filters": request.GET,
    }
    return render(request, "documents/beleg_list.html", context)


def _attach_group_members(belege):
    """Setzt auf jedem Beleg `group_members`: die anderen Belege (Original
    und/oder weitere Kopien), die über 'an weitere Bewegung anhängen' aus
    demselben Dokument entstanden sind -- für die Anzeige "auch abgelegt
    bei ..." in der Belege-Übersicht."""
    root_ids = {b.source_id or b.id for b in belege}
    related = Beleg.objects.filter(Q(pk__in=root_ids) | Q(source_id__in=root_ids)).select_related(
        "bewegung", "bewegung__bank_account"
    )
    by_root = {}
    for r in related:
        by_root.setdefault(r.source_id or r.id, []).append(r)

    for beleg in belege:
        root_id = beleg.source_id or beleg.id
        beleg.group_members = [m for m in by_root.get(root_id, []) if m.pk != beleg.pk]


@login_required
@owner_required
def beleg_toggle_hidden(request, pk):
    beleg = get_object_or_404(Beleg, pk=pk)
    if request.method == "POST":
        beleg.hidden = not beleg.hidden
        beleg.save(update_fields=["hidden"])
        next_url = request.POST.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
    return _redirect_after_beleg_action(beleg)


@login_required
@owner_required
def beleg_upload(request, bewegung_id):
    bewegung = get_object_or_404(Bewegung, pk=bewegung_id)
    if request.method == "POST":
        files = request.FILES.getlist("file")
        if not files:
            messages.error(request, "Bitte mindestens eine Datei auswählen.")
            return redirect("bewegung_detail", pk=bewegung_id)

        shared_data = {
            "document_type": request.POST.get("document_type", Beleg.DocumentType.QUITTUNG),
            "note": request.POST.get("note", ""),
        }
        uploaded_count = 0
        failed = []
        for uploaded in files:
            form = BelegUploadForm(data=shared_data, files={"file": uploaded})
            if form.is_valid():
                beleg = form.save(commit=False)
                beleg.bewegung = bewegung
                beleg.uploaded_by = request.user
                beleg.original_filename = uploaded.name
                beleg.content_type = getattr(uploaded, "content_type", "") or ""
                beleg.size_bytes = uploaded.size
                beleg.save()
                uploaded_count += 1
            else:
                failed.append(uploaded.name)

        if uploaded_count:
            messages.success(request, f"{uploaded_count} Beleg(e) wurden hochgeladen.")
        if failed:
            messages.error(
                request,
                f"Nicht hochgeladen (ungültiges Format oder zu gross): {', '.join(failed)}",
            )
    return redirect("bewegung_detail", pk=bewegung_id)


@login_required
def beleg_download(request, pk):
    beleg = get_object_or_404(Beleg, pk=pk)
    try:
        file_handle = beleg.file.open("rb")
    except FileNotFoundError:
        raise Http404("Datei nicht gefunden.")
    response = FileResponse(
        file_handle, content_type=beleg.content_type or "application/octet-stream"
    )
    response["Content-Disposition"] = f'inline; filename="{beleg.original_filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def beleg_thumbnail(request, pk):
    beleg = get_object_or_404(Beleg, pk=pk)
    try:
        thumb_path = get_or_create_thumbnail_path(beleg)
    except Exception:
        logger.exception("Vorschau für Beleg %s (content_type=%s) fehlgeschlagen", pk, beleg.content_type)
        raise Http404("Vorschau konnte nicht erzeugt werden.")
    if thumb_path is None:
        raise Http404("Keine Vorschau für diesen Dateityp verfügbar.")
    response = FileResponse(open(thumb_path, "rb"), content_type="image/png")
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@owner_required
def beleg_rotate(request, pk):
    beleg = get_object_or_404(Beleg, pk=pk)
    if request.method == "POST":
        try:
            degrees = float(request.POST.get("degrees", "0"))
        except ValueError:
            degrees = 0
        if degrees:
            try:
                if beleg.content_type == "application/pdf":
                    if degrees % 90 != 0:
                        raise ValueError("Bei PDF-Belegen sind nur 90°-Schritte möglich.")
                    rotate_pdf_file(beleg, int(degrees / 90))
                else:
                    rotate_image_file(beleg, degrees)
                messages.success(request, "Beleg wurde gedreht.")
            except Exception as exc:
                messages.error(request, f"Beleg konnte nicht gedreht werden: {exc}")
    return _redirect_after_beleg_action(beleg)


@login_required
@owner_required
def beleg_delete(request, pk):
    beleg = get_object_or_404(Beleg, pk=pk)
    redirect_response = _redirect_after_beleg_action(beleg)
    if request.method == "POST":
        beleg.file.delete(save=False)
        beleg.delete()
        messages.info(request, "Beleg gelöscht.")
    return redirect_response


@login_required
@owner_required
def posteingang_list(request):
    belege = Beleg.objects.filter(bewegung__isnull=True).select_related("uploaded_by")
    return render(request, "documents/posteingang_list.html", {"belege": belege})


@login_required
@owner_required
def posteingang_upload(request):
    if request.method == "POST":
        form = PosteingangUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded = form.cleaned_data["file"]
            beleg = form.save(commit=False)
            beleg.uploaded_by = request.user
            beleg.original_filename = uploaded.name
            beleg.content_type = getattr(uploaded, "content_type", "") or ""
            beleg.size_bytes = uploaded.size

            match = find_matching_bewegung(
                form.cleaned_data.get("expected_amount"), form.cleaned_data.get("expected_date")
            )
            if match:
                beleg.bewegung = match
                beleg.save()
                messages.success(
                    request,
                    f"Automatisch zugewiesen: Bewegung vom {match.booking_date:%d.%m.%Y} "
                    f"– {match.description} ({match.amount} {match.currency}).",
                )
                return redirect("bewegung_detail", pk=match.pk)
            beleg.bewegung = None
            beleg.save()
            messages.info(request, "Kein eindeutiger Treffer gefunden – Beleg liegt im Posteingang.")
            return redirect("posteingang_list")
        for error in form.errors.get("file", []):
            messages.error(request, error)
    else:
        form = PosteingangUploadForm()
    return render(request, "documents/posteingang_upload.html", {"form": form})


@login_required
@owner_required
def posteingang_bulk_upload(request):
    if request.method == "POST":
        files = request.FILES.getlist("files")
        document_type = request.POST.get("document_type", Beleg.DocumentType.QUITTUNG)
        if not files:
            messages.error(request, "Keine Dateien ausgewählt.")
        created = 0
        failed = []
        for uploaded_file in files:
            form = BelegUploadForm(
                data={"document_type": document_type, "note": ""},
                files={"file": uploaded_file},
            )
            if form.is_valid():
                beleg = form.save(commit=False)
                beleg.bewegung = None
                beleg.uploaded_by = request.user
                beleg.original_filename = uploaded_file.name
                beleg.content_type = getattr(uploaded_file, "content_type", "") or ""
                beleg.size_bytes = uploaded_file.size
                beleg.save()
                created += 1
            else:
                failed.append(uploaded_file.name)
        if created:
            messages.success(request, f"{created} Beleg(e) in den Posteingang hochgeladen.")
        if failed:
            messages.error(
                request,
                f"Nicht hochgeladen (ungültiges Format oder zu gross): {', '.join(failed)}",
            )
        return redirect("posteingang_list")

    form = PosteingangBulkUploadForm()
    return render(request, "documents/posteingang_bulk_upload.html", {"form": form})


@login_required
@owner_required
def beleg_assign(request, pk):
    beleg = get_object_or_404(Beleg, pk=pk)
    if request.method == "POST":
        was_assigned = beleg.bewegung_id is not None
        bewegung_id = request.POST.get("bewegung_id")
        bewegung = get_object_or_404(Bewegung, pk=bewegung_id)
        beleg.bewegung = bewegung
        beleg.save(update_fields=["bewegung"])
        verb = "verschoben zu" if was_assigned else "zugewiesen an"
        messages.success(request, f"Beleg wurde {verb} Bewegung vom {bewegung.booking_date:%d.%m.%Y}.")
        return redirect("bewegung_detail", pk=bewegung.pk)

    query = request.GET.get("q", "")
    amount_query = request.GET.get("betrag", "")

    matches = Bewegung.objects.select_related("bank_account").order_by("-booking_date")
    amount_error = None
    if amount_query:
        try:
            matches = bewegungen_matching_amount(Decimal(amount_query.replace(",", "."))).select_related(
                "bank_account"
            )
        except InvalidOperation:
            amount_error = "Ungültiger Betrag."
    elif query:
        matches = matches.filter(description__icontains=query)
    elif beleg.expected_amount:
        matches = bewegungen_matching_amount(beleg.expected_amount).select_related("bank_account")

    if query and amount_query and not amount_error:
        matches = matches.filter(description__icontains=query)

    matches = matches.order_by("-booking_date")[:30]
    context = {
        "beleg": beleg,
        "matches": matches,
        "query": query,
        "amount_query": amount_query,
        "amount_error": amount_error,
    }
    return render(request, "documents/beleg_assign.html", context)


@login_required
@owner_required
def beleg_copy(request, pk):
    """Hängt eine Kopie eines bereits hochgeladenen Belegs an eine weitere
    Bewegung an, ohne dass die Datei erneut hochgeladen werden muss
    (z.B. eine Kreditkartenabrechnung, die mehrere Bewegungen belegt)."""
    beleg = get_object_or_404(Beleg, pk=pk)
    if request.method == "POST":
        bewegung_id = request.POST.get("bewegung_id")
        bewegung = get_object_or_404(Bewegung, pk=bewegung_id)
        with beleg.file.open("rb") as f:
            file_bytes = f.read()
        copy = Beleg(
            bewegung=bewegung,
            document_type=beleg.document_type,
            uploaded_by=request.user,
            original_filename=beleg.original_filename,
            content_type=beleg.content_type,
            size_bytes=len(file_bytes),
            note=beleg.note or f"Kopie von Beleg #{beleg.pk}",
            source=beleg.source or beleg,
        )
        copy.file.save(beleg.original_filename, ContentFile(file_bytes), save=False)
        copy.save()
        messages.success(
            request,
            f"Beleg wurde zusätzlich an Bewegung vom {bewegung.booking_date:%d.%m.%Y} angehängt.",
        )
        return redirect("bewegung_detail", pk=bewegung.pk)

    has_explicit_filters = any(key in request.GET for key in ("betrag", "von", "bis", "q"))

    anchor_amount = beleg.expected_amount or (abs(beleg.bewegung.amount) if beleg.bewegung_id else None)
    anchor_date = beleg.expected_date or (beleg.bewegung.booking_date if beleg.bewegung_id else None)

    if has_explicit_filters:
        query = request.GET.get("q", "")
        amount_query = request.GET.get("betrag", "")
        von_raw = request.GET.get("von", "")
        bis_raw = request.GET.get("bis", "")
    else:
        # Erstaufruf ohne eigene Suche: Betrag/Zeitraum anhand des Belegs bzw.
        # der aktuell zugewiesenen Bewegung vorschlagen (z.B. bei einer
        # Kreditkarten-Abrechnung, die schon einer Bewegung zugewiesen ist).
        query = ""
        amount_query = str(anchor_amount) if anchor_amount else ""
        if anchor_date:
            von_raw = (anchor_date - timedelta(days=BELEG_COPY_DATE_WINDOW_DAYS)).isoformat()
            bis_raw = (anchor_date + timedelta(days=BELEG_COPY_DATE_WINDOW_DAYS)).isoformat()
        else:
            von_raw = ""
            bis_raw = ""

    matches = Bewegung.objects.select_related("bank_account").exclude(pk=beleg.bewegung_id)

    amount_error = None
    amount_value = None
    if amount_query:
        try:
            amount_value = Decimal(amount_query.replace("'", "").replace(",", "."))
            matches = matches.filter(_amount_range_filter(amount_value))
        except InvalidOperation:
            amount_error = "Ungültiger Betrag."

    if query:
        matches = matches.filter(description__icontains=query)

    date_error = None
    von_date = None
    bis_date = None
    if von_raw:
        try:
            von_date = date.fromisoformat(von_raw)
            matches = matches.filter(booking_date__gte=von_date)
        except ValueError:
            date_error = "Ungültiges Von-Datum."
    if bis_raw:
        try:
            bis_date = date.fromisoformat(bis_raw)
            matches = matches.filter(booking_date__lte=bis_date)
        except ValueError:
            date_error = "Ungültiges Bis-Datum."

    if von_date and bis_date:
        sort_anchor_date = von_date + (bis_date - von_date) / 2
    else:
        sort_anchor_date = von_date or bis_date or anchor_date

    matches = list(matches.order_by("-booking_date")[:200])
    for b in matches:
        b.amount_diff = abs(abs(b.amount) - amount_value) if amount_value is not None else None
        b.date_diff = abs((b.booking_date - sort_anchor_date).days) if sort_anchor_date else None

    matches.sort(
        key=lambda b: (
            b.amount_diff if b.amount_diff is not None else Decimal("0"),
            b.date_diff if b.date_diff is not None else 0,
            -b.booking_date.toordinal(),
        )
    )
    matches = matches[:30]

    context = {
        "beleg": beleg,
        "matches": matches,
        "query": query,
        "amount_query": amount_query,
        "amount_error": amount_error,
        "von": von_raw,
        "bis": bis_raw,
        "date_error": date_error,
    }
    return render(request, "documents/beleg_copy.html", context)


SESSION_KEY_STATEMENT_SCAN = "statement_scan"


@login_required
@owner_required
def statement_scan_upload(request):
    if request.method == "POST":
        bank_account_id = request.POST.get("bank_account")
        uploaded = request.FILES.get("file")
        if not uploaded or not bank_account_id:
            messages.error(request, "Bitte Bankkonto und PDF-Datei auswählen.")
            return redirect("statement_scan_upload")
        if not uploaded.name.lower().endswith(".pdf"):
            messages.error(request, "Bitte eine PDF-Datei hochladen.")
            return redirect("statement_scan_upload")
        if uploaded.size > 15 * 1024 * 1024:
            messages.error(request, "Datei ist zu gross (max. 15 MB).")
            return redirect("statement_scan_upload")

        try:
            from pypdf import PdfReader

            reader = PdfReader(uploaded)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            logger.exception("Kreditkarten-Abrechnung konnte nicht gelesen werden")
            messages.error(request, "PDF konnte nicht gelesen werden.")
            return redirect("statement_scan_upload")

        transactions = parse_statement(text)
        if not transactions:
            messages.info(request, "Es wurden keine Positionen in der PDF gefunden.")
            return redirect("statement_scan_upload")

        uploaded.seek(0)
        temp_path = default_storage.save(f"tmp_statements/{uuid.uuid4()}.pdf", ContentFile(uploaded.read()))

        rows = []
        for i, tx in enumerate(transactions):
            candidates = list(
                bewegungen_matching_amount(tx["amount"])
                .filter(bank_account_id=bank_account_id)
                .select_related("bank_account")
            )
            # Naehste Betrags-Uebereinstimmung zuerst (Toleranz erlaubt kleine
            # Rundungsdifferenzen, soll aber einen exakten Treffer nicht von
            # einer bloss zufaellig aehnlichen anderen Bewegung verdraengen lassen).
            candidates.sort(key=lambda b: (abs(abs(b.amount) - tx["amount"]), -b.booking_date.toordinal()))
            candidates = candidates[:5]
            rows.append(
                {
                    "index": i,
                    "date": tx["date"].isoformat(),
                    "description": tx["description"],
                    "amount": str(tx["amount"]),
                    "candidates": [
                        {
                            "id": b.pk,
                            "date": b.booking_date.isoformat(),
                            "description": b.description,
                            "amount": str(b.amount),
                        }
                        for b in candidates
                    ],
                }
            )

        request.session[SESSION_KEY_STATEMENT_SCAN] = {
            "file_path": temp_path,
            "original_filename": uploaded.name,
            "bank_account_id": bank_account_id,
            "rows": rows,
        }
        return redirect("statement_scan_review")

    bank_accounts = BankAccount.objects.filter(is_active=True)
    return render(request, "documents/statement_scan_upload.html", {"bank_accounts": bank_accounts})


def _create_bewegung_from_statement_row(request, row, bank_account_id):
    """Legt für eine erkannte Position ohne passende Bewegung eine neue
    Bewegung auf dem gescannten Bankkonto an (Datum/Text/Betrag vom
    Formular, mit den erkannten Werten als Fallback). Kreditkarten-Positionen
    sind Ausgaben, Bewegung.amount ist vorzeichenbehaftet (Ausgang negativ)."""
    bank_account = BankAccount.objects.filter(pk=bank_account_id).first()
    if not bank_account:
        return None

    try:
        booking_date = date.fromisoformat(request.POST.get(f"neu_datum_{row['index']}", ""))
    except ValueError:
        booking_date = date.fromisoformat(row["date"])

    description = (request.POST.get(f"neu_text_{row['index']}") or row["description"]).strip()
    if not description:
        return None

    try:
        amount = Decimal(request.POST.get(f"neu_betrag_{row['index']}", "").replace("'", "").replace(",", "."))
    except InvalidOperation:
        amount = Decimal(row["amount"])
    if amount > 0:
        amount = -amount

    dedup_hash = _compute_hash(bank_account.id, booking_date, amount, description)
    bewegung, _ = Bewegung.objects.get_or_create(
        dedup_hash=dedup_hash,
        defaults=dict(
            bank_account=bank_account,
            booking_date=booking_date,
            amount=amount,
            currency=bank_account.currency,
            description=description,
            source=Bewegung.Source.MANUAL,
        ),
    )
    return bewegung


@login_required
@owner_required
def statement_scan_review(request):
    data = request.session.get(SESSION_KEY_STATEMENT_SCAN)
    if not data:
        messages.error(request, "Keine Abrechnung zum Prüfen gefunden. Bitte erneut hochladen.")
        return redirect("statement_scan_upload")

    if request.method == "POST":
        confirmed = 0
        created_bewegungen = 0
        bank_account_id = data.get("bank_account_id")
        for row in data["rows"]:
            bewegung_id = request.POST.get(f"bewegung_{row['index']}")
            bewegung = None
            if bewegung_id:
                bewegung = Bewegung.objects.filter(pk=bewegung_id).first()
            elif request.POST.get(f"neu_{row['index']}") and bank_account_id:
                bewegung = _create_bewegung_from_statement_row(request, row, bank_account_id)
                if bewegung:
                    created_bewegungen += 1

            if not bewegung:
                continue

            with default_storage.open(data["file_path"], "rb") as f:
                file_bytes = f.read()

            beleg = Beleg(
                bewegung=bewegung,
                document_type=Beleg.DocumentType.BANKBELEG,
                uploaded_by=request.user,
                original_filename=data["original_filename"],
                content_type="application/pdf",
                size_bytes=len(file_bytes),
                note=f"Automatisch erkannt: {row['description']} ({row['amount']} CHF)",
            )
            beleg.file.save(data["original_filename"], ContentFile(file_bytes), save=False)
            beleg.save()
            confirmed += 1

        if default_storage.exists(data["file_path"]):
            default_storage.delete(data["file_path"])
        del request.session[SESSION_KEY_STATEMENT_SCAN]

        if confirmed:
            message = f"{confirmed} Beleg(e) zugewiesen."
            if created_bewegungen:
                message += f" Davon {created_bewegungen} neue Bewegung(en) erstellt."
            messages.success(request, message)
        else:
            messages.info(request, "Keine Zuordnung bestätigt.")
        return redirect("posteingang_list")

    return render(request, "documents/statement_scan_review.html", {"rows": data["rows"]})
