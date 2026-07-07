from datetime import timedelta
from decimal import Decimal

from django.db.models import Q

AMOUNT_TOLERANCE = Decimal("0.05")
DATE_WINDOW_DAYS = 10


def _amount_range_filter(amount, tolerance=AMOUNT_TOLERANCE):
    """Bewegung.amount ist vorzeichenbehaftet (Ausgang negativ), der auf dem
    Beleg notierte Betrag aber immer positiv – daher beide Vorzeichen prüfen."""
    low, high = amount - tolerance, amount + tolerance
    return Q(amount__gte=low, amount__lte=high) | Q(amount__gte=-high, amount__lte=-low)


def find_matching_bewegung(amount, date=None):
    """Sucht eine eindeutig passende Bewegung (Betrag + optional Datumsfenster).
    Gibt nur bei genau einem Treffer eine Bewegung zurück, sonst None."""
    from bank.models import Bewegung

    if not amount:
        return None

    qs = Bewegung.objects.exclude(status=Bewegung.Status.IGNORED).filter(_amount_range_filter(amount))
    if date:
        qs = qs.filter(
            booking_date__gte=date - timedelta(days=DATE_WINDOW_DAYS),
            booking_date__lte=date + timedelta(days=DATE_WINDOW_DAYS),
        )
    matches = list(qs[:2])
    if len(matches) == 1:
        return matches[0]
    return None


def bewegungen_matching_amount(amount):
    from bank.models import Bewegung

    return Bewegung.objects.exclude(status=Bewegung.Status.IGNORED).filter(_amount_range_filter(amount))
