import io
import os

from PIL import Image, ImageOps

FORMAT_BY_CONTENT_TYPE = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


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
