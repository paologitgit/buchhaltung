import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from bank.models import Bewegung
from core.decorators import owner_required

from .forms import BelegUploadForm, PosteingangBulkUploadForm, PosteingangUploadForm
from .matching import bewegungen_matching_amount, find_matching_bewegung
from .models import Beleg
from .services import get_or_create_thumbnail_path, rotate_image_file, rotate_pdf_file

logger = logging.getLogger(__name__)


def _redirect_after_beleg_action(beleg):
    if beleg.bewegung_id:
        return redirect("bewegung_detail", pk=beleg.bewegung_id)
    return redirect("posteingang_list")


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
    matches = Bewegung.objects.select_related("bank_account").order_by("-booking_date")
    if query:
        matches = matches.filter(description__icontains=query)
    elif beleg.expected_amount:
        matches = bewegungen_matching_amount(beleg.expected_amount).select_related("bank_account").order_by(
            "-booking_date"
        )
    matches = matches[:30]
    return render(request, "documents/beleg_assign.html", {"beleg": beleg, "matches": matches, "query": query})
