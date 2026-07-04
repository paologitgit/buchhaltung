from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from core.decorators import owner_required

from .export import export_journal_csv, export_journal_xlsx
from .forms import FiscalYearForm
from .models import Account, FiscalYear, JournalEntry


@login_required
def account_list(request):
    accounts = Account.objects.all()
    return render(request, "ledger/account_list.html", {"accounts": accounts})


@login_required
def journal_list(request):
    entries = JournalEntry.objects.select_related("fiscal_year", "created_by").prefetch_related(
        "lines__account"
    )
    fiscal_year_id = request.GET.get("geschaeftsjahr")
    if fiscal_year_id:
        entries = entries.filter(fiscal_year_id=fiscal_year_id)
    return render(
        request,
        "ledger/journal_list.html",
        {"entries": entries[:500], "fiscal_years": FiscalYear.objects.all()},
    )


@login_required
def fiscal_year_list(request):
    return render(request, "ledger/fiscal_year_list.html", {"fiscal_years": FiscalYear.objects.all()})


@login_required
def journal_export(request, fmt):
    fiscal_year_id = request.GET.get("geschaeftsjahr")
    if fmt == "csv":
        return export_journal_csv(fiscal_year_id)
    if fmt == "xlsx":
        return export_journal_xlsx(fiscal_year_id)
    return HttpResponseBadRequest("Unbekanntes Exportformat.")


@login_required
@owner_required
def fiscal_year_create(request):
    if request.method == "POST":
        form = FiscalYearForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Geschäftsjahr wurde angelegt.")
            return redirect("fiscal_year_list")
    else:
        form = FiscalYearForm()
    return render(request, "ledger/fiscal_year_form.html", {"form": form})


@login_required
@owner_required
def fiscal_year_close(request, pk):
    fiscal_year = get_object_or_404(FiscalYear, pk=pk)
    if request.method == "POST":
        fiscal_year.close()
        messages.success(request, "Geschäftsjahr wurde abgeschlossen und gesperrt.")
        return redirect("fiscal_year_list")
    return render(request, "ledger/fiscal_year_close_confirm.html", {"fiscal_year": fiscal_year})
