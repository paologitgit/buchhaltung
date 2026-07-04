from django import forms

from .models import FiscalYear


class FiscalYearForm(forms.ModelForm):
    class Meta:
        model = FiscalYear
        fields = ["start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }
