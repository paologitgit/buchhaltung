from bs4 import BeautifulSoup

from gigfinder.scrape import _extract_emails, _rank_email, _NAME_RE, _PHONE_RE


def _emails(html: str) -> list[str]:
    return _extract_emails(html, BeautifulSoup(html, "html.parser"))


def test_mailto_and_plain_email():
    html = '<a href="mailto:info@weinbar.ch?subject=x">Mail</a> oder reservation@weinbar.ch'
    assert set(_emails(html)) == {"info@weinbar.ch", "reservation@weinbar.ch"}


def test_obfuscated_email():
    html = "<p>Schreib uns: info (at) kulturhaus.ch</p>"
    assert "info@kulturhaus.ch" in _emails(html)


def test_junk_emails_filtered():
    html = "logo@2x.png bild@example.com echt@bar.ch"
    assert _emails(html) == ["echt@bar.ch"]


def test_rank_prefers_own_domain():
    ranked = _rank_email(["hans@gmail.com", "info@weinbar.ch"], "weinbar.ch")
    assert ranked == "info@weinbar.ch"


def test_contact_name_pattern():
    m = _NAME_RE.search("Inhaberin: Maria Müller-Steiner, seit 2004")
    assert m and m.group(1) == "Maria Müller-Steiner"
    m = _NAME_RE.search("Geschäftsführer Hans Peter Weber")
    assert m and m.group(1) == "Hans Peter Weber"


def test_swiss_phone_pattern():
    assert _PHONE_RE.search("Tel. +41 44 123 45 67")
    assert _PHONE_RE.search("052 213 44 55")
