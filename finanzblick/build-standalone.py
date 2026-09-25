#!/usr/bin/env python3
"""Baut aus den Einzeldateien eine einzige HTML-Datei.

Ergebnis ist "Finanzblick.html": CSS und JavaScript sind eingebettet, die Datei
braucht weder Server noch Nachbardateien. Doppelklick genügt – auch auf einem
Rechner ohne Internetverbindung oder von einem USB-Stick.

    python3 build-standalone.py

Nach Änderungen an index.html, styles.css oder den JS-Dateien neu ausführen,
sonst bleibt die Einzeldatei auf einem alten Stand stehen.
"""

import pathlib
import re
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE / "Finanzblick.html"

SCRIPTS = ["parser.js", "categories.js", "charts.js", "app.js"]


def read(name):
    return (HERE / name).read_text(encoding="utf-8")


def protect(code):
    """Ein "</script>" im Code würde den umschliessenden Block vorzeitig
    beenden – im JavaScript ist die maskierte Form gleichwertig."""
    return re.sub(r"</(script)", r"<\\/\1", code, flags=re.IGNORECASE)


def source_version():
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=HERE, capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", "."],
            cwd=HERE, capture_output=True, text=True, check=True,
        ).stdout.strip()
        return rev + (" (mit ungespeicherten Änderungen)" if dirty else "")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unbekannt"


def main():
    html = read("index.html")

    style = '<style>\n' + read("styles.css") + '</style>'
    html, count = re.subn(r'<link rel="stylesheet" href="styles\.css">', lambda _: style, html, count=1)
    if count != 1:
        raise SystemExit("Der Verweis auf styles.css wurde in index.html nicht gefunden.")

    for name in SCRIPTS:
        tag = '<script src="%s"></script>' % name
        if tag not in html:
            raise SystemExit("Der Verweis auf %s wurde in index.html nicht gefunden." % name)
        inline = "<script>\n" + protect(read(name)) + "</script>"
        html = html.replace(tag, inline, 1)

    banner = (
        "<!-- Finanzblick – erzeugt von build-standalone.py aus den Dateien des\n"
        "     Ordners finanzblick/ (Quellstand: %s).\n"
        "     Diese Datei nicht von Hand bearbeiten, sondern die Quelldateien\n"
        "     ändern und das Skript erneut ausführen. -->\n" % source_version()
    )
    html = html.replace("<!DOCTYPE html>", "<!DOCTYPE html>\n" + banner, 1)

    TARGET.write_text(html, encoding="utf-8")
    print("%s geschrieben (%.0f KB)" % (TARGET.name, TARGET.stat().st_size / 1024))


if __name__ == "__main__":
    main()
