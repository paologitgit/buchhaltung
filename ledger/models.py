from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Account(models.Model):
    class Type(models.TextChoices):
        AKTIVA = "AKTIVA", "Aktiven"
        PASSIVA = "PASSIVA", "Passiven"
        AUFWAND = "AUFWAND", "Aufwand"
        ERTRAG = "ERTRAG", "Ertrag"

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=200)
    account_type = models.CharField(max_length=10, choices=Type.choices)
    is_active = models.BooleanField(default=True)
    is_bank_account = models.BooleanField(
        default=False,
        help_text="Konto wird per CSV-Import bebucht (Gegenkonto Bankbewegungen).",
    )

    class Meta:
        ordering = ["code"]
        verbose_name = "Konto"
        verbose_name_plural = "Kontenplan"

    def __str__(self):
        return f"{self.code} – {self.name}"


class FiscalYear(models.Model):
    start_date = models.DateField()
    end_date = models.DateField()
    is_closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Geschäftsjahr"
        verbose_name_plural = "Geschäftsjahre"

    def __str__(self):
        return f"{self.start_date:%d.%m.%Y} – {self.end_date:%d.%m.%Y}"

    def clean(self):
        if self.end_date <= self.start_date:
            raise ValidationError("Enddatum muss nach dem Startdatum liegen.")

    def contains(self, date):
        return self.start_date <= date <= self.end_date

    def close(self):
        from django.utils import timezone

        self.entries.update(is_locked=True)
        self.is_closed = True
        self.closed_at = timezone.now()
        self.save(update_fields=["is_closed", "closed_at"])


class JournalEntry(models.Model):
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, related_name="entries")
    date = models.DateField()
    reference = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="journal_entries"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_locked = models.BooleanField(
        default=False,
        help_text="Gesperrt (Geschäftsjahr abgeschlossen) – keine Änderung mehr möglich.",
    )

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Buchung"
        verbose_name_plural = "Buchungen"

    def __str__(self):
        return f"{self.date} – {self.description}"

    @property
    def total_debit(self):
        return sum((line.debit_amount for line in self.lines.all()), Decimal("0.00"))

    @property
    def total_credit(self):
        return sum((line.credit_amount for line in self.lines.all()), Decimal("0.00"))

    @property
    def is_balanced(self):
        return self.total_debit == self.total_credit


class JournalLine(models.Model):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="journal_lines")
    debit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    vat_code = models.ForeignKey(
        "vat.VatCode", on_delete=models.PROTECT, null=True, blank=True, related_name="journal_lines"
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "Buchungszeile"
        verbose_name_plural = "Buchungszeilen"
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(debit_amount__gt=0, credit_amount=0)
                    | models.Q(debit_amount=0, credit_amount__gt=0)
                ),
                name="journalline_debit_xor_credit",
            ),
        ]

    def __str__(self):
        side = "Soll" if self.debit_amount else "Haben"
        amount = self.debit_amount or self.credit_amount
        return f"{self.account.code} {side} {amount}"
