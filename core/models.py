from django.db import models


class CompanySettings(models.Model):
    """Singleton (immer pk=1) mit firmenweiten Einstellungen."""

    firmenname = models.CharField(
        max_length=120,
        blank=True,
        default="",
        db_default="",
        verbose_name="Firmenname",
        help_text='Erscheint im Kopf der PDF-Berichte, z.B. "Muster GmbH, Chur".',
    )
    mwst_pflichtig = models.BooleanField(
        default=True,
        verbose_name="MWST-pflichtig",
        help_text="Wenn deaktiviert, wird die MWST-Auswahl beim Verbuchen ausgeblendet.",
    )
    privatkonto = models.ForeignKey(
        "ledger.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Privatkonto",
        help_text=(
            "Gegenkonto für Bewegungen, die als privat markiert werden (z.B. private Käufe über die "
            "geschäftliche Zahlungsmethode). Wird ohne MWST verbucht und fliesst nicht in "
            "Erfolgsrechnung/Auswertung ein. Leer = Konto mit Nummer 2850 wird automatisch verwendet."
        ),
    )

    class Meta:
        verbose_name = "Firmeneinstellung"
        verbose_name_plural = "Firmeneinstellungen"

    def __str__(self):
        return "Firmeneinstellungen"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
