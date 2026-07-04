import csv
from io import BytesIO

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
