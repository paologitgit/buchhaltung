import csv
import os
import re
import zipfile
from io import BytesIO, StringIO

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from openpyxl import Workbook

from .models import JournalEntry

EXPORT_HEADER = ["Datum", "Beleg-Nr", "Text", "Konto", "Kontobezeichnung", "Soll", "Haben", "MWST-Code"]


def _entries_for_export(fiscal_year_id=None):
    qs = (
        JournalEntry.objects.select_related("fiscal_year")
        .prefetch_related("lines__account", "lines__vat_code")
        .order_by("date", "id")
    )
    if fiscal_year_id:
        qs = qs.filter(fiscal_year_id=fiscal_year_id)
    return qs


def export_journal_csv(fiscal_year_id=None):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="journal.csv"'
    writer = csv.writer(response, delimiter=";")
    writer.writerow(EXPORT_HEADER)
    for entry in _entries_for_export(fiscal_year_id):
        for line in entry.lines.all():
            writer.writerow(
                [
                    entry.date.isoformat(),
                    entry.reference,
                    entry.description,
                    line.account.code,
                    line.account.name,
                    line.debit_amount or "",
                    line.credit_amount or "",
                    line.vat_code.code if line.vat_code else "",
                ]
            )
    return response


def export_journal_xlsx(fiscal_year_id=None):
    wb = Workbook()
    ws = wb.active
    ws.title = "Journal"
    ws.append(EXPORT_HEADER)
    for entry in _entries_for_export(fiscal_year_id):
        for line in entry.lines.all():
            ws.append(
                [
                    entry.date.isoformat(),
                    entry.reference,
                    entry.description,
                    line.account.code,
                    line.account.name,
                    float(line.debit_amount) if line.debit_amount else None,
                    float(line.credit_amount) if line.credit_amount else None,
                    line.vat_code.code if line.vat_code else "",
                ]
            )
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="journal.xlsx"'
    return response


def _safe_filename_part(text, max_length=50):
    text = re.sub(r"[^\w\-. ]", "_", text).strip()
    return text[:max_length] or "beleg"


def export_journal_zip(fiscal_year_id=None):
    """Journal (CSV) plus alle Belege der verbuchten Bewegungen im gewählten
    Zeitraum, gebündelt als ZIP – für die Übergabe an die Treuhänderin."""
    entries = _entries_for_export(fiscal_year_id)

    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer, delimiter=";")
    writer.writerow(EXPORT_HEADER)
    for entry in entries:
        for line in entry.lines.all():
            writer.writerow(
                [
                    entry.date.isoformat(),
                    entry.reference,
                    entry.description,
                    line.account.code,
                    line.account.name,
                    line.debit_amount or "",
                    line.credit_amount or "",
                    line.vat_code.code if line.vat_code else "",
                ]
            )

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("journal.csv", csv_buffer.getvalue())

        for entry in entries:
            try:
                bewegung = entry.bewegung
            except ObjectDoesNotExist:
                continue
            if bewegung is None:
                continue
            for beleg in bewegung.belege.all():
                if not beleg.file or not os.path.exists(beleg.file.path):
                    continue
                ext = os.path.splitext(beleg.original_filename)[1]
                desc = _safe_filename_part(entry.description)
                arcname = f"belege/{entry.date.isoformat()}_{desc}_{beleg.document_type}_{beleg.pk}{ext}"
                zf.write(beleg.file.path, arcname=arcname)

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.read(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="journal_mit_belegen.zip"'
    return response
