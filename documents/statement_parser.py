import re
from datetime import date
from decimal import Decimal, InvalidOperation

DATE_LINE_RE = re.compile(r"^(\d{2})\.(\d{2})\s+(.*)$")
AMOUNT_RE = re.compile(r"[\d']+\.\d{2}(?!\s*%)")
ISSUE_DATE_RE = re.compile(
    r"(\d{1,2})\.\s*"
    r"(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
    r"\s+(\d{4})",
    re.IGNORECASE,
)
GERMAN_MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12,
}
# Zeilen, die eine laufende Position beenden, ohne selbst eine neue zu beginnen
# (Kartennummer-Kopfzeilen, Zwischensummen, Seitenfusszeilen ...).
BOUNDARY_PREFIXES = ("total", "visa ", "mastercard ", "amex", "american express", "seite ")
SKIP_DESCRIPTION_PREFIXES = ("saldovortrag",)


def _extract_reference_date(text):
    match = ISSUE_DATE_RE.search(text)
    if not match:
        return None
    day, month_name, year = match.groups()
    month = GERMAN_MONTHS.get(month_name.lower())
    if not month:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def _is_boundary(line):
    stripped = line.strip()
    if not stripped:
        return True
    lower = stripped.lower()
    return lower.startswith(BOUNDARY_PREFIXES)


def _clean_description(first_line, matched_amount_text):
    idx = first_line.rfind(matched_amount_text)
    if idx == -1:
        return first_line.strip(" ,")
    return (first_line[:idx] + first_line[idx + len(matched_amount_text):]).strip(" ,")


def parse_statement(text):
    """Extrahiert (Datum, Beschreibung, Betrag) je Position aus einer
    Kreditkarten-Monatsabrechnung. Aktuell auf das Cornèrcard-Layout
    zugeschnitten (Zeilenformat "TT.MM Beschreibung [Betrag]")."""
    reference_date = _extract_reference_date(text) or date.today()
    reference_month = reference_date.month
    reference_year = reference_date.year

    transactions = []
    current = None

    def finalize():
        if current is None:
            return
        block_text = " ".join(current["block_lines"])
        amounts = AMOUNT_RE.findall(block_text)
        if not amounts:
            return
        amount_text = amounts[-1]
        try:
            amount = Decimal(amount_text.replace("'", ""))
        except InvalidOperation:
            return

        description = _clean_description(current["block_lines"][0], amount_text)
        if not description or description.lower().startswith(SKIP_DESCRIPTION_PREFIXES):
            return

        month = current["month"]
        year = reference_year - 1 if month > reference_month else reference_year
        try:
            tx_date = date(year, month, current["day"])
        except ValueError:
            return

        transactions.append({"date": tx_date, "description": description, "amount": amount})

    for raw_line in text.splitlines():
        line = raw_line.strip()
        date_match = DATE_LINE_RE.match(line)
        # "21.62 US Dollars" (Fremdwaehrungsbetrag) sieht wie ein Datum aus --
        # nur echte Monate (1-12) als neue Position werten, sonst faellt die
        # Zeile durch zur Fortsetzungs-Behandlung weiter unten.
        if date_match and 1 <= int(date_match.group(2)) <= 12:
            finalize()
            day, month, rest = date_match.groups()
            current = {"day": int(day), "month": int(month), "block_lines": [rest]}
            continue
        if current is None:
            continue
        if _is_boundary(line):
            finalize()
            current = None
            continue
        current["block_lines"].append(line)

    finalize()
    return transactions
