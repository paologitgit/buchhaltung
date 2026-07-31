"""Optionale Anreicherung über die Claude API.

Wenn ANTHROPIC_API_KEY gesetzt ist, liest Claude den Website-Auszug jeder
Location und liefert eine Kurzbeschreibung, eine Eignungs-Einschätzung für
Akustik-Auftritte (Gitarre/Gesang) und – falls im Text erkennbar – E-Mail
und Ansprechpartner, die der Scraper übersehen hat.

Fehler werden als EnrichmentError gemeldet, damit die Oberfläche sagen
kann, *warum* keine Beschreibungen entstanden sind, statt sie kommentarlos
wegzulassen.
"""
import json
import logging
import os

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5"

# Modelle ohne Unterstützung für output_config.effort – dort würde der
# Parameter die Anfrage mit einem 400er scheitern lassen.
_NO_EFFORT_PREFIXES = ("claude-haiku-4-5", "claude-haiku-3", "claude-sonnet-4-5",
                       "claude-3-", "claude-2")

_SCHEMA = {
    "type": "object",
    "properties": {
        "beschreibung": {
            "type": "string",
            "description": "Zwei kurze Sätze auf Deutsch über die Location.",
        },
        "eignung": {
            "type": "integer",
            "enum": [1, 2, 3, 4, 5],
            "description": "Eignung für Akustik-Livemusik (Solo Gitarre/Gesang): "
                           "1=ungeeignet, 5=ideal.",
        },
        "email": {"type": "string", "description": "Kontakt-E-Mail aus dem Text, sonst leer."},
        "kontakt_name": {
            "type": "string",
            "description": "Name der Kontaktperson aus dem Text, sonst leer.",
        },
    },
    "required": ["beschreibung", "eignung", "email", "kontakt_name"],
    "additionalProperties": False,
}


class EnrichmentError(Exception):
    """Die Anreicherung einer Location ist fehlgeschlagen."""


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def model_name() -> str:
    return os.environ.get("CLAUDE_MODEL") or DEFAULT_MODEL


def _supports_effort(model: str) -> bool:
    return not any(model.startswith(prefix) for prefix in _NO_EFFORT_PREFIXES)


def _client():
    import anthropic
    return anthropic.Anthropic()


def _request(client, model: str, prompt: str, mit_effort: bool):
    output_config = {"format": {"type": "json_schema", "schema": _SCHEMA}}
    if mit_effort:
        output_config["effort"] = "low"
    return client.messages.create(
        model=model,
        max_tokens=16000,
        output_config=output_config,
        messages=[{"role": "user", "content": prompt}],
    )


def enrich(location: dict) -> dict | None:
    """Liefert {"beschreibung", "eignung", "email", "kontakt_name"}.

    None, wenn es für diese Location nichts zu lesen gab. Bei einem Fehler
    wird EnrichmentError mit einer verständlichen Meldung ausgelöst.
    """
    if not available():
        return None
    text = (location.get("scrape_text") or "").strip()
    if not text:
        return None

    model = model_name()
    prompt = (
        "Ein Musiker (Solo, Gitarre und Gesang, akustisch) sucht Auftrittsorte "
        "in der Schweiz. Hier die Daten einer möglichen Location und ein Auszug "
        "ihrer Website. Beurteile sie.\n\n"
        f"Name: {location.get('name', '')}\n"
        f"Kategorie: {location.get('kategorie_label', location.get('kategorie', ''))}\n"
        f"Ort: {location.get('plz', '')} {location.get('ort', '')}\n\n"
        f"Website-Auszug:\n{text[:4000]}"
    )

    import anthropic
    try:
        client = _client()
    except Exception as exc:
        raise EnrichmentError(f"Claude-Zugang nicht nutzbar: {exc}") from exc

    mit_effort = _supports_effort(model)
    try:
        try:
            response = _request(client, model, prompt, mit_effort)
        except anthropic.BadRequestError as exc:
            # Manche Modelle akzeptieren output_config.effort nicht – einmal ohne
            # versuchen, bevor wir aufgeben.
            if not mit_effort or "effort" not in str(exc).lower():
                raise
            log.info("Modell %s akzeptiert kein effort – erneuter Versuch ohne.", model)
            response = _request(client, model, prompt, False)
    except anthropic.AuthenticationError as exc:
        raise EnrichmentError(
            f"Claude-API-Key wurde abgelehnt ({exc.status_code}). "
            "Bitte ANTHROPIC_API_KEY in der .env prüfen.") from exc
    except anthropic.PermissionDeniedError as exc:
        raise EnrichmentError(
            f"Claude-API-Key hat keinen Zugriff auf das Modell «{model}» "
            f"({exc.status_code}).") from exc
    except anthropic.NotFoundError as exc:
        raise EnrichmentError(
            f"Das Modell «{model}» gibt es nicht. Bitte CLAUDE_MODEL in der "
            ".env prüfen.") from exc
    except anthropic.RateLimitError as exc:
        raise EnrichmentError(
            "Claude-API-Limit erreicht – bitte später nochmals versuchen.") from exc
    except anthropic.BadRequestError as exc:
        raise EnrichmentError(
            f"Claude hat die Anfrage abgelehnt: {exc.message}") from exc
    except anthropic.APIStatusError as exc:
        raise EnrichmentError(
            f"Claude-API meldet einen Fehler ({exc.status_code}).") from exc
    except anthropic.APIConnectionError as exc:
        raise EnrichmentError(
            "Claude-API nicht erreichbar – Netzwerkverbindung prüfen.") from exc

    if response.stop_reason == "refusal":
        raise EnrichmentError("Claude hat die Beurteilung dieser Website abgelehnt.")
    if response.stop_reason == "max_tokens":
        raise EnrichmentError("Claude-Antwort war unvollständig (max_tokens erreicht).")

    raw = next((b.text for b in response.content if b.type == "text"), None)
    if not raw:
        raise EnrichmentError("Claude hat eine leere Antwort geliefert.")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EnrichmentError(f"Claude-Antwort war kein gültiges JSON: {exc}") from exc


def check_access() -> str | None:
    """Prüft den Zugang mit einer minimalen Anfrage.

    Liefert None wenn alles passt, sonst eine Fehlermeldung im Klartext.
    So merkt man Konfigurationsfehler sofort und nicht erst, wenn alle
    Beschreibungen fehlen.
    """
    if not available():
        return "Kein ANTHROPIC_API_KEY gesetzt."
    probe = {"name": "Test", "kategorie_label": "Test", "plz": "", "ort": "",
             "scrape_text": "Eine kleine Bar mit Platz für Livemusik."}
    try:
        enrich(probe)
    except EnrichmentError as exc:
        return str(exc)
    return None
