from django.conf import settings
from django.db import models


class BankAccount(models.Model):
    name = models.CharField(max_length=100, verbose_name="Name")
    iban = models.CharField(max_length=34, blank=True, verbose_name="IBAN")
    currency = models.CharField(max_length=3, default="CHF", verbose_name="Währung")
    ledger_account = models.OneToOneField(
        "ledger.Account",
        on_delete=models.PROTECT,
        related_name="bank_account",
        verbose_name="Buchhaltungskonto",
        help_text="Das Konto aus dem Kontenplan, das dieses Bankkonto darstellt (z.B. 1020 – Bank).",
    )

    # Spalten-Zuordnung für den CSV-Import, damit spätere Uploads ohne erneute
    # Konfiguration funktionieren. Wird einmalig pro Bank/Format eingerichtet.
    csv_delimiter = models.CharField(max_length=5, default=",", verbose_name="CSV-Trennzeichen")
    csv_date_column = models.CharField(
        max_length=50, default="Datum", verbose_name="CSV-Spalte Datum"
    )
    csv_amount_column = models.CharField(
        max_length=50, default="Betrag", verbose_name="CSV-Spalte Betrag"
    )
    csv_description_column = models.CharField(
        max_length=50, default="Beschreibung", verbose_name="CSV-Spalte Beschreibung"
    )
    csv_date_format = models.CharField(
        max_length=20, default="%d.%m.%Y", verbose_name="CSV-Datumsformat"
    )

    is_active = models.BooleanField(default=True, verbose_name="Aktiv")

    class Meta:
        ordering = ["name"]
        verbose_name = "Bankkonto"
        verbose_name_plural = "Bankkonten"

    def __str__(self):
        return self.name


class ImportBatch(models.Model):
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name="import_batches")
    filename = models.CharField(max_length=255)
    imported_at = models.DateTimeField(auto_now_add=True)
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    row_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    duplicate_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-imported_at"]
        verbose_name = "CSV-Import"
        verbose_name_plural = "CSV-Importe"

    def __str__(self):
        return f"{self.filename} ({self.imported_at:%d.%m.%Y %H:%M})"


class Bewegung(models.Model):
    class Status(models.TextChoices):
        OFFEN = "OFFEN", "Offen"
        BOOKED = "BOOKED", "Verbucht"
        IGNORED = "IGNORED", "Ignoriert"

    class Source(models.TextChoices):
        CSV = "CSV", "CSV-Import"
        API = "API", "Bank-Schnittstelle"
        MANUAL = "MANUAL", "Manuell"

    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name="bewegungen")
    import_batch = models.ForeignKey(
        ImportBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="bewegungen"
    )
    booking_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="CHF")
    description = models.CharField(max_length=500)
    reference = models.CharField(max_length=100, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.CSV)
    dedup_hash = models.CharField(max_length=64, unique=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OFFEN)
    quittung_erforderlich = models.BooleanField(
        default=True,
        verbose_name="Quittung erforderlich",
        help_text="Abschalten, wenn für diese Bewegung keine Quittung nötig/verfügbar ist (z.B. Bankgebühren).",
    )
    assigned_account = models.ForeignKey(
        "ledger.Account", on_delete=models.PROTECT, null=True, blank=True, related_name="bewegungen"
    )
    vat_code = models.ForeignKey(
        "vat.VatCode", on_delete=models.PROTECT, null=True, blank=True, related_name="bewegungen"
    )
    journal_entry = models.OneToOneField(
        "ledger.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True, related_name="bewegung"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-booking_date", "-id"]
        verbose_name = "Bewegung"
        verbose_name_plural = "Bewegungen"

    def __str__(self):
        return f"{self.booking_date} {self.amount} {self.description[:40]}"
