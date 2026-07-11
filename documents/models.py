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
    extracted_text = models.TextField(
        blank=True,
        default="",
        db_default="",
        verbose_name="Erkannter Text",
        help_text="Beim Hochladen automatisch aus dem Dokument extrahierter Text (PDF-Text oder OCR), für die Volltextsuche.",
    )
    source = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="copies",
        help_text="Gesetzt, wenn dieser Beleg über 'an weitere Bewegung anhängen' als Kopie eines anderen Belegs entstanden ist.",
    )
    hidden = models.BooleanField(
        default=False,
        verbose_name="Nicht mehr anzeigen",
        help_text="Beleg wurde bereits abgelegt und soll in der Belege-Übersicht ausgeblendet werden können.",
    )
    expected_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Betrag",
        help_text="Für die automatische Zuordnung zu einer Bewegung beim Hochladen im Posteingang.",
    )
    expected_date = models.DateField(null=True, blank=True, verbose_name="Datum")

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Beleg"
        verbose_name_plural = "Belege"

    def __str__(self):
        return self.original_filename
