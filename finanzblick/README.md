# Finanzblick

Ein Offline-Werkzeug, das CSV-Auszüge der Bank auswertet und die eigene
Finanzentwicklung sichtbar macht. Es läuft vollständig im Browser: kein Server,
keine Installation, keine Netzwerkaufrufe. Die Kontodaten verlassen den Rechner
nicht.

## Starten

Zwei Wege, beide ohne Installation:

**Direkt aus der Datei.** `finanzblick/index.html` im Browser öffnen – per
Doppelklick oder über „Datei öffnen". Reicht für den Alltag völlig aus.

**Über localhost.** Im Ordner `finanzblick/`:

```sh
./start.sh          # macOS, Linux
start.cmd           # Windows (auch per Doppelklick)
```

Das öffnet <http://localhost:8765/index.html> im Browser. Port 8765 ist bewusst
gewählt: Port 8000 gehört der Buchhaltungs-App in diesem Repository, 80 und 443
dem nginx davor. Ein anderer Port geht als Argument: `./start.sh 9000`.

Der Server hört nur auf `127.0.0.1`, ist also ausschliesslich von diesem Rechner
erreichbar und nicht aus dem übrigen Netzwerk. Beenden mit `Strg+C`. Gebraucht
wird nur Python, das auf macOS und Linux ohnehin vorhanden ist – ohne Python
bleibt der Weg über die Datei.

Der ganze Ordner lässt sich auf einen USB-Stick kopieren und auf einem Rechner
ohne Internetverbindung benutzen.

Zum Ausprobieren ohne eigene Daten: **Beispieldaten laden** erzeugt zwei Jahre
plausibler Buchungen.

## Was es zeigt

| Ansicht | Frage, die sie beantwortet |
| --- | --- |
| Kennzahlen | Wie viel bleibt übrig? Wie hoch sind Einnahmen, Ausgaben, Sparquote? |
| Saldoverlauf | Wächst oder schrumpft das Vermögen über die Zeit? |
| Einnahmen und Ausgaben pro Monat | In welchen Monaten lief es aus dem Ruder? |
| Monatssaldo | Welche Monate waren im Plus, welche im Minus? |
| Ausgaben nach Kategorie | Wohin fliesst das Geld? |
| Wiederkehrende Zahlungen | Welche Fixkosten laufen jeden Monat weiter? |
| Grösste Empfänger | Wer bekommt am meisten? |
| Buchungen | Die Einzelbelege, durchsuchbar und filterbar |

Jedes Diagramm hat eine Schaltfläche **Tabelle** – dieselben Werte als Text,
ohne Mauszeiger erreichbar.

## CSV-Formate

Das Tool rät Kodierung, Trennzeichen, Kopfzeile, Spalten sowie Datums- und
Zahlenformat selbst. Getestet mit:

- Schweizer Auszügen mit Vorspann, Semikolon, `Belastung`/`Gutschrift` und
  Apostroph-Zahlen (`1'650.00`)
- deutschen Exporten mit `1.234,56` und einer einzelnen `Betrag`-Spalte
- englischen Exporten (`2025-01-05`, Komma-Trennzeichen, `-12.99`)
- Tabulator-Dateien, nachgestelltem Minus (`85.40-`) und Dateien ganz ohne
  Kopfzeile

Windows-1252 wird automatisch erkannt, wenn die Datei kein gültiges UTF-8 ist.

Wenn die Erkennung danebenliegt, lässt sich unter jeder geladenen Datei jede
Spalte von Hand zuordnen, der Kontoname setzen und das Vorzeichen umkehren
(für Banken, die Ausgaben positiv ausweisen).

## Weitere Dateien nachladen

Ein späterer Import ersetzt nichts: neue Dateien kommen zu den bereits geladenen
dazu, egal ob sie neuere oder ältere Zeiträume enthalten. Der Zeitraum der
Auswertung wächst entsprechend mit.

Damit überlappende Exporte keine Buchung doppelt zählen, müssen beide Dateien
demselben Konto zugeordnet sein. Der Kontoname wird deshalb aus der **IBAN in
der Datei** abgeleitet (`Konto ••5295`) – die bleibt über alle Exporte gleich.
Fehlt eine IBAN, dient der Dateiname ohne Zeitraumangaben als Name, sodass aus
`Auszug_2024.csv` und `Auszug_2025.csv` ein Konto wird. Notfalls lässt sich der
Kontoname bei jeder Datei von Hand setzen; zwei Dateien mit demselben
Kontonamen gehören zusammen.

Innerhalb eines Kontos gilt eine Buchung als Dublette, wenn Datum, Betrag und
Text übereinstimmen. Nach jedem Import steht in der Meldung, wie viele Buchungen
schon bekannt waren.

## Kategorien

Die Zuordnung erfolgt über Stichwortregeln, erste passende Regel gewinnt. Rund
190 Regeln für den DACH-Raum sind vorbereitet (Migros, Coop, SBB, Krankenkassen,
Abos, Steuern …).

**So trifft ein Stichwort.** Es muss am Wortanfang stehen – sonst würde „otto"
auch *Ris**otto*** treffen und „kurs" auch *Kon**kurs**amt*. Kurze Stichwörter
bis vier Zeichen müssen zusätzlich am Wortende aufhören: „spar" trifft den
Supermarkt SPAR, nicht das Sparkonto; „bar" die Bar, nicht den Bargeldbezug.
Wer die Suche im ganzen Wort braucht, stellt einen Stern voran: `*otto`.
Gross- und Kleinschreibung sowie Umlaute spielen keine Rolle – „gebühr" trifft
auch `GEBUEHR`.

**Aufräumen in vier Schritten.** Der Filter **Zuordnung → Nur nicht zugeordnete**
zeigt alle Buchungen, auf die keine Regel passt (ihre Zahl steht auch unter der
Filterzeile). Bei jeder Buchung führt die Schaltfläche **Regel** den
Buchungstext ins Regelformular, wo nur noch die Kategorie zu wählen ist. Die
Spalte **Treffer** in der Regeltabelle zeigt, wie viele Buchungen jede Regel
einsammelt – eine Regel mit auffällig vielen Treffern greift meist zu weit. Ein
Zeigen auf die Kategorie in der Buchungstabelle verrät, welche Regel sie gesetzt
hat.

- Einzelne Buchung ändern: Kategorie direkt in der Buchungstabelle wählen. Die
  Zuweisung überschreibt alle Regeln und bleibt erhalten.
- Regel ergänzen: Stichwort und Kategorie im Abschnitt **Kategorie-Regeln**
  eintragen. Neue Regeln stehen zuoberst und gewinnen damit gegen die
  Standardregeln.
- Reihenfolge zählt: mit ▲ rutscht eine Regel nach oben.
- Regeln und manuelle Zuweisungen lassen sich als JSON sichern und wieder laden.

## Daten im Browser behalten

Standardmässig liegen die Buchungen nur im Arbeitsspeicher und sind nach dem
Schliessen weg. Wer sie behalten will, aktiviert **Buchungen im Browser
speichern**; sie landen dann im lokalen Speicher des Browsers (localStorage) –
weiterhin nur auf diesem Rechner. Das Häkchen wieder zu entfernen löscht sie.

Regeln und manuelle Zuweisungen werden unabhängig davon immer lokal gespeichert.

## Aufbau

| Datei | Inhalt |
| --- | --- |
| `index.html` | Seitengerüst |
| `styles.css` | Gestaltung, Hell- und Dunkelmodus |
| `parser.js` | CSV-Erkennung: Kodierung, Trennzeichen, Kopfzeile, Spalten, Datums- und Betragsformate |
| `categories.js` | Kategorien, Regelwerk, Erkennung wiederkehrender Zahlungen |
| `charts.js` | Diagramme als handgezeichnetes SVG, ohne Bibliothek |
| `app.js` | Zustand, Filter, Kennzahlen, Tabellen, Import und Export |
| `start.sh` / `start.cmd` | Startet den lokalen Server auf Port 8765 |

Kein Build-Schritt, keine Abhängigkeiten. Änderungen an den Dateien wirken nach
einem Neuladen der Seite.

## Verhältnis zur Buchhaltungs-App

Finanzblick ist bewusst eigenständig und unabhängig von der Django-Anwendung in
diesem Repository: keine Datenbank, keine Anmeldung, kein Docker. Es dient dem
Verstehen der eigenen Zahlen, nicht der Buchführung. Die Spaltenerkennung greift
dieselben Formate auf, die auch der CSV-Import unter `bank/services.py`
verarbeitet.
