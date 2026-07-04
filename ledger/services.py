from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import FiscalYear, JournalEntry, JournalLine

TWO_PLACES = Decimal("0.01")


def _round(amount):
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def find_open_fiscal_year(date):
    return FiscalYear.objects.filter(start_date__lte=date, end_date__gte=date, is_closed=False).first()


@transaction.atomic
def book_bewegung(bewegung, gegenkonto, vat_code, user):
    """Erstellt aus einer Bank-Bewegung eine ausgeglichene doppelte Buchung.

    Ausgang (amount < 0): Gegenkonto (netto) + Vorsteuer im Soll, Bankkonto im Haben.
    Eingang (amount > 0): Bankkonto im Soll, Gegenkonto (netto) + Umsatzsteuer im Haben.
    """
    if bewegung.journal_entry_id:
        raise ValidationError("Diese Bewegung ist bereits verbucht.")

    fiscal_year = find_open_fiscal_year(bewegung.booking_date)
    if fiscal_year is None:
        raise ValidationError(
            "Kein offenes Geschäftsjahr für dieses Datum gefunden. Bitte zuerst ein Geschäftsjahr anlegen."
        )

    bank_account = bewegung.bank_account.ledger_account
    gross = abs(bewegung.amount)

    if vat_code and vat_code.rate_percent:
        if not vat_code.clearing_account_id:
            raise ValidationError(f"MWST-Code {vat_code.code} hat kein Verrechnungskonto hinterlegt.")
        net = _round(gross / (Decimal("1") + vat_code.rate_percent / Decimal("100")))
        vat_amount = gross - net
    else:
        net = gross
        vat_amount = Decimal("0.00")

    entry = JournalEntry.objects.create(
        fiscal_year=fiscal_year,
        date=bewegung.booking_date,
        reference=bewegung.reference or "",
        description=bewegung.description[:255],
        created_by=user,
    )

    is_outgoing = bewegung.amount < 0

    if is_outgoing:
        JournalLine.objects.create(journal_entry=entry, account=gegenkonto, debit_amount=net)
        if vat_amount:
            JournalLine.objects.create(
                journal_entry=entry,
                account=vat_code.clearing_account,
                debit_amount=vat_amount,
                vat_code=vat_code,
            )
        JournalLine.objects.create(journal_entry=entry, account=bank_account, credit_amount=gross)
    else:
        JournalLine.objects.create(journal_entry=entry, account=bank_account, debit_amount=gross)
        JournalLine.objects.create(journal_entry=entry, account=gegenkonto, credit_amount=net)
        if vat_amount:
            JournalLine.objects.create(
                journal_entry=entry,
                account=vat_code.clearing_account,
                credit_amount=vat_amount,
                vat_code=vat_code,
            )

    entry.refresh_from_db()
    if not entry.is_balanced:
        raise ValidationError("Buchung ist nicht ausgeglichen (Soll != Haben).")

    bewegung.journal_entry = entry
    bewegung.assigned_account = gegenkonto
    bewegung.vat_code = vat_code
    bewegung.status = bewegung.Status.BOOKED
    bewegung.save(update_fields=["journal_entry", "assigned_account", "vat_code", "status"])

    return entry
