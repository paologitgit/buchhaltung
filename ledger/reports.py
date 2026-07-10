from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum

from .models import Account, JournalLine

DEBIT_NORMAL_TYPES = (Account.Type.AKTIVA, Account.Type.AUFWAND)
BILANZ_TYPES = (Account.Type.AKTIVA, Account.Type.PASSIVA)


def _signed_balance(account_type, debit, credit):
    debit = debit or Decimal("0.00")
    credit = credit or Decimal("0.00")
    if account_type in DEBIT_NORMAL_TYPES:
        return debit - credit
    return credit - debit


def _account_sums(accounts, date_from=None, date_to=None):
    """Soll-/Haben-Summen je Konto für gebuchte Journalzeilen im Zeitraum
    (Grenzen inklusive, None = offen). Gibt {account_id: (debit, credit)} zurück."""
    accounts = list(accounts)
    if not accounts:
        return {}
    lines = JournalLine.objects.filter(account__in=accounts)
    if date_from:
        lines = lines.filter(journal_entry__date__gte=date_from)
    if date_to:
        lines = lines.filter(journal_entry__date__lte=date_to)
    rows = lines.values("account_id").annotate(debit=Sum("debit_amount"), credit=Sum("credit_amount"))
    return {
        row["account_id"]: (row["debit"] or Decimal("0.00"), row["credit"] or Decimal("0.00")) for row in rows
    }


def saldobilanz(fiscal_year):
    """Saldobilanz: Eröffnungssaldo, Soll-/Haben-Bewegungen und Schlusssaldo
    je Konto für das gewählte Geschäftsjahr."""
    accounts = list(Account.objects.all().order_by("code"))
    opening_sums = _account_sums(accounts, date_to=fiscal_year.start_date - timedelta(days=1))
    period_sums = _account_sums(accounts, date_from=fiscal_year.start_date, date_to=fiscal_year.end_date)

    rows = []
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")
    for account in accounts:
        o_debit, o_credit = opening_sums.get(account.id, (Decimal("0.00"), Decimal("0.00")))
        p_debit, p_credit = period_sums.get(account.id, (Decimal("0.00"), Decimal("0.00")))
        opening_balance = (
            _signed_balance(account.account_type, o_debit, o_credit)
            if account.account_type in BILANZ_TYPES
            else Decimal("0.00")
        )
        if opening_balance == 0 and p_debit == 0 and p_credit == 0:
            continue
        closing_balance = opening_balance + _signed_balance(account.account_type, p_debit, p_credit)
        rows.append(
            {
                "account": account,
                "opening_balance": opening_balance,
                "debit": p_debit,
                "credit": p_credit,
                "closing_balance": closing_balance,
            }
        )
        total_debit += p_debit
        total_credit += p_credit

    return {"rows": rows, "total_debit": total_debit, "total_credit": total_credit}


def erfolgsrechnung(fiscal_year):
    """Erfolgsrechnung (Aufwand/Ertrag) für die Periode des Geschäftsjahres."""
    aufwand_accounts = Account.objects.filter(account_type=Account.Type.AUFWAND).order_by("code")
    ertrag_accounts = Account.objects.filter(account_type=Account.Type.ERTRAG).order_by("code")

    aufwand_sums = _account_sums(aufwand_accounts, date_from=fiscal_year.start_date, date_to=fiscal_year.end_date)
    ertrag_sums = _account_sums(ertrag_accounts, date_from=fiscal_year.start_date, date_to=fiscal_year.end_date)

    aufwand_rows = []
    total_aufwand = Decimal("0.00")
    for account in aufwand_accounts:
        debit, credit = aufwand_sums.get(account.id, (Decimal("0.00"), Decimal("0.00")))
        balance = _signed_balance(account.account_type, debit, credit)
        if balance == 0:
            continue
        aufwand_rows.append({"account": account, "balance": balance})
        total_aufwand += balance

    ertrag_rows = []
    total_ertrag = Decimal("0.00")
    for account in ertrag_accounts:
        debit, credit = ertrag_sums.get(account.id, (Decimal("0.00"), Decimal("0.00")))
        balance = _signed_balance(account.account_type, debit, credit)
        if balance == 0:
            continue
        ertrag_rows.append({"account": account, "balance": balance})
        total_ertrag += balance

    return {
        "aufwand_rows": aufwand_rows,
        "ertrag_rows": ertrag_rows,
        "total_aufwand": total_aufwand,
        "total_ertrag": total_ertrag,
        "result": total_ertrag - total_aufwand,
    }


def bilanz(fiscal_year):
    """Bilanz per Ende Geschäftsjahr: Aktiven und Passiven kumuliert seit
    Eröffnung, plus Jahreserfolg als Ausgleichsposten auf der Passivseite."""
    aktiva_accounts = Account.objects.filter(account_type=Account.Type.AKTIVA).order_by("code")
    passiva_accounts = Account.objects.filter(account_type=Account.Type.PASSIVA).order_by("code")

    aktiva_sums = _account_sums(aktiva_accounts, date_to=fiscal_year.end_date)
    passiva_sums = _account_sums(passiva_accounts, date_to=fiscal_year.end_date)

    aktiva_rows = []
    total_aktiva = Decimal("0.00")
    for account in aktiva_accounts:
        debit, credit = aktiva_sums.get(account.id, (Decimal("0.00"), Decimal("0.00")))
        balance = _signed_balance(account.account_type, debit, credit)
        if balance == 0:
            continue
        aktiva_rows.append({"account": account, "balance": balance})
        total_aktiva += balance

    passiva_rows = []
    total_passiva = Decimal("0.00")
    for account in passiva_accounts:
        debit, credit = passiva_sums.get(account.id, (Decimal("0.00"), Decimal("0.00")))
        balance = _signed_balance(account.account_type, debit, credit)
        if balance == 0:
            continue
        passiva_rows.append({"account": account, "balance": balance})
        total_passiva += balance

    jahreserfolg = erfolgsrechnung(fiscal_year)["result"]
    total_passiva_mit_erfolg = total_passiva + jahreserfolg

    return {
        "aktiva_rows": aktiva_rows,
        "passiva_rows": passiva_rows,
        "total_aktiva": total_aktiva,
        "total_passiva": total_passiva,
        "jahreserfolg": jahreserfolg,
        "total_passiva_mit_erfolg": total_passiva_mit_erfolg,
        "balanced": total_aktiva == total_passiva_mit_erfolg,
    }


def kontoblatt(account, fiscal_year):
    """Kontoblatt: Eröffnungssaldo, alle Buchungszeilen des Kontos in der
    Periode mit laufendem Saldo, Schlusssaldo."""
    opening_debit, opening_credit = _account_sums(
        [account], date_to=fiscal_year.start_date - timedelta(days=1)
    ).get(account.id, (Decimal("0.00"), Decimal("0.00")))
    opening_balance = (
        _signed_balance(account.account_type, opening_debit, opening_credit)
        if account.account_type in BILANZ_TYPES
        else Decimal("0.00")
    )

    lines = (
        JournalLine.objects.filter(
            account=account,
            journal_entry__date__gte=fiscal_year.start_date,
            journal_entry__date__lte=fiscal_year.end_date,
        )
        .select_related("journal_entry", "vat_code")
        .order_by("journal_entry__date", "journal_entry__id", "id")
    )

    running = opening_balance
    entries = []
    for line in lines:
        running += _signed_balance(account.account_type, line.debit_amount, line.credit_amount)
        entries.append({"line": line, "running_balance": running})

    return {
        "account": account,
        "opening_balance": opening_balance,
        "entries": entries,
        "closing_balance": running,
    }
