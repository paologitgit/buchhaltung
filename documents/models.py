from django.conf import settings
from django.db import models


def beleg_upload_path(instance, filename):
    return f"belege/{instance.bewegung.bank_account_id}/{instance.bewegung.booking_date:%Y/%m}/{filename}"


class Beleg(models.Model):
    bewegung = models.ForeignKey(
        "bank.Bewegung", on_delete=models.CASCADE, related_name="belege"
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
