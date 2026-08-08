"""PDF-Berichte im Stil der Treuhand-Auswertungen: Kontoblätter (optional mit
angehängten Belegen) sowie Bilanz + Erfolgsrechnung mit Vorjahresvergleich."""

import io
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from core.models import CompanySettings

from .models import Account, FiscalYear, JournalLine
from .reports import BILANZ_TYPES, _account_sums, _signed_balance, bilanz, erfolgsrechnung, kontoblatt

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 15 * mm
USABLE_WIDTH = PAGE_WIDTH - 2 * MARGIN

GRID_COLOR = colors.Color(0.75, 0.75, 0.75)

STYLE_TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=12, leading=15)
STYLE_SUBTITLE = ParagraphStyle("subtitle", fontName="Helvetica", fontSize=9, leading=12)
STYLE_SECTION = ParagraphStyle(
    "section", fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=10, spaceAfter=4
)
STYLE_CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=8, leading=10)


def _chf(amount):
    """Schweizer Zahlenformat: 15'197.17; leere Zelle für None."""
    if amount is None:
        return ""
    quantized = amount.quantize(Decimal("0.01"))
    sign = "-" if quantized < 0 else ""
    digits, cents = f"{abs(quantized):.2f}".split(".")
    groups = []
    while digits:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    return f"{sign}{'’'.join(groups)}.{cents}"


def _pct(amount, base):
    if base in (None, 0) or amount is None:
        return ""
    return f"{(amount / base * 100).quantize(Decimal('0.1'))}"


def _company_name():
    return CompanySettings.load().firmenname


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.black)
    canvas.drawString(MARGIN, 10 * mm, timezone.localdate().strftime("%d.%m.%Y"))
    name = _company_name()
    if name:
        canvas.drawCentredString(PAGE_WIDTH / 2, 10 * mm, name)
    canvas.drawRightString(PAGE_WIDTH - MARGIN, 10 * mm, f"Seite {doc.page}")
    canvas.restoreState()


def _build_doc(buffer):
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=18 * mm,
    )
    frame = Frame(MARGIN, 18 * mm, USABLE_WIDTH, PAGE_HEIGHT - MARGIN - 18 * mm, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_footer)])
    return doc


# ---------------------------------------------------------------------------
# Kontoblätter


def _beleg_group_key(beleg):
    """Belege, die Kopien desselben Dokuments sind (identischer Dateiinhalt
    bzw. source-Gruppe), teilen sich eine Beleg-Nummer. Prüfsumme zuerst:
    sie fasst auch Original und Kopie zusammen, die beide dieselbe Datei
    tragen, aber unterschiedliche source-Wurzeln hätten."""
    if beleg.file_hash:
        return ("hash", beleg.file_hash)
    if beleg.source_id:
        return ("root", beleg.source_id)
    return ("pk", beleg.pk)


def _collect_kontoblatt_data(fiscal_year):
    """Kontoblatt-Daten aller Konten mit Aktivität, plus Beleg-Nummerierung.

    Gibt (sections, numbered_belege) zurück; sections sind kontoblatt()-Dicts
    ergänzt um 'gegenkonto' und 'beleg_nr' je Zeile, numbered_belege ist die
    Liste der zu druckenden Belege in Nummern-Reihenfolge."""
    from bank.models import Bewegung

    accounts = list(Account.objects.order_by("code"))
    period_sums = _account_sums(accounts, date_from=fiscal_year.start_date, date_to=fiscal_year.end_date)
    opening_sums = _account_sums(accounts, date_to=fiscal_year.start_date - timedelta(days=1))

    active_accounts = []
    for account in accounts:
        p = period_sums.get(account.id)
        o = opening_sums.get(account.id) if account.account_type in BILANZ_TYPES else None
        has_opening = o and _signed_balance(account.account_type, o[0], o[1]) != 0
        if p or has_opening:
            active_accounts.append(account)

    sections = [kontoblatt(account, fiscal_year) for account in active_accounts]

    # Gegenkonto je Zeile: andere Konten desselben Journaleintrags.
    entry_ids = {
        row["line"].journal_entry_id for section in sections for row in section["entries"]
    }
    lines_by_entry = {}
    for line in JournalLine.objects.filter(journal_entry_id__in=entry_ids).select_related("account"):
        lines_by_entry.setdefault(line.journal_entry_id, []).append(line)

    # Beleg-Nummern je Journaleintrag (über die verknüpfte Bewegung).
    bewegungen = Bewegung.objects.filter(journal_entry_id__in=entry_ids).prefetch_related("belege")
    belege_by_entry = {}
    for bewegung in bewegungen:
        belege_by_entry[bewegung.journal_entry_id] = list(bewegung.belege.all())

    numbered_belege = []
    number_by_group = {}
    entry_beleg_nr = {}

    def _number_for(entry_id):
        if entry_id in entry_beleg_nr:
            return entry_beleg_nr[entry_id]
        numbers = []
        for beleg in belege_by_entry.get(entry_id, []):
            key = _beleg_group_key(beleg)
            if key not in number_by_group:
                number_by_group[key] = len(numbered_belege) + 1
                numbered_belege.append(beleg)
            numbers.append(number_by_group[key])
        label = "/".join(str(n) for n in sorted(set(numbers))) if numbers else ""
        entry_beleg_nr[entry_id] = label
        return label

    for section in sections:
        for row in section["entries"]:
            line = row["line"]
            others = [
                other.account.code
                for other in lines_by_entry.get(line.journal_entry_id, [])
                if other.pk != line.pk and other.account_id != line.account_id
            ]
            unique_others = sorted(set(others))
            if len(unique_others) == 1:
                row["gegenkonto"] = unique_others[0]
            elif unique_others:
                row["gegenkonto"] = "div."
            else:
                row["gegenkonto"] = ""
            row["beleg_nr"] = _number_for(line.journal_entry_id)

    return sections, numbered_belege


def kontoblaetter_pdf(fiscal_year):
    """Kontoblätter aller bebuchten Konten als PDF. Gibt (BytesIO,
    numbered_belege) zurück -- die Beleg-Liste für den Anhang-Modus."""
    sections, numbered_belege = _collect_kontoblatt_data(fiscal_year)

    buffer = io.BytesIO()
    doc = _build_doc(buffer)
    story = []

    name = _company_name()
    if name:
        story.append(Paragraph(name, STYLE_SUBTITLE))
    story.append(Paragraph("Kontoblätter", STYLE_TITLE))
    story.append(
        Paragraph(
            f"Geschäftsjahr {fiscal_year.start_date:%d.%m.%Y} – {fiscal_year.end_date:%d.%m.%Y}, Währung CHF",
            STYLE_SUBTITLE,
        )
    )
    story.append(Spacer(1, 6))

    col_widths = [22 * mm, 63 * mm, 20 * mm, 14 * mm, 20 * mm, 20 * mm, 21 * mm]
    header = ["Datum", "Text", "Gegenkonto", "Beleg", "Soll", "Haben", "Saldo"]

    base_style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]

    for section in sections:
        account = section["account"]
        story.append(Paragraph(f"Konto {account.code} {account.name}", STYLE_SECTION))

        data = [header]
        style = list(base_style)
        if account.account_type in BILANZ_TYPES:
            data.append(["", "Saldovortrag", "", "", "", "", _chf(section["opening_balance"])])
        for row in section["entries"]:
            line = row["line"]
            data.append(
                [
                    line.journal_entry.date.strftime("%d.%m.%Y"),
                    Paragraph(line.journal_entry.description, STYLE_CELL),
                    row["gegenkonto"],
                    row["beleg_nr"],
                    _chf(line.debit_amount) if line.debit_amount else "",
                    _chf(line.credit_amount) if line.credit_amount else "",
                    _chf(row["running_balance"]),
                ]
            )
        data.append(["", "Schlusssaldo", "", "", "", "", _chf(section["closing_balance"])])
        style.append(("FONT", (0, len(data) - 1), (-1, len(data) - 1), "Helvetica-Bold", 8))
        style.append(("LINEABOVE", (0, len(data) - 1), (-1, len(data) - 1), 0.5, colors.black))

        story.append(Table(data, colWidths=col_widths, repeatRows=1, style=TableStyle(style)))

    doc.build(story)
    buffer.seek(0)
    return buffer, numbered_belege


# ---------------------------------------------------------------------------
# Belege anhängen


def _beleg_stamp_overlay(text, page_width, page_height):
    """Kleine 'Beleg N'-Markierung oben rechts als Overlay-PDF-Seite."""
    from reportlab.pdfgen import canvas as rl_canvas

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(page_width, page_height))
    c.setFont("Helvetica-Bold", 11)
    text_width = c.stringWidth(text, "Helvetica-Bold", 11)
    x = page_width - text_width - 18
    y = page_height - 24
    c.setFillColor(colors.white)
    c.rect(x - 6, y - 5, text_width + 12, 20, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.rect(x - 6, y - 5, text_width + 12, 20, fill=0, stroke=1)
    c.drawString(x, y, text)
    c.save()
    buf.seek(0)
    return buf


def _image_beleg_to_pdf(beleg):
    """Bild-Beleg als A4-PDF-Seite (eingepasst, Seitenverhältnis erhalten)."""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas

    from PIL import Image, ImageOps

    image = Image.open(beleg.file.path)
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    max_w = PAGE_WIDTH - 2 * MARGIN
    max_h = PAGE_HEIGHT - 2 * MARGIN
    scale = min(max_w / image.width, max_h / image.height)
    draw_w, draw_h = image.width * scale, image.height * scale
    c.drawImage(
        ImageReader(image),
        (PAGE_WIDTH - draw_w) / 2,
        PAGE_HEIGHT - MARGIN - draw_h,
        width=draw_w,
        height=draw_h,
    )
    c.save()
    buf.seek(0)
    return buf


def append_belege(main_pdf, numbered_belege):
    """Hängt die nummerierten Belege an das Kontoblätter-PDF an; jeder Beleg
    erhält auf seiner ersten Seite einen 'Beleg N'-Stempel oben rechts."""
    import logging

    from pypdf import PdfReader, PdfWriter

    logger = logging.getLogger(__name__)

    writer = PdfWriter()
    writer.append(PdfReader(main_pdf))

    for number, beleg in enumerate(numbered_belege, start=1):
        try:
            if beleg.content_type == "application/pdf":
                reader = PdfReader(beleg.file.path)
            elif beleg.content_type.startswith("image/"):
                reader = PdfReader(_image_beleg_to_pdf(beleg))
            else:
                continue
            first = reader.pages[0]
            overlay = PdfReader(
                _beleg_stamp_overlay(
                    f"Beleg {number}", float(first.mediabox.width), float(first.mediabox.height)
                )
            ).pages[0]
            first.merge_page(overlay)
            writer.append(reader)
        except Exception:
            logger.exception("Beleg %s konnte nicht angehängt werden", beleg.pk)

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out


# ---------------------------------------------------------------------------
# Bilanz + Erfolgsrechnung mit Vorjahresvergleich


def _previous_fiscal_year(fiscal_year):
    return (
        FiscalYear.objects.filter(end_date__lt=fiscal_year.start_date).order_by("-end_date").first()
    )


def _rows_by_account(rows):
    return {row["account"].id: row["balance"] for row in rows}


def jahresabschluss_pdf(fiscal_year):
    """Bilanz per Stichtag und Erfolgsrechnung der Periode als PDF, mit
    Vorjahresspalte (falls ein Vorjahres-Geschäftsjahr erfasst ist) und
    %-Spalten (Bilanz: Anteil an Total Aktiven, ER: Anteil am Ertrag)."""
    data = bilanz(fiscal_year)
    er = erfolgsrechnung(fiscal_year)

    prev_fy = _previous_fiscal_year(fiscal_year)
    prev_bilanz = bilanz(prev_fy) if prev_fy else None
    prev_er = erfolgsrechnung(prev_fy) if prev_fy else None

    prev_aktiva = _rows_by_account(prev_bilanz["aktiva_rows"]) if prev_bilanz else {}
    prev_passiva = _rows_by_account(prev_bilanz["passiva_rows"]) if prev_bilanz else {}
    prev_aufwand = _rows_by_account(prev_er["aufwand_rows"]) if prev_er else {}
    prev_ertrag = _rows_by_account(prev_er["ertrag_rows"]) if prev_er else {}

    buffer = io.BytesIO()
    doc = _build_doc(buffer)
    story = []

    name = _company_name()
    if name:
        story.append(Paragraph(name, STYLE_SUBTITLE))

    col_widths = [20 * mm, 80 * mm, 25 * mm, 12 * mm, 25 * mm, 12 * mm]
    header = ["Nummer", "Bezeichnung", "Berichtsjahr", "%", "Vorjahr", "%"]

    base_style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]

    def section_table(rows, prev_map, base, prev_base, total_label, total, prev_total, extra_rows=None):
        table_data = [header]
        style = list(base_style)
        for row in rows:
            account = row["account"]
            prev_balance = prev_map.get(account.id)
            table_data.append(
                [
                    account.code,
                    Paragraph(account.name, STYLE_CELL),
                    _chf(row["balance"]),
                    _pct(row["balance"], base),
                    _chf(prev_balance),
                    _pct(prev_balance, prev_base),
                ]
            )
        for extra in extra_rows or []:
            table_data.append(extra)
        table_data.append(
            [
                "",
                total_label,
                _chf(total),
                _pct(total, base),
                _chf(prev_total) if prev_total is not None else "",
                _pct(prev_total, prev_base),
            ]
        )
        style.append(("FONT", (0, len(table_data) - 1), (-1, len(table_data) - 1), "Helvetica-Bold", 8))
        style.append(("LINEABOVE", (0, len(table_data) - 1), (-1, len(table_data) - 1), 0.5, colors.black))
        return Table(table_data, colWidths=col_widths, repeatRows=1, style=TableStyle(style))

    # --- Bilanz
    story.append(Paragraph(f"Bilanz per {fiscal_year.end_date:%d.%m.%Y}", STYLE_TITLE))
    story.append(Spacer(1, 6))

    base = data["total_aktiva"]
    prev_base = prev_bilanz["total_aktiva"] if prev_bilanz else None

    story.append(Paragraph("Aktiven", STYLE_SECTION))
    story.append(
        section_table(
            data["aktiva_rows"], prev_aktiva, base, prev_base,
            "Total Aktiven", data["total_aktiva"],
            prev_bilanz["total_aktiva"] if prev_bilanz else None,
        )
    )

    story.append(Paragraph("Passiven", STYLE_SECTION))
    jahreserfolg_row = [
        "",
        "Jahresergebnis (Gewinn +/Verlust -)",
        _chf(data["jahreserfolg"]),
        _pct(data["jahreserfolg"], base),
        _chf(prev_bilanz["jahreserfolg"]) if prev_bilanz else "",
        _pct(prev_bilanz["jahreserfolg"], prev_base) if prev_bilanz else "",
    ]
    story.append(
        section_table(
            data["passiva_rows"], prev_passiva, base, prev_base,
            "Total Passiven (inkl. Jahresergebnis)", data["total_passiva_mit_erfolg"],
            prev_bilanz["total_passiva_mit_erfolg"] if prev_bilanz else None,
            extra_rows=[jahreserfolg_row],
        )
    )

    # --- Erfolgsrechnung
    story.append(Spacer(1, 14))
    story.append(
        Paragraph(
            f"Erfolgsrechnung {fiscal_year.start_date:%d.%m.%Y} – {fiscal_year.end_date:%d.%m.%Y}",
            STYLE_TITLE,
        )
    )
    story.append(Spacer(1, 6))

    er_base = er["total_ertrag"]
    prev_er_base = prev_er["total_ertrag"] if prev_er else None

    story.append(Paragraph("Ertrag", STYLE_SECTION))
    story.append(
        section_table(
            er["ertrag_rows"], prev_ertrag, er_base, prev_er_base,
            "Total Ertrag", er["total_ertrag"], prev_er["total_ertrag"] if prev_er else None,
        )
    )

    story.append(Paragraph("Aufwand", STYLE_SECTION))
    story.append(
        section_table(
            er["aufwand_rows"], prev_aufwand, er_base, prev_er_base,
            "Total Aufwand", er["total_aufwand"], prev_er["total_aufwand"] if prev_er else None,
        )
    )

    result_data = [
        [
            "",
            "Jahresergebnis (Gewinn +/Verlust -)",
            _chf(er["result"]),
            _pct(er["result"], er_base),
            _chf(prev_er["result"]) if prev_er else "",
            _pct(prev_er["result"], prev_er_base) if prev_er else "",
        ]
    ]
    result_style = TableStyle(
        [
            ("FONT", (0, 0), (-1, -1), "Helvetica-Bold", 8),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("LINEABOVE", (0, 0), (-1, 0), 1, colors.black),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]
    )
    story.append(Spacer(1, 6))
    story.append(Table(result_data, colWidths=col_widths, style=result_style))

    doc.build(story)
    buffer.seek(0)
    return buffer
