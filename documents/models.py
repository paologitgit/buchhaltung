from django.conf import settings
from django.db import models
from django.utils import timezone


def beleg_upload_path(instance, filename):
    if instance.bewegung_id:
        return f"belege/{instance.bewegung.bank_account_id}/{instance.bewegung.booking_date:%Y/%m}/{filename}"
    return f"belege/posteingang/{timezone.now():%Y/%m}/{filename}"


class Beleg(models.Model):
    class DocumentType(models.TextChoices):
        BANKBELEG = "BANKBELEG", "Bankbeleg / Zahlungsbestätigung"
        QUITTUNG = "QUITTUNG", "Quittung / Rechnung"
        SONSTIGES = "SONSTIGES", "Sonstiges"

    bewegung = models.ForeignKey(
        "bank.Bewegung",
        on_delete=models.CASCADE,
        related_name="belege",
        null=True,
        blank=True,
        help_text="Leer = liegt im Posteingang und wurde noch keiner Bewegung zugewiesen.",
    )
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.QUITTUNG,
        verbose_name="Beleg-Typ",
    )
    file = models.FileField(upload_to=beleg_upload_path)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Beleg"
        verbose_name_plural = "Belege"

    def __str__(self):
        return self.original_filename
