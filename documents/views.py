import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect

from bank.models import Bewegung
from core.decorators import owner_required

from .forms import BelegUploadForm
from .models import Beleg
from .services import get_or_create_thumbnail_path, rotate_image_file, rotate_pdf_file

logger = logging.getLogger(__name__)


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
    return redirect("bewegung_detail", pk=beleg.bewegung_id)


@login_required
@owner_required
def beleg_delete(request, pk):
    beleg = get_object_or_404(Beleg, pk=pk)
    bewegung_id = beleg.bewegung_id
    if request.method == "POST":
        beleg.file.delete(save=False)
        beleg.delete()
        messages.info(request, "Beleg gelöscht.")
    return redirect("bewegung_detail", pk=bewegung_id)
