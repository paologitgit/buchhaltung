from functools import wraps

from django.core.exceptions import PermissionDenied


def owner_required(view_func):
    """Nur für die Rolle OWNER: Treuhänder:innen haben ausschliesslich Lesezugriff."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.has_write_access():
            raise PermissionDenied("Diese Aktion ist nur für Inhaber:in verfügbar.")
        return view_func(request, *args, **kwargs)

    return _wrapped
