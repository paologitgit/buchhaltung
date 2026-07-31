"""Optionale Anreicherung über die Claude API.

Wenn ANTHROPIC_API_KEY gesetzt ist, liest Claude den Website-Auszug jeder
Location und liefert eine Kurzbeschreibung, eine Eignungs-Einschätzung für
Akustik-Auftritte (Gitarre/Gesang) und – falls im Text erkennbar – E-Mail
und Ansprechpartner, die der Scraper übersehen hat.
"""
import json
import logging
import os

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5"

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


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _client():
    import anthropic
    return anthropic.Anthropic()


def enrich(location: dict) -> dict | None:
    """Liefert {"beschreibung", "eignung", "email", "kontakt_name"} oder None."""
    if not available():
        return None
    text = (location.get("scrape_text") or "").strip()
    if not text:
        return None

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
        response = client.messages.create(
            model=os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL),
            max_tokens=8000,
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": _SCHEMA},
            },
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason == "refusal":
            return None
        raw = next((b.text for b in response.content if b.type == "text"), None)
        if not raw:
            return None
        return json.loads(raw)
    except anthropic.APIError as exc:
        log.warning("Claude-Anreicherung für %s fehlgeschlagen: %s",
                    location.get("name"), exc)
        return None
    except (json.JSONDecodeError, StopIteration) as exc:
        log.warning("Claude-Antwort unlesbar für %s: %s", location.get("name"), exc)
        return None
