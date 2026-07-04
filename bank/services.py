import csv
import hashlib
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Bewegung, ImportBatch


def _parse_amount(raw):
    raw = raw.strip().replace("'", "").replace(" ", "")
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ValidationError(f"Ungültiger Betrag in CSV: '{raw}'") from exc


def _compute_hash(bank_account_id, booking_date, amount, description):
    payload = f"{bank_account_id}|{booking_date.isoformat()}|{amount}|{description.strip().lower()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@transaction.atomic
def import_csv(bank_account, uploaded_file, user):
    raw = uploaded_file.read()
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter=bank_account.csv_delimiter)

    batch = ImportBatch.objects.create(
        bank_account=bank_account,
        filename=uploaded_file.name,
        imported_by=user,
    )

    row_count = 0
    created_count = 0
    duplicate_count = 0

    for row in reader:
        row_count += 1
        try:
            date_raw = row[bank_account.csv_date_column].strip()
            amount_raw = row[bank_account.csv_amount_column]
        except KeyError as exc:
            raise ValidationError(
                f"Spalte {exc} nicht in CSV gefunden. Bitte Spalten-Zuordnung des Bankkontos prüfen."
            ) from exc
        description = row.get(bank_account.csv_description_column, "").strip()

        try:
            booking_date = datetime.strptime(date_raw, bank_account.csv_date_format).date()
        except ValueError as exc:
            raise ValidationError(f"Ungültiges Datum in CSV: '{date_raw}'") from exc

        amount = _parse_amount(amount_raw)
        dedup_hash = _compute_hash(bank_account.id, booking_date, amount, description)

        _, created = Bewegung.objects.get_or_create(
            dedup_hash=dedup_hash,
            defaults=dict(
                bank_account=bank_account,
                import_batch=batch,
                booking_date=booking_date,
                amount=amount,
                currency=bank_account.currency,
                description=description,
                source=Bewegung.Source.CSV,
            ),
        )
        if created:
            created_count += 1
        else:
            duplicate_count += 1

    batch.row_count = row_count
    batch.created_count = created_count
    batch.duplicate_count = duplicate_count
    batch.save(update_fields=["row_count", "created_count", "duplicate_count"])
    return batch
