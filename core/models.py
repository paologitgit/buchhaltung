from django.db import models


class CompanySettings(models.Model):
    """Singleton (immer pk=1) mit firmenweiten Einstellungen."""

    mwst_pflichtig = models.BooleanField(
        default=True,
        verbose_name="MWST-pflichtig",
        help_text="Wenn deaktiviert, wird die MWST-Auswahl beim Verbuchen ausgeblendet.",
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
