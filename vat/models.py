from decimal import Decimal

from django.db import models


class VatCode(models.Model):
    class Direction(models.TextChoices):
        INPUT = "INPUT", "Vorsteuer (auf Aufwand)"
        OUTPUT = "OUTPUT", "Umsatzsteuer (auf Ertrag)"
        NONE = "NONE", "Keine MWST"

    code = models.CharField(max_length=20, unique=True)
    label = models.CharField(max_length=100)
    rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    direction = models.CharField(max_length=10, choices=Direction.choices, default=Direction.NONE)
    clearing_account = models.ForeignKey(
        "ledger.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vat_codes",
        help_text="Konto für die MWST-Verbuchung (z.B. Vorsteuer oder Geschuldete MWST).",
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "MWST-Code"
        verbose_name_plural = "MWST-Codes"

    def __str__(self):
        return f"{self.code} ({self.rate_percent}%)"
