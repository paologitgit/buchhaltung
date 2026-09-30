"""Gruppierte Bilanz/Erfolgsrechnung-Berechnungen für zwei Darstellungen:

- SALDOBILANZ: nummerierte Kontengruppen (z.B. "10 Umlaufvermögen" >
  "100 Flüssige Mittel"), wie in der Treuhand-Saldobilanz gewohnt.
- JAHRESRECHNUNG: sprachliche Gruppen (z.B. "Flüssige Mittel"), für die
  vollständige Jahresrechnung mit EBITDA/EBIT/EBT-Kaskade, Anhang und
  Antrag über die Gewinnverwendung.

Der Jahreserfolg (Ertrag - Aufwand) wird in beiden Darstellungen LIVE
berechnet (wie schon in reports.bilanz()), nicht aus einem Buchungskonto
gelesen -- so bleibt die Bilanz auch ohne formellen Jahresabschluss-Buchungslauf
jederzeit aktuell und ausgeglichen."""

from datetime import timedelta
from decimal import Decimal

from .models import Account, AccountGroup, AccountType
from .reports import _account_sums, _signed_balance, erfolgsrechnung

ZERO = Decimal("0.00")


def _group_accounts(group):
    if group.tree == AccountGroup.Tree.SALDOBILANZ:
        return group.saldobilanz_accounts.all().order_by("code")
    return group.jahresrechnung_accounts.all().order_by("code")


def _group_balance(group, sums, cache=None):
    """Rekursive Summe eines Gruppenknotens: eigene Konten + alle Kinder."""
    if cache is None:
        cache = {}
    if group.id in cache:
        return cache[group.id]
    total = ZERO
    for account in _group_accounts(group):
        debit, credit = sums.get(account.id, (ZERO, ZERO))
        total += _signed_balance(account.account_type, debit, credit)
    for child in group.children.all():
        total += _group_balance(child, sums, cache)
    cache[group.id] = total
    return total


def _period_sums(fiscal_year):
    accounts = list(Account.objects.all())
    return _account_sums(accounts, date_from=fiscal_year.start_date, date_to=fiscal_year.end_date)


def _opening_sums(fiscal_year):
    accounts = list(Account.objects.all())
    return _account_sums(accounts, date_to=fiscal_year.start_date - timedelta(days=1))


def _closing_sums(fiscal_year):
    accounts = list(Account.objects.all())
    return _account_sums(accounts, date_to=fiscal_year.end_date)


# ---------------------------------------------------------------------------
# Bilanz (beide Bäume): rekursiv, mit Vorjahresvergleich


def _saldobilanz_bilanz_side(root_groups, sums, prev_sums, jahreserfolg, prev_jahreserfolg):
    """Saldobilanz-Stil: Wurzelgruppe als Kopfzeile ohne Wert, dann jede
    Kindgruppe mit ihren Konten und einer 'Total <Name>'-Zeile, zum Schluss
    'Total <Wurzelname>'. Die Gruppe mit Code '290' (Reserven/Jahreserfolg)
    erhält zusätzlich eine synthetische Zeile mit dem live berechneten
    Jahreserfolg, damit die Bilanz auch ohne gebuchten Abschluss stimmt."""
    rows = []
    side_total = ZERO
    side_prev_total = ZERO if prev_sums is not None else None

    for root in root_groups:
        rows.append({"code": root.code, "label": root.name, "value": None, "prev_value": None, "depth": 0, "bold": True})
        root_total = ZERO
        root_prev_total = ZERO if prev_sums is not None else None

        for child in root.children.all().order_by("order"):
            child_total = ZERO
            child_prev_total = ZERO if prev_sums is not None else None
            for account in _group_accounts(child):
                debit, credit = sums.get(account.id, (ZERO, ZERO))
                balance = _signed_balance(account.account_type, debit, credit)
                prev_balance = None
                if prev_sums is not None:
                    p_debit, p_credit = prev_sums.get(account.id, (ZERO, ZERO))
                    prev_balance = _signed_balance(account.account_type, p_debit, p_credit)
                rows.append(
                    {
                        "code": account.code,
                        "label": account.name,
                        "value": balance,
                        "prev_value": prev_balance,
                        "depth": 1,
                        "bold": False,
                    }
                )
                child_total += balance
                if prev_sums is not None:
                    child_prev_total += prev_balance

            if child.code == "290" and jahreserfolg is not None:
                rows.append(
                    {
                        "code": "",
                        "label": "Jahresverlust / Jahresgewinn",
                        "value": jahreserfolg,
                        "prev_value": prev_jahreserfolg,
                        "depth": 1,
                        "bold": False,
                    }
                )
                child_total += jahreserfolg
                if prev_sums is not None:
                    child_prev_total += prev_jahreserfolg or ZERO

            rows.append(
                {
                    "code": child.code,
                    "label": child.name,
                    "value": child_total,
                    "prev_value": child_prev_total,
                    "depth": 0,
                    "bold": True,
                }
            )
            root_total += child_total
            if prev_sums is not None:
                root_prev_total += child_prev_total

        rows.append(
            {
                "code": root.code,
                "label": f"Total {root.name}",
                "value": root_total,
                "prev_value": root_prev_total,
                "depth": 0,
                "bold": True,
            }
        )
        side_total += root_total
        if prev_sums is not None:
            side_prev_total += root_prev_total

    return rows, side_total, side_prev_total


def _jahresrechnung_nested(group, sums, prev_sums, depth, rows, jahreserfolg, prev_jahreserfolg):
    """Jahresrechnung-Stil: Gruppe zeigt zuerst ihren eigenen Totalwert,
    danach ihre Kinder bzw. Konten darunter (top-down)."""
    if group.code == "GEWINNVORTRAG":
        gewinnvortrag = _group_balance(group, sums)
        prev_gewinnvortrag = _group_balance(group, prev_sums) if prev_sums is not None else None
        total = gewinnvortrag + (jahreserfolg or ZERO)
        prev_total = (prev_gewinnvortrag + (prev_jahreserfolg or ZERO)) if prev_sums is not None else None
        rows.append({"label": group.name, "value": total, "prev_value": prev_total, "depth": depth, "bold": True})
        rows.append(
            {"label": "Gewinnvortrag", "value": gewinnvortrag, "prev_value": prev_gewinnvortrag, "depth": depth + 1, "bold": False}
        )
        rows.append(
            {
                "label": "Jahresverlust/-gewinn",
                "value": jahreserfolg,
                "prev_value": prev_jahreserfolg,
                "depth": depth + 1,
                "bold": False,
            }
        )
        return total, prev_total

    total = _group_balance(group, sums)
    prev_total = _group_balance(group, prev_sums) if prev_sums is not None else None
    rows.append({"label": group.name, "value": total, "prev_value": prev_total, "depth": depth, "bold": depth == 0})

    children = list(group.children.all().order_by("order"))
    if children:
        for child in children:
            _jahresrechnung_nested(child, sums, prev_sums, depth + 1, rows, jahreserfolg, prev_jahreserfolg)
    else:
        for account in _group_accounts(group):
            debit, credit = sums.get(account.id, (ZERO, ZERO))
            balance = _signed_balance(account.account_type, debit, credit)
            prev_balance = None
            if prev_sums is not None:
                p_debit, p_credit = prev_sums.get(account.id, (ZERO, ZERO))
                prev_balance = _signed_balance(account.account_type, p_debit, p_credit)
            if balance == 0 and not prev_balance:
                continue
            rows.append(
                {"label": account.name, "value": balance, "prev_value": prev_balance, "depth": depth + 1, "bold": False}
            )
    return total, prev_total


def _jahresrechnung_bilanz_side(root_groups, sums, prev_sums, jahreserfolg, prev_jahreserfolg):
    """Wurzelgruppen (Umlaufvermögen/Anlagevermögen bzw. Fremdkapital/
    Eigenkapital): Kinder zuerst (top-down je Kind), Wurzel-Total am Schluss."""
    rows = []
    side_total = ZERO
    side_prev_total = ZERO if prev_sums is not None else None

    for root in root_groups:
        for child in root.children.all().order_by("order"):
            _jahresrechnung_nested(child, sums, prev_sums, 0, rows, jahreserfolg, prev_jahreserfolg)
        root_total = _group_balance(root, sums)
        if root.children.filter(code="GEWINNVORTRAG").exists():
            root_total += jahreserfolg or ZERO
        root_prev_total = None
        if prev_sums is not None:
            root_prev_total = _group_balance(root, prev_sums)
            if root.children.filter(code="GEWINNVORTRAG").exists():
                root_prev_total += prev_jahreserfolg or ZERO
        rows.append({"label": root.name, "value": root_total, "prev_value": root_prev_total, "depth": 0, "bold": True})
        side_total += root_total
        if prev_sums is not None:
            side_prev_total += root_prev_total

    return rows, side_total, side_prev_total


def grouped_bilanz(fiscal_year, tree, prev_fiscal_year=None):
    """Gruppierte Bilanz für einen der beiden Bäume, mit Zwischentotalen und
    optionalem Vorjahresvergleich."""
    sums = _closing_sums(fiscal_year)
    prev_sums = _closing_sums(prev_fiscal_year) if prev_fiscal_year else None

    jahreserfolg = erfolgsrechnung(fiscal_year)["result"]
    prev_jahreserfolg = erfolgsrechnung(prev_fiscal_year)["result"] if prev_fiscal_year else None

    aktiva_roots = AccountGroup.objects.filter(tree=tree, parent=None, account_type=AccountType.AKTIVA).order_by(
        "order"
    )
    passiva_roots = AccountGroup.objects.filter(tree=tree, parent=None, account_type=AccountType.PASSIVA).order_by(
        "order"
    )

    side_fn = _saldobilanz_bilanz_side if tree == AccountGroup.Tree.SALDOBILANZ else _jahresrechnung_bilanz_side

    aktiva_rows, total_aktiva, prev_total_aktiva = side_fn(aktiva_roots, sums, prev_sums, None, None)
    passiva_rows, total_passiva, prev_total_passiva = side_fn(
        passiva_roots, sums, prev_sums, jahreserfolg, prev_jahreserfolg
    )

    return {
        "aktiva_rows": aktiva_rows,
        "passiva_rows": passiva_rows,
        "total_aktiva": total_aktiva,
        "total_passiva": total_passiva,
        "prev_total_aktiva": prev_total_aktiva,
        "prev_total_passiva": prev_total_passiva,
        "jahreserfolg": jahreserfolg,
        "prev_jahreserfolg": prev_jahreserfolg,
        "balanced": total_aktiva == total_passiva,
    }


# ---------------------------------------------------------------------------
# Erfolgsrechnung (beide Bäume): feste Kaskade mit Zwischenergebnissen


SALDOBILANZ_ER_PIPELINE = [
    {"type": "group", "code": "30"},
    {"type": "subtotal", "label": "Nettoerlös aus Lieferungen und Leistungen"},
    {"type": "group", "code": "40"},
    {"type": "subtotal", "label": "Bruttoergebnis 1"},
    {"type": "group", "code": "50"},
    {"type": "group", "code": "57"},
    {"type": "subtotal", "label": "Bruttoergebnis 2"},
    {"type": "group", "code": "610"},
    {"type": "group", "code": "620"},
    {"type": "group", "code": "630"},
    {"type": "group", "code": "640"},
    {"type": "group", "code": "650"},
    {"type": "group", "code": "670"},
    {"type": "group", "code": "675"},
    {"type": "subtotal", "label": "Betriebsergebnis 1"},
    {"type": "group", "code": "680"},
    {"type": "subtotal", "label": "Betriebsergebnis 2"},
    {"type": "group", "code": "690"},
    {"type": "subtotal", "label": "Jahresergebnis vor Steuern"},
    {"type": "group", "code": "890"},
    {"type": "subtotal", "label": "Jahresverlust / Jahresgewinn"},
]

JAHRESRECHNUNG_ER_PIPELINE = [
    {"type": "group", "code": "BRUTTOERTRAG"},
    {"type": "subtotal", "label": "Nettoerlöse aus Lieferungen und Leistungen"},
    {"type": "group", "code": "MATERIALAUFWAND"},
    {"type": "subtotal", "label": "Bruttogewinn I"},
    {"type": "group", "code": "PERSONALAUFWAND"},
    {"type": "subtotal", "label": "Bruttogewinn II"},
    {"type": "group", "code": "UEBRIGER_BETRIEBSAUFWAND"},
    {"type": "subtotal", "label": "Betriebliches Ergebnis vor Zinsen, Steuern und Abschreibungen (EBITDA)"},
    {"type": "group", "code": "ABSCHREIBUNGEN"},
    {"type": "subtotal", "label": "Betriebliches Ergebnis vor Zinsen und Steuern (EBIT)"},
    {"type": "group", "code": "FINANZERFOLG"},
    {"type": "subtotal", "label": "Jahresergebnis vor Steuern (EBT)"},
    {"type": "group", "code": "STEUERN"},
    {"type": "subtotal", "label": "Jahresverlust/-gewinn"},
]


def _contribution(account, debit, credit):
    """Ertrag positiv, Aufwand negativ -- Summe ergibt direkt den Erfolg."""
    balance = _signed_balance(account.account_type, debit, credit)
    return balance if account.account_type == AccountType.ERTRAG else -balance


def grouped_erfolgsrechnung(fiscal_year, tree, prev_fiscal_year=None):
    sums = _period_sums(fiscal_year)
    prev_sums = _period_sums(prev_fiscal_year) if prev_fiscal_year else None

    groups_by_code = {g.code: g for g in AccountGroup.objects.filter(tree=tree)}
    pipeline = SALDOBILANZ_ER_PIPELINE if tree == AccountGroup.Tree.SALDOBILANZ else JAHRESRECHNUNG_ER_PIPELINE

    rows = []
    running = ZERO
    prev_running = ZERO if prev_sums is not None else None
    ertrag_base = None
    prev_ertrag_base = None

    for step in pipeline:
        if step["type"] == "group":
            group = groups_by_code.get(step["code"])
            if not group:
                continue
            group_total = ZERO
            group_prev_total = ZERO if prev_sums is not None else None
            for account in _group_accounts(group):
                debit, credit = sums.get(account.id, (ZERO, ZERO))
                contribution = _contribution(account, debit, credit)
                prev_contribution = None
                if prev_sums is not None:
                    p_debit, p_credit = prev_sums.get(account.id, (ZERO, ZERO))
                    prev_contribution = _contribution(account, p_debit, p_credit)
                if contribution == 0 and not prev_contribution:
                    continue
                rows.append(
                    {
                        "code": account.code,
                        "label": account.name,
                        "value": contribution,
                        "prev_value": prev_contribution,
                        "depth": 1,
                        "bold": False,
                    }
                )
                group_total += contribution
                if prev_sums is not None:
                    group_prev_total += prev_contribution or ZERO
            rows.append(
                {
                    "code": group.code,
                    "label": group.name,
                    "value": group_total,
                    "prev_value": group_prev_total,
                    "depth": 0,
                    "bold": True,
                }
            )
            running += group_total
            if prev_sums is not None:
                prev_running += group_prev_total
        elif step["type"] == "subtotal":
            rows.append(
                {"code": "", "label": step["label"], "value": running, "prev_value": prev_running, "depth": 0, "bold": True}
            )
            if ertrag_base is None:
                ertrag_base = running
                prev_ertrag_base = prev_running

    return {
        "rows": rows,
        "result": running,
        "prev_result": prev_running,
        "ertrag_base": ertrag_base or Decimal("1.00"),
        "prev_ertrag_base": prev_ertrag_base,
    }


# ---------------------------------------------------------------------------
# Anhang: Aufschlüsselung für Jahresrechnung-Gruppen mit mehreren Konten


BILANZ_ANHANG_CODES = [
    "FLUESSIGE_MITTEL",
    "FORDERUNGEN_LL",
    "UEBRIGE_FORDERUNGEN",
    "AKTIVE_RA",
    "MOBILE_SACHANLAGEN",
    "VERB_LL",
    "KURZFR_VERZINSLICH",
    "UEBRIGE_KURZFR_VERB",
    "PASSIVE_RA",
    "STAMMKAPITAL",
    "GESETZLICHE_RESERVE",
]
ER_ANHANG_CODES = [
    "BRUTTOERTRAG",
    "MATERIALAUFWAND",
    "PERSONALAUFWAND",
    "UEBRIGER_BETRIEBSAUFWAND",
    "ABSCHREIBUNGEN",
    "FINANZERFOLG",
    "STEUERN",
]


def _anhang_note(group, sums, prev_sums, is_er):
    contributing = 0
    for account in _group_accounts(group):
        debit, credit = sums.get(account.id, (ZERO, ZERO))
        if _signed_balance(account.account_type, debit, credit) != 0:
            contributing += 1
    if contributing < 2:
        return None

    rows = []
    total = ZERO
    prev_total = ZERO if prev_sums is not None else None
    for account in _group_accounts(group):
        debit, credit = sums.get(account.id, (ZERO, ZERO))
        value = _contribution(account, debit, credit) if is_er else _signed_balance(account.account_type, debit, credit)
        prev_value = None
        if prev_sums is not None:
            p_debit, p_credit = prev_sums.get(account.id, (ZERO, ZERO))
            prev_value = (
                _contribution(account, p_debit, p_credit)
                if is_er
                else _signed_balance(account.account_type, p_debit, p_credit)
            )
        if value == 0 and not prev_value:
            continue
        rows.append({"label": account.name, "value": value, "prev_value": prev_value})
        total += value
        if prev_sums is not None:
            prev_total += prev_value or ZERO

    return {"title": group.name, "rows": rows, "total": total, "prev_total": prev_total}


def jahresrechnung_anhang(fiscal_year, prev_fiscal_year=None):
    """Automatische Anhang-Notizen für jede Jahresrechnung-Gruppe mit mehr
    als einem beitragenden Konto (Saldo bzw. Periodenbewegung ungleich 0)."""
    groups_by_code = {g.code: g for g in AccountGroup.objects.filter(tree=AccountGroup.Tree.JAHRESRECHNUNG)}

    bilanz_sums = _closing_sums(fiscal_year)
    prev_bilanz_sums = _closing_sums(prev_fiscal_year) if prev_fiscal_year else None
    er_sums = _period_sums(fiscal_year)
    prev_er_sums = _period_sums(prev_fiscal_year) if prev_fiscal_year else None

    notes = []
    for code in BILANZ_ANHANG_CODES:
        group = groups_by_code.get(code)
        if not group:
            continue
        note = _anhang_note(group, bilanz_sums, prev_bilanz_sums, is_er=False)
        if note:
            notes.append(note)

    for code in ER_ANHANG_CODES:
        group = groups_by_code.get(code)
        if not group:
            continue
        note = _anhang_note(group, er_sums, prev_er_sums, is_er=True)
        if note:
            notes.append(note)

    return notes


# ---------------------------------------------------------------------------
# Antrag über die Verwendung des Bilanzgewinnes


def gewinnverwendung(fiscal_year):
    groups_by_code = {g.code: g for g in AccountGroup.objects.filter(tree=AccountGroup.Tree.JAHRESRECHNUNG)}
    gv_group = groups_by_code.get("GEWINNVORTRAG")
    accounts = list(gv_group.jahresrechnung_accounts.all()) if gv_group else []
    opening_sums = _account_sums(accounts, date_to=fiscal_year.start_date - timedelta(days=1))

    gewinnvortrag = ZERO
    for account in accounts:
        debit, credit = opening_sums.get(account.id, (ZERO, ZERO))
        gewinnvortrag += _signed_balance(account.account_type, debit, credit)

    jahresergebnis = erfolgsrechnung(fiscal_year)["result"]
    total = gewinnvortrag + jahresergebnis
    zuweisung = fiscal_year.gewinnruecklage_zuweisung or ZERO
    vortrag = total - zuweisung

    return {
        "gewinnvortrag": gewinnvortrag,
        "jahresergebnis": jahresergebnis,
        "total": total,
        "zuweisung": zuweisung,
        "vortrag": vortrag,
    }
