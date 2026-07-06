from django.conf import settings
from django.core.exceptions import ValidationError
from django import forms

from .models import Beleg


class BelegUploadForm(forms.ModelForm):
    class Meta:
        model = Beleg
        fields = ["file", "document_type", "note"]
        labels = {"file": "Beleg-Datei (PDF/Bild)", "document_type": "Beleg-Typ", "note": "Notiz"}

    def clean_file(self):
        f = self.cleaned_data["file"]
        if f.size > settings.MAX_UPLOAD_SIZE_BYTES:
            raise ValidationError("Datei ist zu gross (max. 15 MB).")
        content_type = getattr(f, "content_type", "") or ""
        if content_type not in settings.ALLOWED_BELEG_CONTENT_TYPES:
            raise ValidationError("Nur PDF- oder Bilddateien (JPEG/PNG/WEBP) sind erlaubt.")
        return f
