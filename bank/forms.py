from django import forms

from ledger.models import Account
from vat.models import VatCode

from .models import BankAccount


class CSVImportForm(forms.Form):
    bank_account = forms.ModelChoiceField(
        queryset=BankAccount.objects.filter(is_active=True), label="Bankkonto"
    )
    csv_file = forms.FileField(label="CSV-Datei")

    def clean_csv_file(self):
        f = self.cleaned_data["csv_file"]
        if not f.name.lower().endswith(".csv"):
            raise forms.ValidationError("Bitte eine CSV-Datei hochladen.")
        if f.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Datei ist zu gross (max. 10 MB).")
        return f


class BewegungBookingForm(forms.Form):
    gegenkonto = forms.ModelChoiceField(
        queryset=Account.objects.filter(is_active=True, is_bank_account=False),
        label="Gegenkonto",
    )
    vat_code = forms.ModelChoiceField(
        queryset=VatCode.objects.filter(active=True), required=False, label="MWST-Code"
    )
