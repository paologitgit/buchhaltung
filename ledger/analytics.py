from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncMonth

from .models import Account, JournalLine

BAR_WIDTH = 22
BAR_GAP = 4
GROUP_GAP = 26
CHART_HEIGHT = 220
MARGIN_LEFT = 70
MARGIN_TOP = 16
MARGIN_BOTTOM = 34
CORNER_RADIUS = 4


def monthly_income_expense(fiscal_year=None):
    """Netto Einnahmen (Ertrag) und Ausgaben (Aufwand) pro Monat, aus den
    gebuchten Journalzeilen (ohne MWST-Konten, da diese weder Aufwand noch
    Ertrag sind)."""
    lines = JournalLine.objects.filter(
        account__account_type__in=[Account.Type.AUFWAND, Account.Type.ERTRAG]
    )
    if fiscal_year:
        lines = lines.filter(journal_entry__fiscal_year=fiscal_year)

    rows = (
        lines.annotate(month=TruncMonth("journal_entry__date"))
        .values("month", "account__account_type")
        .annotate(debit=Sum("debit_amount"), credit=Sum("credit_amount"))
        .order_by("month")
    )

    by_month = {}
    for row in rows:
        month = row["month"]
        bucket = by_month.setdefault(month, {"income": Decimal("0.00"), "expense": Decimal("0.00")})
        debit = row["debit"] or Decimal("0.00")
        credit = row["credit"] or Decimal("0.00")
        if row["account__account_type"] == Account.Type.ERTRAG:
            bucket["income"] += credit - debit
        else:
            bucket["expense"] += debit - credit

    return sorted(by_month.items())


def top_expense_accounts(fiscal_year=None, limit=8):
    """Aufwand-Konten absteigend nach gebuchtem Betrag, für die Periode."""
    lines = JournalLine.objects.filter(account__account_type=Account.Type.AUFWAND)
    if fiscal_year:
        lines = lines.filter(journal_entry__fiscal_year=fiscal_year)

    rows = (
        lines.values("account__code", "account__name")
        .annotate(debit=Sum("debit_amount"), credit=Sum("credit_amount"))
        .order_by()
    )
    totals = []
    for row in rows:
        amount = (row["debit"] or Decimal("0.00")) - (row["credit"] or Decimal("0.00"))
        if amount > 0:
            totals.append({"code": row["account__code"], "name": row["account__name"], "amount": amount})
    totals.sort(key=lambda t: t["amount"], reverse=True)

    max_amount = totals[0]["amount"] if totals else Decimal("0.00")
    for t in totals[:limit]:
        t["percent"] = round(float(t["amount"] / max_amount) * 100) if max_amount else 0
    return totals[:limit]


def _bar_path(x, y, width, height):
    if height <= 0:
        return ""
    radius = min(CORNER_RADIUS, height / 2, width / 2)
    return (
        f"M{x},{y + height} "
        f"L{x},{y + radius} "
        f"Q{x},{y} {x + radius},{y} "
        f"L{x + width - radius},{y} "
        f"Q{x + width},{y} {x + width},{y + radius} "
        f"L{x + width},{y + height} Z"
    )


def build_income_expense_chart(monthly_data):
    """Baut die Geometrie für ein gruppiertes SVG-Balkendiagramm (reine
    Python-Berechnung, kein JS nötig)."""
    values = [v["income"] for _, v in monthly_data] + [v["expense"] for _, v in monthly_data]
    max_value = max(values) if values and max(values) > 0 else Decimal("1.00")

    group_width = BAR_WIDTH * 2 + BAR_GAP
    bars = []
    x = MARGIN_LEFT
    for month, values in monthly_data:
        income_h = float(values["income"] / max_value) * CHART_HEIGHT
        expense_h = float(values["expense"] / max_value) * CHART_HEIGHT
        baseline = MARGIN_TOP + CHART_HEIGHT
        bars.append(
            {
                "label": _format_month(month),
                "income": values["income"],
                "expense": values["expense"],
                "difference": values["income"] - values["expense"],
                "income_path": _bar_path(x, baseline - income_h, BAR_WIDTH, income_h),
                "expense_path": _bar_path(x + BAR_WIDTH + BAR_GAP, baseline - expense_h, BAR_WIDTH, expense_h),
                "label_x": x + group_width / 2,
            }
        )
        x += group_width + GROUP_GAP

    total_width = max(x - GROUP_GAP + MARGIN_LEFT / 2, MARGIN_LEFT + 40)
    baseline = MARGIN_TOP + CHART_HEIGHT
    gridlines = []
    for fraction in (0, 0.25, 0.5, 0.75, 1.0):
        y = baseline - fraction * CHART_HEIGHT
        gridlines.append({"y": y, "label": _format_chf(max_value * Decimal(str(fraction)))})

    return {
        "bars": bars,
        "width": total_width,
        "height": MARGIN_TOP + CHART_HEIGHT + MARGIN_BOTTOM,
        "baseline": baseline,
        "margin_left": MARGIN_LEFT,
        "gridlines": gridlines,
    }


def _format_month(date):
    monatsnamen = [
        "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
        "Jul", "Aug", "Sep", "Okt", "Nov", "Dez",
    ]
    return f"{monatsnamen[date.month - 1]} {date.year % 100:02d}"


def _format_chf(amount):
    return f"{amount:,.0f}".replace(",", "'")
