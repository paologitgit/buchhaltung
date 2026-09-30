from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AccountType(models.TextChoices):
    AKTIVA = "AKTIVA", "Aktiven"
    PASSIVA = "PASSIVA", "Passiven"
    AUFWAND = "AUFWAND", "Aufwand"
    ERTRAG = "ERTRAG", "Ertrag"


class AccountGroup(models.Model):
    """Gruppierungsknoten für Bilanz/Erfolgsrechnung-Berichte. Es gibt zwei
    unabhängige Bäume (tree): die nummerierte Saldobilanz-Gliederung (z.B.
    "10 Umlaufvermögen" > "100 Flüssige Mittel") und die sprachliche
    Jahresrechnung-Gliederung (z.B. "Flüssige Mittel"). Ein Konto kann in
    beiden Bäumen je einer Gruppe zugewiesen werden (siehe Account)."""

    class Tree(models.TextChoices):
        SALDOBILANZ = "SALDOBILANZ", "Saldobilanz (nummeriert)"
        JAHRESRECHNUNG = "JAHRESRECHNUNG", "Jahresrechnung (sprachlich)"

    tree = models.CharField(max_length=20, choices=Tree.choices)
    code = models.CharField(
        max_length=30,
        help_text='Eindeutiger Code innerhalb des Baums, z.B. "100" (Saldobilanz) oder "FLUESSIGE_MITTEL" (Jahresrechnung).',
    )
    name = models.CharField(max_length=200)
    account_type = models.CharField(
        max_length=10,
        choices=AccountType.choices,
        blank=True,
        help_text="Nur für Wurzelgruppen relevant (Aktiven/Passiven bzw. Aufwand/Ertrag).",
    )
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["tree", "order", "code"]
        constraints = [models.UniqueConstraint(fields=["tree", "code"], name="uniq_accountgroup_tree_code")]
        verbose_name = "Kontengruppe"
        verbose_name_plural = "Kontengruppen"

    def __str__(self):
        return f"{self.code} {self.name}" if self.code and not self.code.isupper() else self.name


class Account(models.Model):
    Type = AccountType

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=200)
    account_type = models.CharField(max_length=10, choices=Type.choices)
    is_active = models.BooleanField(default=True)
    is_bank_account = models.BooleanField(
        default=False,
        help_text="Konto wird per CSV-Import bebucht (Gegenkonto Bankbewegungen).",
    )
    saldobilanz_gruppe = models.ForeignKey(
        AccountGroup,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="saldobilanz_accounts",
        limit_choices_to={"tree": AccountGroup.Tree.SALDOBILANZ},
        verbose_name="Gruppe (nummerierte Saldobilanz)",
        help_text="Für die gruppierte Bilanz/Erfolgsrechnung-PDF (Zwischentotale).",
    )
    jahresrechnung_gruppe = models.ForeignKey(
        AccountGroup,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="jahresrechnung_accounts",
        limit_choices_to={"tree": AccountGroup.Tree.JAHRESRECHNUNG},
        verbose_name="Gruppe (Jahresrechnung)",
        help_text="Für die vollständige Jahresrechnung-PDF (Titelseite, Anhang, Antrag).",
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
    gewinnruecklage_zuweisung = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Zuweisung an gesetzliche Gewinnreserve",
        help_text=(
            "Für den Antrag über die Verwendung des Bilanzgewinnes: Betrag, der der gesetzlichen "
            "Gewinnreserve zugewiesen wird. Der Rest von Gewinnvortrag + Jahresergebnis gilt als "
            "Vortrag auf neue Rechnung. Leer/0 = alles wird vorgetragen."
        ),
    )

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
