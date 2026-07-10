import logging
import uuid
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from bank.models import BankAccount, Bewegung
from core.decorators import owner_required

from .forms import BelegUploadForm, PosteingangBulkUploadForm, PosteingangUploadForm
from .matching import bewegungen_matching_amount, find_matching_bewegung
from .models import Beleg
from .services import get_or_create_thumbnail_path, rotate_image_file, rotate_pdf_file
from .statement_parser import parse_statement

logger = logging.getLogger(__name__)


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

    context = {
        "belege": belege[:300],
        "document_type_choices": Beleg.DocumentType.choices,
        "bank_accounts": BankAccount.objects.filter(is_active=True),
        "filters": request.GET,
    }
    return render(request, "documents/beleg_list.html", context)


@login_required
@owner_required
def beleg_upload(request, bewegung_id):
    bewegung = get_object_or_404(Bewegung, pk=bewegung_id)
    if request.method == "POST":
        form = BelegUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded = form.cleaned_data["file"]
            beleg = form.save(commit=False)
            beleg.bewegung = bewegung
            beleg.uploaded_by = request.user
            beleg.original_filename = uploaded.name
            beleg.content_type = getattr(uploaded, "content_type", "") or ""
            beleg.size_bytes = uploaded.size
            beleg.save()
            messages.success(request, "Beleg wurde hochgeladen.")
        else:
            for error in form.errors.get("file", []):
                messages.error(request, error)
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
        )
        copy.file.save(beleg.original_filename, ContentFile(file_bytes), save=False)
        copy.save()
        messages.success(
            request,
            f"Beleg wurde zusätzlich an Bewegung vom {bewegung.booking_date:%d.%m.%Y} angehängt.",
        )
        return redirect("bewegung_detail", pk=bewegung.pk)

    query = request.GET.get("q", "")
    amount_query = request.GET.get("betrag", "")

    matches = Bewegung.objects.select_related("bank_account").exclude(pk=beleg.bewegung_id)
    amount_error = None
    if amount_query:
        try:
            matches = bewegungen_matching_amount(Decimal(amount_query.replace(",", "."))).exclude(
                pk=beleg.bewegung_id
            ).select_related("bank_account")
        except InvalidOperation:
            amount_error = "Ungültiger Betrag."
    elif query:
        matches = matches.filter(description__icontains=query)
    elif beleg.expected_amount:
        matches = bewegungen_matching_amount(beleg.expected_amount).exclude(
            pk=beleg.bewegung_id
        ).select_related("bank_account")

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
            "rows": rows,
        }
        return redirect("statement_scan_review")

    bank_accounts = BankAccount.objects.filter(is_active=True)
    return render(request, "documents/statement_scan_upload.html", {"bank_accounts": bank_accounts})


@login_required
@owner_required
def statement_scan_review(request):
    data = request.session.get(SESSION_KEY_STATEMENT_SCAN)
    if not data:
        messages.error(request, "Keine Abrechnung zum Prüfen gefunden. Bitte erneut hochladen.")
        return redirect("statement_scan_upload")

    if request.method == "POST":
        confirmed = 0
        for row in data["rows"]:
            bewegung_id = request.POST.get(f"bewegung_{row['index']}")
            if not bewegung_id:
                continue
            try:
                bewegung = Bewegung.objects.get(pk=bewegung_id)
            except Bewegung.DoesNotExist:
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
            messages.success(request, f"{confirmed} Beleg(e) zugewiesen.")
        else:
            messages.info(request, "Keine Zuordnung bestätigt.")
        return redirect("posteingang_list")

    return render(request, "documents/statement_scan_review.html", {"rows": data["rows"]})
