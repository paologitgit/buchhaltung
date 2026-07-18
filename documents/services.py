import hashlib
import io
import os
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageOps

HASH_CHUNK_SIZE = 1024 * 1024


def compute_file_hash(file_obj):
    """SHA-256 des Dateiinhalts, zur Duplikat-Erkennung. Akzeptiert ein
    file-like Objekt (wird an den Anfang zurückgespult) oder rohe Bytes."""
    if isinstance(file_obj, (bytes, bytearray)):
        return hashlib.sha256(file_obj).hexdigest()

    digest = hashlib.sha256()
    file_obj.seek(0)
    for chunk in iter(lambda: file_obj.read(HASH_CHUNK_SIZE), b""):
        digest.update(chunk)
    file_obj.seek(0)
    return digest.hexdigest()

FORMAT_BY_CONTENT_TYPE = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}

THUMBNAIL_MAX_WIDTH = 800
THUMBNAIL_DIR = Path(settings.MEDIA_ROOT) / "belege_thumbnails"


def get_or_create_thumbnail_path(beleg):
    """Liefert den Pfad zu einer PNG-Vorschau des Belegs und erzeugt sie bei
    Bedarf (einmalig, danach aus dem Cache). Für PDFs wird die erste Seite
    gerendert, für Bilder eine verkleinerte Kopie. Gibt None zurück, wenn für
    den content_type keine Vorschau erzeugt werden kann."""
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    # Auflösung im Dateinamen, damit eine künftige Änderung von
    # THUMBNAIL_MAX_WIDTH alte Cache-Dateien automatisch ungültig macht,
    # statt eine veraltete (falsch aufgelöste) Vorschau weiter auszuliefern.
    thumb_path = THUMBNAIL_DIR / f"{beleg.pk}_{THUMBNAIL_MAX_WIDTH}.png"
    source_path = beleg.file.path

    if thumb_path.exists() and thumb_path.stat().st_mtime >= os.path.getmtime(source_path):
        return thumb_path

    if beleg.content_type == "application/pdf":
        _render_pdf_thumbnail(source_path, thumb_path)
    elif beleg.content_type.startswith("image/"):
        _render_image_thumbnail(source_path, thumb_path)
    else:
        return None
    return thumb_path


def _render_pdf_thumbnail(pdf_path, out_path):
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    try:
        page = pdf[0]
        width_pt, height_pt = page.get_size()
        scale = THUMBNAIL_MAX_WIDTH / width_pt
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil().convert("RGB")
        image.save(out_path, format="PNG")
    finally:
        pdf.close()


def _render_image_thumbnail(image_path, out_path):
    image = Image.open(image_path)
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.thumbnail((THUMBNAIL_MAX_WIDTH, THUMBNAIL_MAX_WIDTH * 3))
    image.save(out_path, format="PNG")


def rotate_image_file(beleg, degrees):
    """Dreht das gespeicherte Bild um `degrees` (positiv = im Uhrzeigersinn)."""
    path = beleg.file.path
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)

    fmt = FORMAT_BY_CONTENT_TYPE.get(beleg.content_type, image.format or "JPEG")
    if fmt == "JPEG" and image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    rotated = image.rotate(-degrees, expand=True, fillcolor="white")
    save_kwargs = {"quality": 92} if fmt == "JPEG" else {}
    rotated.save(path, format=fmt, **save_kwargs)

    beleg.size_bytes = os.path.getsize(path)
    beleg.save(update_fields=["size_bytes"])


def rotate_pdf_file(beleg, quarter_turns):
    """Dreht alle Seiten eines PDF-Belegs um Vielfache von 90 Grad."""
    from pypdf import PdfReader, PdfWriter

    path = beleg.file.path
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(90 * quarter_turns)
        writer.add_page(page)

    buffer = io.BytesIO()
    writer.write(buffer)
    with open(path, "wb") as f:
        f.write(buffer.getvalue())

    beleg.size_bytes = os.path.getsize(path)
    beleg.save(update_fields=["size_bytes"])
