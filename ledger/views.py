from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from core.decorators import owner_required

from .analytics import build_income_expense_chart, monthly_income_expense, top_expense_accounts
from .export import export_journal_csv, export_journal_xlsx, export_journal_zip
from .forms import FiscalYearForm
from .models import Account, FiscalYear, JournalEntry


@login_required
def account_list(request):
    accounts = Account.objects.all()
    return render(request, "ledger/account_list.html", {"accounts": accounts})


@login_required
def auswertung(request):
    fiscal_years = FiscalYear.objects.all()
    fiscal_year_id = request.GET.get("geschaeftsjahr")
    fiscal_year = None
    if fiscal_year_id:
        fiscal_year = fiscal_years.filter(pk=fiscal_year_id).first()
    elif fiscal_years.exists():
        fiscal_year = fiscal_years.filter(is_closed=False).order_by("-start_date").first() or fiscal_years.first()

    monthly_data = monthly_income_expense(fiscal_year)
    chart = build_income_expense_chart(monthly_data) if monthly_data else None
    top_accounts = top_expense_accounts(fiscal_year)

    total_income = sum((v["income"] for _, v in monthly_data), Decimal("0.00"))
    total_expense = sum((v["expense"] for _, v in monthly_data), Decimal("0.00"))

    context = {
        "fiscal_years": fiscal_years,
        "selected_fiscal_year": fiscal_year,
        "chart": chart,
        "monthly_data": monthly_data,
        "top_accounts": top_accounts,
        "total_income": total_income,
        "total_expense": total_expense,
    }
    return render(request, "ledger/auswertung.html", context)


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
    if fmt == "zip":
        return export_journal_zip(fiscal_year_id)
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
