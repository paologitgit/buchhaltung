"""Besucht die Website einer Location und extrahiert E-Mail, Telefon und
Ansprechpartner – aus der Startseite plus Kontakt-/Impressumsseite."""
import logging
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

MAX_BYTES = 1_500_000
TIMEOUT = (6, 12)
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 gig-finder/1.0"),
    "Accept-Language": "de-CH,de;q=0.9,en;q=0.5",
}

# E-Mail-Regex inkl. gängiger Verschleierungen: info(at)domain.ch, info [at] domain [dot] ch
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_OBFUSCATED_RE = re.compile(
    r"([a-zA-Z0-9._%+\-]+)\s*[\(\[\{]\s*at\s*[\)\]\}]\s*([a-zA-Z0-9.\-]+)"
    r"\s*(?:[\(\[\{]\s*(?:dot|punkt)\s*[\)\]\}]\s*([a-zA-Z]{2,}))?",
    re.IGNORECASE,
)
_BAD_EMAIL_PARTS = ("example.", "sentry.", "wixpress.", ".png", ".jpg", ".gif",
                    ".svg", ".webp", "@2x", "your-email", "email@", "domain.")

_CONTACT_LINK_RE = re.compile(r"kontakt|impressum|contact|ueber-?uns|über-?uns|about|team",
                              re.IGNORECASE)

_NAME_RE = re.compile(
    r"(?:Inhaber(?:in)?|Geschäftsführ(?:er|erin|ung)|Betriebsleit(?:er|erin|ung)|"
    r"Gastgeber(?:in)?|Ansprechpartner(?:in)?|Verantwortlich(?:er)?|Leitung|Direktion|"
    r"Geschäftsleitung|Kontaktperson)\s*[:\-–]?\s*"
    r"((?:[A-ZÄÖÜÉ][a-zäöüéèàâ]+(?:-[A-ZÄÖÜÉ][a-zäöüéèàâ]+)?\s+){1,2}"
    r"[A-ZÄÖÜÉ][a-zäöüéèàâ]+(?:-[A-ZÄÖÜÉ][a-zäöüéèàâ]+)?)"
)

_PHONE_RE = re.compile(r"(?:\+41|0041|0)\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}")


def _fetch(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype and "text" not in ctype:
            return None
        content = resp.raw.read(MAX_BYTES, decode_content=True)
        return content.decode(resp.encoding or "utf-8", errors="replace")
    except (requests.RequestException, OSError) as exc:
        log.debug("Abruf %s fehlgeschlagen: %s", url, exc)
        return None


def _extract_emails(html: str, soup: BeautifulSoup) -> list[str]:
    found: list[str] = []
    for a in soup.select('a[href^="mailto:"]'):
        addr = a.get("href", "")[7:].split("?")[0].strip()
        if addr:
            found.append(addr)
    found.extend(_EMAIL_RE.findall(html))
    for m in _OBFUSCATED_RE.finditer(soup.get_text(" ")):
        local, domain, tld = m.group(1), m.group(2), m.group(3)
        if tld:
            found.append(f"{local}@{domain}.{tld}")
        elif "." in domain:
            found.append(f"{local}@{domain}")
    clean, seen = [], set()
    for e in found:
        e = e.strip().strip(".").lower()
        if not _EMAIL_RE.fullmatch(e):
            continue
        if any(bad in e for bad in _BAD_EMAIL_PARTS):
            continue
        if e not in seen:
            seen.add(e)
            clean.append(e)
    return clean


def _rank_email(emails: list[str], site_domain: str) -> str:
    """Bevorzugt Adressen der eigenen Domain, dann info@/kontakt@."""
    if not emails:
        return ""
    def score(e: str) -> tuple:
        domain_match = site_domain and e.endswith("@" + site_domain)
        generic = e.split("@")[0] in ("info", "kontakt", "mail", "hallo", "welcome",
                                      "reservation", "reservationen", "office", "event",
                                      "events", "willkommen")
        return (not domain_match, not generic)
    return sorted(emails, key=score)[0]


def _visible_text(soup: BeautifulSoup, limit: int = 4000) -> str:
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    return text[:limit]


def scrape(website: str) -> dict:
    """Liefert {"email", "telefon", "kontakt_name", "text"} von der Website.

    Fehlende Werte sind leere Strings; "text" ist ein Auszug des sichtbaren
    Inhalts (Startseite + Kontaktseite) für die spätere Claude-Anreicherung.
    """
    result = {"email": "", "telefon": "", "kontakt_name": "", "text": ""}
    if not website:
        return result
    if not website.startswith("http"):
        website = "https://" + website

    html = _fetch(website)
    if html is None:
        return result
    soup = BeautifulSoup(html, "html.parser")
    site_domain = urlparse(website).netloc.removeprefix("www.")

    pages = [(html, soup)]
    # Kontakt-/Impressums-Links derselben Domain nachladen (max. 2)
    seen_urls, extra = {website.rstrip("/")}, 0
    for a in soup.find_all("a", href=True):
        if extra >= 2:
            break
        if not (_CONTACT_LINK_RE.search(a["href"]) or _CONTACT_LINK_RE.search(a.get_text())):
            continue
        target = urljoin(website, a["href"]).split("#")[0].rstrip("/")
        if target in seen_urls or urlparse(target).netloc.removeprefix("www.") != site_domain:
            continue
        seen_urls.add(target)
        sub_html = _fetch(target)
        if sub_html:
            pages.append((sub_html, BeautifulSoup(sub_html, "html.parser")))
            extra += 1

    emails, texts = [], []
    for page_html, page_soup in pages:
        emails.extend(_extract_emails(page_html, page_soup))
        text = _visible_text(page_soup)
        texts.append(text)
        if not result["kontakt_name"]:
            m = _NAME_RE.search(text)
            if m:
                result["kontakt_name"] = m.group(1).strip()
        if not result["telefon"]:
            m = _PHONE_RE.search(text)
            if m:
                result["telefon"] = m.group(0).strip()

    result["email"] = _rank_email(list(dict.fromkeys(emails)), site_domain)
    result["text"] = " | ".join(texts)[:6000]
    return result
