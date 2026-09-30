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
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from core.models import CompanySettings

from .grouped_reports import gewinnverwendung, grouped_bilanz, grouped_erfolgsrechnung, jahresrechnung_anhang
from .models import Account, AccountGroup, FiscalYear, JournalLine
from .reports import BILANZ_TYPES, _account_sums, _signed_balance, kontoblatt

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
    beleg_by_number = {}
    entry_beleg_links = {}

    def _links_for(entry_id):
        if entry_id in entry_beleg_links:
            return entry_beleg_links[entry_id]
        numbers = set()
        for beleg in belege_by_entry.get(entry_id, []):
            key = _beleg_group_key(beleg)
            if key not in number_by_group:
                number = len(numbered_belege) + 1
                number_by_group[key] = number
                beleg_by_number[number] = beleg
                numbered_belege.append(beleg)
            numbers.add(number_by_group[key])
        links = [(n, beleg_by_number[n]) for n in sorted(numbers)]
        entry_beleg_links[entry_id] = links
        return links

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
            row["beleg_links"] = _links_for(line.journal_entry_id)

    return sections, numbered_belege


STYLE_LINK_CELL = ParagraphStyle(
    "link_cell", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.Color(0.1, 0.2, 0.6)
)


def kontoblaetter_pdf(fiscal_year, base_url):
    """Kontoblätter aller bebuchten Konten als PDF. Belege werden nicht
    eingebettet, sondern in der Beleg-Spalte als Link auf die Beleg-Ansicht
    in der App gesetzt (base_url z.B. 'https://buchhaltung.example.com',
    ohne Schrägstrich am Ende)."""
    sections, _numbered_belege = _collect_kontoblatt_data(fiscal_year)

    buffer = io.BytesIO()
    doc = _build_doc(buffer)
    story = []

    name = _company_name()
    if name:
        story.append(Paragraph(name, STYLE_SUBTITLE))
    story.append(Paragraph("Kontoblätter", STYLE_TITLE))
    story.append(
        Paragraph(
            f"Geschäftsjahr {fiscal_year.start_date:%d.%m.%Y} – {fiscal_year.end_date:%d.%m.%Y}, Währung CHF. "
            "Die Beleg-Nummern sind anklickbare Links zur jeweiligen Beleg-Ansicht in der App.",
            STYLE_SUBTITLE,
        )
    )
    story.append(Spacer(1, 6))

    col_widths = [22 * mm, 60 * mm, 20 * mm, 17 * mm, 20 * mm, 20 * mm, 21 * mm]
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
            beleg_cell = ""
            if row["beleg_links"]:
                url = base_url.rstrip("/")
                links = [
                    f'<a href="{url}/belege/{beleg.pk}/">{number}</a>' for number, beleg in row["beleg_links"]
                ]
                beleg_cell = Paragraph(", ".join(links), STYLE_LINK_CELL)
            data.append(
                [
                    line.journal_entry.date.strftime("%d.%m.%Y"),
                    Paragraph(line.journal_entry.description, STYLE_CELL),
                    row["gegenkonto"],
                    beleg_cell,
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
    return buffer


# ---------------------------------------------------------------------------
# Bilanz + Erfolgsrechnung mit Vorjahresvergleich


def _previous_fiscal_year(fiscal_year):
    return (
        FiscalYear.objects.filter(end_date__lt=fiscal_year.start_date).order_by("-end_date").first()
    )


def _grouped_rows_table(rows, base, prev_base, is_passiv=False):
    """Rendert eine Zeilenliste aus grouped_reports (code/label/value/
    prev_value/depth/bold) als Tabelle mit Nummer-, Betrags- und %-Spalten.
    Auf der Passivseite (Saldobilanz-Stil) wird jedem Betrag ein 'H'
    angehängt (Haben-Seite), wie in der Treuhand-Vorlage üblich."""

    def fmt(value):
        text = _chf(value)
        if is_passiv and value is not None and text:
            text += "  H"
        return text

    col_widths = [18 * mm, 82 * mm, 25 * mm, 12 * mm, 25 * mm, 12 * mm]
    header = ["Nummer", "Bezeichnung", "Berichtsjahr", "%", "Vorjahr", "%"]
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    data = [header]
    for row in rows:
        indent = "&nbsp;&nbsp;&nbsp;&nbsp;" * row["depth"]
        data.append(
            [
                row.get("code", "") or "",
                Paragraph(indent + row["label"], STYLE_CELL),
                fmt(row["value"]),
                _pct(row["value"], base) if row["value"] is not None else "",
                fmt(row["prev_value"]),
                _pct(row["prev_value"], prev_base) if row["prev_value"] is not None else "",
            ]
        )
        if row["bold"]:
            i = len(data) - 1
            style.append(("FONT", (0, i), (-1, i), "Helvetica-Bold", 8))
    return Table(data, colWidths=col_widths, repeatRows=1, style=TableStyle(style))


def saldobilanz_pdf(fiscal_year):
    """Bilanz + Erfolgsrechnung im Stil der nummerierten Treuhand-
    Saldobilanz: Kontengruppen mit Zwischentotalen (10/100/110/... bzw.
    3/30/40/...), 'H'-Markierung auf der Passivseite, Vorjahresvergleich."""
    prev_fy = _previous_fiscal_year(fiscal_year)
    b = grouped_bilanz(fiscal_year, AccountGroup.Tree.SALDOBILANZ, prev_fy)
    er = grouped_erfolgsrechnung(fiscal_year, AccountGroup.Tree.SALDOBILANZ, prev_fy)

    buffer = io.BytesIO()
    doc = _build_doc(buffer)
    story = []

    name = _company_name()
    if name:
        story.append(Paragraph(name, STYLE_SUBTITLE))

    aktiva_rows = b["aktiva_rows"] + [
        {
            "code": "",
            "label": "Total Aktiven",
            "value": b["total_aktiva"],
            "prev_value": b["prev_total_aktiva"],
            "depth": 0,
            "bold": True,
        }
    ]
    passiva_rows = b["passiva_rows"] + [
        {
            "code": "",
            "label": "Total Passiven",
            "value": b["total_passiva"],
            "prev_value": b["prev_total_passiva"],
            "depth": 0,
            "bold": True,
        }
    ]

    story.append(Paragraph(f"Bilanz per {fiscal_year.end_date:%d.%m.%Y}", STYLE_TITLE))
    story.append(Spacer(1, 6))
    story.append(Paragraph("AKTIVEN", STYLE_SECTION))
    story.append(_grouped_rows_table(aktiva_rows, b["total_aktiva"], b["prev_total_aktiva"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("PASSIVEN", STYLE_SECTION))
    story.append(
        _grouped_rows_table(passiva_rows, b["total_aktiva"], b["prev_total_aktiva"], is_passiv=True)
    )
    if not b["balanced"]:
        story.append(Spacer(1, 4))
        story.append(
            Paragraph(
                f"Achtung: Bilanz ist nicht ausgeglichen. Total Aktiven {_chf(b['total_aktiva'])} "
                f"≠ Total Passiven {_chf(b['total_passiva'])}.",
                STYLE_SUBTITLE,
            )
        )

    story.append(Spacer(1, 14))
    story.append(
        Paragraph(
            f"Erfolgsrechnung {fiscal_year.start_date:%d.%m.%Y} – {fiscal_year.end_date:%d.%m.%Y}",
            STYLE_TITLE,
        )
    )
    story.append(Spacer(1, 6))
    story.append(_grouped_rows_table(er["rows"], er["ertrag_base"], er["prev_ertrag_base"]))

    doc.build(story)
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------------
# Vollständige Jahresrechnung: Titelseite, Inhaltsverzeichnis, Bilanz/ER
# (sprachlich gruppiert, EBITDA/EBIT/EBT-Kaskade), Anhang, Antrag


STYLE_TOC_TITLE = ParagraphStyle("toc_title", fontName="Helvetica-Bold", fontSize=14, leading=18, spaceAfter=16)
STYLE_TOC_ENTRY = ParagraphStyle("toc_entry", fontName="Helvetica", fontSize=11, leading=20)
STYLE_COVER_COMPANY = ParagraphStyle(
    "cover_company", fontName="Helvetica-Bold", fontSize=18, leading=22, alignment=1, spaceAfter=6
)
STYLE_COVER_TITLE = ParagraphStyle("cover_title", fontName="Helvetica", fontSize=16, leading=20, alignment=1)
STYLE_COVER_YEAR = ParagraphStyle("cover_year", fontName="Helvetica-Bold", fontSize=22, leading=26, alignment=1)
STYLE_COVER_SMALL = ParagraphStyle("cover_small", fontName="Helvetica", fontSize=9, leading=13, alignment=1)
STYLE_ANHANG_TITLE = ParagraphStyle(
    "anhang_title", fontName="Helvetica-Bold", fontSize=10, leading=13, spaceBefore=10, spaceAfter=3
)


def _treuhand_line():
    settings_obj = CompanySettings.load()
    parts = [p for p in [settings_obj.treuhand_name, settings_obj.treuhand_adresse] if p]
    line = " | ".join(parts)
    extra = [p for p in [settings_obj.treuhand_telefon, settings_obj.treuhand_website] if p]
    if extra:
        line = (line + " | " + " | ".join(extra)) if line else " | ".join(extra)
    return line


def _jahresrechnung_cover(fiscal_year):
    settings_obj = CompanySettings.load()
    story = [Spacer(1, 60 * mm)]
    if settings_obj.firmenname:
        story.append(Paragraph(settings_obj.firmenname, STYLE_COVER_COMPANY))
    story.append(Paragraph("Jahresrechnung", STYLE_COVER_TITLE))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(str(fiscal_year.start_date.year), STYLE_COVER_YEAR))
    story.append(Spacer(1, 60 * mm))
    treuhand = _treuhand_line()
    if treuhand:
        story.append(Paragraph(treuhand, STYLE_COVER_SMALL))
    if settings_obj.firmenname or settings_obj.firmenadresse:
        story.append(Spacer(1, 4))
        addr = "<br/>".join([p for p in [settings_obj.firmenname, settings_obj.firmenadresse] if p])
        story.append(Paragraph(addr, STYLE_COVER_SMALL))
    story.append(PageBreak())
    return story


def _jahresrechnung_toc(fiscal_year):
    story = [Paragraph("Inhaltsverzeichnis", STYLE_TOC_TITLE)]
    entries = [
        f"Bilanz per {fiscal_year.end_date:%d.%m.%Y} mit Vorjahr",
        f"Erfolgsrechnung {fiscal_year.start_date:%d.%m.%Y} – {fiscal_year.end_date:%d.%m.%Y} mit Vorjahr",
        f"Anhang der Jahresrechnung {fiscal_year.start_date.year} mit Vorjahr",
        f"Antrag über die Verwendung des Bilanzgewinnes {fiscal_year.start_date.year}",
    ]
    for entry in entries:
        story.append(Paragraph(entry, STYLE_TOC_ENTRY))
    story.append(PageBreak())
    return story


def _jahresrechnung_table(rows, base, prev_base):
    col_widths = [95 * mm, 27 * mm, 13 * mm, 27 * mm, 13 * mm]
    header = ["Bezeichnung", "Berichtsjahr", "%", "Vorjahr", "%"]
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    data = [header]
    for row in rows:
        indent = "&nbsp;&nbsp;&nbsp;&nbsp;" * row["depth"]
        data.append(
            [
                Paragraph(indent + row["label"], STYLE_CELL),
                _chf(row["value"]),
                _pct(row["value"], base) if row["value"] is not None else "",
                _chf(row["prev_value"]),
                _pct(row["prev_value"], prev_base) if row["prev_value"] is not None else "",
            ]
        )
        if row["bold"]:
            i = len(data) - 1
            style.append(("FONT", (0, i), (-1, i), "Helvetica-Bold", 8))
    return Table(data, colWidths=col_widths, repeatRows=1, style=TableStyle(style))


def _jahresrechnung_bilanz_section(fiscal_year, prev_fy):
    b = grouped_bilanz(fiscal_year, AccountGroup.Tree.JAHRESRECHNUNG, prev_fy)
    aktiva_rows = b["aktiva_rows"] + [
        {"label": "Total Aktiven", "value": b["total_aktiva"], "prev_value": b["prev_total_aktiva"], "depth": 0, "bold": True}
    ]
    passiva_rows = b["passiva_rows"] + [
        {"label": "Total Passiven", "value": b["total_passiva"], "prev_value": b["prev_total_passiva"], "depth": 0, "bold": True}
    ]
    story = [Paragraph(f"Bilanz per {fiscal_year.end_date:%d.%m.%Y}", STYLE_TITLE), Spacer(1, 6)]
    story.append(Paragraph("Aktiven", STYLE_SECTION))
    story.append(_jahresrechnung_table(aktiva_rows, b["total_aktiva"], b["prev_total_aktiva"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Passiven", STYLE_SECTION))
    story.append(_jahresrechnung_table(passiva_rows, b["total_aktiva"], b["prev_total_aktiva"]))
    if not b["balanced"]:
        story.append(Spacer(1, 4))
        story.append(
            Paragraph(
                f"Achtung: Bilanz ist nicht ausgeglichen. Total Aktiven {_chf(b['total_aktiva'])} "
                f"≠ Total Passiven {_chf(b['total_passiva'])}.",
                STYLE_SUBTITLE,
            )
        )
    story.append(PageBreak())
    return story, b


def _jahresrechnung_er_section(fiscal_year, prev_fy):
    er = grouped_erfolgsrechnung(fiscal_year, AccountGroup.Tree.JAHRESRECHNUNG, prev_fy)
    story = [
        Paragraph(
            f"Erfolgsrechnung {fiscal_year.start_date:%d.%m.%Y} – {fiscal_year.end_date:%d.%m.%Y}", STYLE_TITLE
        ),
        Spacer(1, 6),
        _jahresrechnung_table(er["rows"], er["ertrag_base"], er["prev_ertrag_base"]),
        PageBreak(),
    ]
    return story, er


def _jahresrechnung_anhang_section(fiscal_year, prev_fy):
    notes = jahresrechnung_anhang(fiscal_year, prev_fy)
    story = [
        Paragraph(f"Anhang der Jahresrechnung {fiscal_year.start_date.year}", STYLE_TITLE),
        Spacer(1, 4),
        Paragraph(
            "1  Angaben über die in der Jahresrechnung angewandten Grundsätze", STYLE_ANHANG_TITLE
        ),
        Paragraph(
            "Die vorliegende Jahresrechnung wurde gemäss den Vorschriften des Schweizerischen Gesetzes, "
            "insbesondere der Artikel über die kaufmännische Buchführung und Rechnungslegung des "
            "Obligationenrechts (Art. 957 bis 962) erstellt.",
            STYLE_CELL,
        ),
    ]
    if notes:
        story.append(
            Paragraph("2  Angaben und Erläuterungen zu Positionen der Bilanz und Erfolgsrechnung", STYLE_ANHANG_TITLE)
        )
        for note in notes:
            story.append(Paragraph(note["title"], STYLE_ANHANG_TITLE))
            col_widths = [95 * mm, 27 * mm, 27 * mm]
            data = [["", "Berichtsjahr", "Vorjahr"]]
            style = [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
            for row in note["rows"]:
                data.append([row["label"], _chf(row["value"]), _chf(row["prev_value"])])
            data.append(["Total", _chf(note["total"]), _chf(note["prev_total"])])
            style.append(("FONT", (0, len(data) - 1), (-1, len(data) - 1), "Helvetica-Bold", 8))
            style.append(("LINEABOVE", (0, len(data) - 1), (-1, len(data) - 1), 0.5, colors.black))
            story.append(Table(data, colWidths=col_widths, style=TableStyle(style)))
            story.append(Spacer(1, 6))
    story.append(PageBreak())
    return story


def _jahresrechnung_antrag_section(fiscal_year):
    gw = gewinnverwendung(fiscal_year)
    year = fiscal_year.start_date.year
    story = [
        Paragraph(f"Antrag über die Verwendung des Bilanzgewinnes {year}", STYLE_TITLE),
        Spacer(1, 6),
    ]
    col_widths = [110 * mm, 34 * mm]
    style = TableStyle(
        [
            ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
    )
    data1 = [
        ["Gewinnvortrag", _chf(gw["gewinnvortrag"])],
        ["Jahresverlust/-gewinn", _chf(gw["jahresergebnis"])],
        ["Total zur Verfügung der Gesellschafterversammlung", _chf(gw["total"])],
    ]
    story.append(Table(data1, colWidths=col_widths, style=style))
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "Die Geschäftsführung beantragt der Gesellschafterversammlung folgende Gewinnverwendung:",
            STYLE_CELL,
        )
    )
    story.append(Spacer(1, 6))
    data2 = [
        ["Zuweisung an die gesetzliche Gewinnreserve", _chf(gw["zuweisung"])],
        ["Vortrag auf neue Rechnung", _chf(gw["vortrag"])],
    ]
    story.append(Table(data2, colWidths=col_widths, style=style))
    return story


def jahresrechnung_pdf(fiscal_year):
    """Vollständige Jahresrechnung: Titelseite, Inhaltsverzeichnis, Bilanz
    und Erfolgsrechnung (sprachlich gruppiert, EBITDA/EBIT/EBT-Kaskade),
    Anhang (automatische Aufschlüsselung von Gruppen mit mehreren Konten)
    und Antrag über die Verwendung des Bilanzgewinnes."""
    prev_fy = _previous_fiscal_year(fiscal_year)

    buffer = io.BytesIO()
    doc = _build_doc(buffer)
    story = []
    story += _jahresrechnung_cover(fiscal_year)
    story += _jahresrechnung_toc(fiscal_year)
    bilanz_story, _ = _jahresrechnung_bilanz_section(fiscal_year, prev_fy)
    story += bilanz_story
    er_story, _ = _jahresrechnung_er_section(fiscal_year, prev_fy)
    story += er_story
    story += _jahresrechnung_anhang_section(fiscal_year, prev_fy)
    story += _jahresrechnung_antrag_section(fiscal_year)

    doc.build(story)
    buffer.seek(0)
    return buffer

