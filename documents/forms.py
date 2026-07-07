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


class PosteingangUploadForm(BelegUploadForm):
    class Meta(BelegUploadForm.Meta):
        fields = ["file", "document_type", "expected_amount", "expected_date", "note"]
        labels = {
            **BelegUploadForm.Meta.labels,
            "expected_amount": "Betrag",
            "expected_date": "Datum (optional)",
        }
        widgets = {"expected_date": forms.DateInput(attrs={"type": "date"})}
        help_texts = {
            "expected_amount": "Wird genutzt, um den Beleg automatisch der passenden Bewegung zuzuordnen.",
        }


class PosteingangBulkUploadForm(forms.Form):
    """Nur für das document_type-Feld – die Dateien selbst kommen über ein
    manuell im Template gerendertes <input multiple>, da Django-FileFields
    von Haus aus nur eine Datei pro Feld unterstützen."""

    document_type = forms.ChoiceField(choices=Beleg.DocumentType.choices, label="Beleg-Typ (gilt für alle)")
