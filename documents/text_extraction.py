import logging
import re

logger = logging.getLogger(__name__)

# PDFs mit weniger extrahiertem Text als das gelten als Scan ohne Textebene
# und werden zusätzlich durch die OCR geschickt.
MIN_NATIVE_TEXT_CHARS = 40

# OCR-Auflösung: PDF-Seiten werden auf diese Breite gerendert. Höher = besser
# lesbar für Tesseract, aber langsamer.
OCR_RENDER_WIDTH = 1600

# Nur die ersten Seiten eines PDFs werden per OCR gelesen (native Textextraktion
# liest immer alle) -- Belege sind kurz, und OCR kostet Sekunden pro Seite.
OCR_MAX_PAGES = 5

MAX_TEXT_LENGTH = 100_000

OCR_LANGUAGES = "deu+eng"

_WHITESPACE_RE = re.compile(r"[ \t]+")
_MANY_NEWLINES_RE = re.compile(r"\n{3,}")

# Manche PDF-Generatoren (z.B. Stripe-Rechnungen/Belege wie "Receipt-...pdf")
# platzieren jeden Buchstaben einzeln für exaktes Kerning. pypdf fügt dann
# zwischen jedem Zeichen ein Leerzeichen ein ("R e c e i p t" statt
# "Receipt"), was den Text für die Substring-Suche unbrauchbar macht.
_LETTER_SPACED_RUN_RE = re.compile(r"(?:\b\w\b[ ]){2,}\b\w\b")
# Zusätzlich Dezimalbeträge wie "4 7 . 2 0" -> "47.20" -- werden vom obigen
# Muster nicht erfasst, da der Punkt/Komma die Wortgrenze unterbricht.
_SPACED_AMOUNT_RE = re.compile(r"\d(?:[ ]\d)*(?:[ ]?[.,][ ]?\d(?:[ ]\d)*)+")
_LETTER_SPACING_MIN_RATIO = 0.4
_LETTER_SPACING_MIN_TOKENS = 10


def _looks_letter_spaced(text):
    tokens = text.split()
    if len(tokens) < _LETTER_SPACING_MIN_TOKENS:
        return False
    single_char = sum(1 for t in tokens if len(t) == 1)
    return (single_char / len(tokens)) >= _LETTER_SPACING_MIN_RATIO


def _squash_spaces(match):
    return match.group(0).replace(" ", "")


def _collapse_letter_spacing(text):
    if not _looks_letter_spaced(text):
        return text
    text = _LETTER_SPACED_RUN_RE.sub(_squash_spaces, text)
    text = _SPACED_AMOUNT_RE.sub(_squash_spaces, text)
    return text


def _clean_text(text):
    # NUL-Bytes kommen in manchen PDF-Textebenen vor; PostgreSQL lehnt sie
    # in Textfeldern ab (DataError: cannot contain NUL bytes).
    text = text.replace("\x00", "")
    text = _collapse_letter_spacing(text)
    text = _WHITESPACE_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = _MANY_NEWLINES_RE.sub("\n\n", text)
    return text.strip()[:MAX_TEXT_LENGTH]


def _ocr_image(pil_image):
    import pytesseract

    return pytesseract.image_to_string(pil_image, lang=OCR_LANGUAGES)


def _extract_pdf_text(path):
    from pypdf import PdfReader

    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _ocr_pdf(path):
    import pypdfium2 as pdfium

    texts = []
    pdf = pdfium.PdfDocument(path)
    try:
        for page_index in range(min(len(pdf), OCR_MAX_PAGES)):
            page = pdf[page_index]
            width_pt, _ = page.get_size()
            scale = OCR_RENDER_WIDTH / width_pt
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil().convert("RGB")
            texts.append(_ocr_image(image))
    finally:
        pdf.close()
    return "\n".join(texts)


def extract_text(beleg):
    """Extrahiert den Textinhalt eines Belegs: bei PDFs zuerst die native
    Textebene, bei (fast) leerem Ergebnis oder Bildern per Tesseract-OCR.
    Gibt bereinigten Text zurück; Fehler werden geloggt und ergeben ""."""
    try:
        path = beleg.file.path
        if beleg.content_type == "application/pdf":
            text = _clean_text(_extract_pdf_text(path))
            if len(text) >= MIN_NATIVE_TEXT_CHARS:
                return text
            return _clean_text(_ocr_pdf(path))
        if beleg.content_type.startswith("image/"):
            from PIL import Image, ImageOps

            image = Image.open(path)
            image = ImageOps.exif_transpose(image)
            return _clean_text(_ocr_image(image))
    except Exception:
        logger.exception("Textextraktion für Beleg %s fehlgeschlagen", beleg.pk)
    return ""


def update_extracted_text(beleg):
    """Extrahiert den Text und speichert ihn auf dem Beleg."""
    beleg.extracted_text = extract_text(beleg)
    beleg.save(update_fields=["extracted_text"])
    return beleg.extracted_text
