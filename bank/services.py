import csv
import hashlib
import io
import re
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Bewegung, ImportBatch

_WHITESPACE_RE = re.compile(r"\s+")


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
    # Betrag und Text werden normalisiert (feste Nachkommastellen, zusammen-
    # gefasste Leerzeichen), damit kleine Formatierungsunterschiede zwischen
    # zwei CSV-Exporten (z.B. "-15" statt "-15.00") nicht zu Dubletten führen.
    normalized_amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    normalized_description = _WHITESPACE_RE.sub(" ", description.strip()).lower()
    payload = f"{bank_account_id}|{booking_date.isoformat()}|{normalized_amount}|{normalized_description}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _decode_csv_bytes(raw):
    """Viele Schweizer Bank-Exporte sind Windows-1252 (nicht UTF-8) kodiert."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def _find_header_line(lines, delimiter, required_column):
    """Bank-Exporte enthalten oft Kopfzeilen (Kontonummer, Saldo, Adresse ...)
    vor der eigentlichen Tabelle. Wir suchen die Zeile, die die konfigurierte
    Datumsspalte tatsächlich als Spaltennamen enthält."""
    for i, line in enumerate(lines):
        fields = [f.strip().strip('"') for f in line.split(delimiter)]
        if required_column in fields:
            return i
    return None


@transaction.atomic
def import_csv(bank_account, uploaded_file, user):
    raw = uploaded_file.read()
    text = _decode_csv_bytes(raw)

    lines = text.splitlines()
    header_index = _find_header_line(lines, bank_account.csv_delimiter, bank_account.csv_date_column)
    if header_index is None:
        raise ValidationError(
            f"Spalte '{bank_account.csv_date_column}' wurde in der CSV-Datei nicht gefunden. "
            "Bitte Spalten-Zuordnung und Trennzeichen des Bankkontos prüfen."
        )
    csv_text = "\n".join(lines[header_index:])
    reader = csv.DictReader(io.StringIO(csv_text), delimiter=bank_account.csv_delimiter)

    batch = ImportBatch.objects.create(
        bank_account=bank_account,
        filename=uploaded_file.name,
        imported_by=user,
    )

    row_count = 0
    created_count = 0
    duplicate_count = 0

    for row in reader:
        if not any((value or "").strip() for value in row.values()):
            continue  # leere Zeile (z.B. am Dateiende) uebergehen, nicht als Bewegung zaehlen

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
