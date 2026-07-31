import json

import anthropic
import httpx
import pytest

from gigfinder import claude_enrich
from gigfinder.claude_enrich import EnrichmentError

LOC = {"name": "Weinbar Rot", "kategorie_label": "Weinbars", "plz": "8400",
       "ort": "Winterthur", "scrape_text": "Kleine Weinbar mit Innenhof."}


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text, stop_reason="end_turn"):
        self.content = [_Block(text)]
        self.stop_reason = stop_reason


class _FakeMessages:
    def __init__(self, antwort=None, fehler=None):
        self.antwort = antwort
        self.fehler = fehler
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fehler is not None:
            raise self.fehler
        return self.antwort


class _FakeClient:
    def __init__(self, messages):
        self.messages = messages


def _install(monkeypatch, messages, model="claude-opus-5"):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("CLAUDE_MODEL", model)
    monkeypatch.setattr(claude_enrich, "_client", lambda: _FakeClient(messages))
    return messages


def _api_error(cls, status):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status, request=request, json={
        "type": "error", "error": {"type": "invalid_request_error", "message": "kaputt"}})
    return cls("kaputt", response=response, body=None)


def test_supports_effort():
    assert claude_enrich._supports_effort("claude-opus-5")
    assert claude_enrich._supports_effort("claude-sonnet-5")
    assert not claude_enrich._supports_effort("claude-haiku-4-5")
    assert not claude_enrich._supports_effort("claude-3-haiku-20240307")


def test_effort_weggelassen_bei_haiku(monkeypatch):
    payload = json.dumps({"beschreibung": "Test.", "eignung": 3,
                          "email": "", "kontakt_name": ""})
    msgs = _install(monkeypatch, _FakeMessages(antwort=_Response(payload)),
                    model="claude-haiku-4-5")
    assert claude_enrich.enrich(LOC)["eignung"] == 3
    assert "effort" not in msgs.calls[0]["output_config"]


def test_effort_gesetzt_bei_opus(monkeypatch):
    payload = json.dumps({"beschreibung": "Test.", "eignung": 3,
                          "email": "", "kontakt_name": ""})
    msgs = _install(monkeypatch, _FakeMessages(antwort=_Response(payload)))
    claude_enrich.enrich(LOC)
    assert msgs.calls[0]["output_config"]["effort"] == "low"


def test_falscher_key_gibt_klare_meldung(monkeypatch):
    _install(monkeypatch, _FakeMessages(
        fehler=_api_error(anthropic.AuthenticationError, 401)))
    with pytest.raises(EnrichmentError, match="API-Key wurde abgelehnt"):
        claude_enrich.enrich(LOC)


def test_unbekanntes_modell_gibt_klare_meldung(monkeypatch):
    _install(monkeypatch, _FakeMessages(fehler=_api_error(anthropic.NotFoundError, 404)),
             model="claude-gibts-nicht")
    with pytest.raises(EnrichmentError, match="gibt es nicht"):
        claude_enrich.enrich(LOC)


def test_ratelimit_gibt_klare_meldung(monkeypatch):
    _install(monkeypatch, _FakeMessages(fehler=_api_error(anthropic.RateLimitError, 429)))
    with pytest.raises(EnrichmentError, match="Limit erreicht"):
        claude_enrich.enrich(LOC)


def test_abgeschnittene_antwort_wird_gemeldet(monkeypatch):
    _install(monkeypatch, _FakeMessages(
        antwort=_Response('{"beschreibung": "abgeschn', stop_reason="max_tokens")))
    with pytest.raises(EnrichmentError, match="unvollständig"):
        claude_enrich.enrich(LOC)


def test_kaputtes_json_wird_gemeldet(monkeypatch):
    _install(monkeypatch, _FakeMessages(antwort=_Response("kein json")))
    with pytest.raises(EnrichmentError, match="kein gültiges JSON"):
        claude_enrich.enrich(LOC)


def test_ohne_website_text_kein_aufruf(monkeypatch):
    msgs = _install(monkeypatch, _FakeMessages(antwort=_Response("{}")))
    assert claude_enrich.enrich({"name": "X", "scrape_text": ""}) is None
    assert msgs.calls == []
