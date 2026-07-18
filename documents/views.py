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
from .services import compute_file_hash, get_or_create_thumbnail_path, rotate_image_file, rotate_pdf_file
from .statement_parser import parse_statement
from .text_extraction import update_extracted_text

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


def _set_file_hash(beleg, file_obj):
    beleg.file_hash = compute_file_hash(file_obj)
    beleg.save(update_fields=["file_hash"])


def _warn_if_duplicate(request, beleg):
    """Meldet, falls eine Datei mit identischem Inhalt schon existiert. Nur
    für frische Uploads gedacht -- bewusste Kopien über 'an weitere Bewegung
    anhängen' sind bereits über 'Auch abgelegt bei' verknüpft und sollen
    hier nicht warnen."""
    if not beleg.file_hash:
        return
    existing = (
        Beleg.objects.filter(file_hash=beleg.file_hash)
        .exclude(pk=beleg.pk)
        .select_related("bewegung")
        .order_by("uploaded_at")
        .first()
    )
    if not existing:
        return
    where = f"Bewegung vom {existing.bewegung.booking_date:%d.%m.%Y}" if existing.bewegung_id else "im Posteingang"
    messages.warning(
        request,
        f"Hinweis: '{beleg.original_filename}' scheint bereits hochgeladen zu sein "
        f"(Beleg vom {existing.uploaded_at:%d.%m.%Y}, {where}). Falls du denselben Beleg "
        f"einer weiteren Bewegung zuordnen willst, nutze dort besser 'An weitere Bewegung "
        f"anhängen' statt eines erneuten Uploads -- so bleiben alle Zuordnungen als eine "
        f"Gruppe nachvollziehbar.",
    )


def _beleg_search_q(search):
    """Volltextsuche über Dateiname, Notiz, Bewegungstext und den aus dem
    Dokument extrahierten Text. Beträge werden tolerant behandelt: "47.20"
    findet auch "47,20", Tausender-Apostrophe im Suchbegriff werden ignoriert."""
    search = search.strip()
    variants = {search, search.replace("'", "")}
    if any(ch.isdigit() for ch in search):
        for variant in list(variants):
            variants.add(variant.replace(",", "."))
            variants.add(variant.replace(".", ","))

    q = Q()
    for variant in variants:
        for field in ("original_filename", "note", "bewegung__description", "extracted_text"):
            q |= Q(**{f"{field}__icontains": variant})
    return q


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
        belege = belege.filter(_beleg_search_q(search))

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
def beleg_duplicates(request):
    """Zeigt Belege mit identischem Dateiinhalt, die aber in getrennte
    source-Gruppen zerfallen -- z.B. weil dieselbe Kreditkarten-Abrechnung
    zweimal unabhängig hochgeladen oder gescannt wurde. Bewusste Kopien über
    'an weitere Bewegung anhängen' bilden bereits eine einzige source-Gruppe
    und tauchen hier nicht auf."""
    all_hashed = (
        Beleg.objects.exclude(file_hash="")
        .select_related("bewegung", "bewegung__bank_account")
        .order_by("uploaded_at")
    )
    by_hash = {}
    for beleg in all_hashed:
        by_hash.setdefault(beleg.file_hash, []).append(beleg)

    groups = []
    for file_hash, members in by_hash.items():
        by_root = {}
        for m in members:
            by_root.setdefault(m.source_id or m.id, []).append(m)
        if len(by_root) < 2:
            continue
        roots = sorted(by_root.items(), key=lambda item: min(m.uploaded_at for m in item[1]))
        groups.append(
            {
                "file_hash": file_hash,
                "roots": roots,
                "canonical_root_id": roots[0][0],
                "total": len(members),
            }
        )

    context = {"groups": groups}
    return render(request, "documents/beleg_duplicates.html", context)


@login_required
@owner_required
def beleg_duplicates_merge(request, file_hash):
    if request.method == "POST":
        members = list(Beleg.objects.filter(file_hash=file_hash))
        if not members:
            messages.error(request, "Keine Belege mit dieser Prüfsumme gefunden.")
            return redirect("beleg_duplicates")

        root_ids = {m.source_id or m.id for m in members}
        try:
            canonical_root_id = int(request.POST.get("canonical_root", ""))
        except (TypeError, ValueError):
            canonical_root_id = None
        if canonical_root_id not in root_ids:
            messages.error(request, "Ungültige Auswahl für die Zusammenführung.")
            return redirect("beleg_duplicates")

        updated = 0
        for other_root_id in root_ids - {canonical_root_id}:
            updated += (
                Beleg.objects.filter(Q(pk=other_root_id) | Q(source_id=other_root_id))
                .exclude(pk=canonical_root_id)
                .update(source_id=canonical_root_id)
            )
        messages.success(request, f"{updated} Beleg(e) zu einer gemeinsamen Gruppe zusammengeführt.")
    return redirect("beleg_duplicates")


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
def beleg_change_type(request, pk):
    beleg = get_object_or_404(Beleg, pk=pk)
    if request.method == "POST":
        document_type = request.POST.get("document_type")
        if document_type in Beleg.DocumentType.values:
            beleg.document_type = document_type
            beleg.save(update_fields=["document_type"])
            messages.success(request, "Beleg-Typ wurde geändert.")
        else:
            messages.error(request, "Ungültiger Beleg-Typ.")
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
                _set_file_hash(beleg, uploaded)
                _warn_if_duplicate(request, beleg)
                update_extracted_text(beleg)
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
    context = {"belege": belege, "document_type_choices": Beleg.DocumentType.choices}
    return render(request, "documents/posteingang_list.html", context)


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
                _set_file_hash(beleg, uploaded)
                _warn_if_duplicate(request, beleg)
                update_extracted_text(beleg)
                messages.success(
                    request,
                    f"Automatisch zugewiesen: Bewegung vom {match.booking_date:%d.%m.%Y} "
                    f"– {match.description} ({match.amount} {match.currency}).",
                )
                return redirect("bewegung_detail", pk=match.pk)
            beleg.bewegung = None
            beleg.save()
            _set_file_hash(beleg, uploaded)
            _warn_if_duplicate(request, beleg)
            update_extracted_text(beleg)
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
                _set_file_hash(beleg, uploaded_file)
                _warn_if_duplicate(request, beleg)
                update_extracted_text(beleg)
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
            extracted_text=beleg.extracted_text,
            file_hash=beleg.file_hash or compute_file_hash(file_bytes),
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
        # Alle bestätigten Zeilen erhalten dieselbe PDF -- Text und Prüfsumme
        # nur einmal berechnen (beim ersten erstellten Beleg) und wiederver-
        # wenden. Der erste Beleg wird zur "source" der übrigen, damit sie als
        # eine zusammengehörige Gruppe ("Auch abgelegt bei") erkennbar bleiben
        # statt als unverbundene Duplikate.
        shared_extracted_text = None
        shared_file_hash = None
        root_beleg = None
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
                source=root_beleg,
            )
            beleg.file.save(data["original_filename"], ContentFile(file_bytes), save=False)
            beleg.save()
            if root_beleg is None:
                root_beleg = beleg
            if shared_file_hash is None:
                shared_file_hash = compute_file_hash(file_bytes)
            beleg.file_hash = shared_file_hash
            beleg.save(update_fields=["file_hash"])
            if shared_extracted_text is None:
                shared_extracted_text = update_extracted_text(beleg)
            else:
                beleg.extracted_text = shared_extracted_text
                beleg.save(update_fields=["extracted_text"])
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
