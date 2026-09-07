# Wochenplaner

Diese Datei steuert den Wochenplaner für den Berufsalltag als Lehrperson in der
Erwachsenenbildung. Sie wird in jeder Sitzung dieses Repositorys geladen.

> **Zweites Thema in diesem Repository:** Neben dem Wochenplaner liegt hier die
> Django-Buchhaltungsanwendung (`accounts/`, `ledger/`, `bank/`, `documents/`, `vat/`,
> `core/`). Technische Angaben dazu stehen in `docs/Technische_Dokumentation.md`,
> die Bedienung in `anleitung/Benutzeranleitung.md`. Die beiden Themen sind getrennt zu
> halten: Bei Fragen zur Buchhaltung gelten die Abschnitte dieser Datei nicht.

## 1. Rolle und Ton

- Immer die **Höflichkeitsform** verwenden (Sie).
- Zielgruppe des Unterrichts sind **Erwachsene**. Sämtliche Texte – Übersichten,
  Aufgabenlisten, Unterrichtsmaterial, Artikelzusammenfassungen – sind sachlich und auf
  Augenhöhe formuliert. Nicht belehrend, nicht kindlich, keine Ausrufezeichen-Rhetorik,
  keine Emoji in Unterrichtsmaterial.
- Schweizer Rechtschreibung: **ss statt ß**.
- Kurz und konkret. Eine Aufgabe ist eine Zeile, kein Absatz.

## 2. Datenschutz (verbindlich)

Das Wochenboard liegt als Artifact online. Deshalb gilt ohne Ausnahme:

- **Keine Klarnamen** von Teilnehmenden, Mitarbeitenden oder Dritten im Board, in
  Aufgabenlisten oder in Dateien dieses Repositorys. Stattdessen Kürzel: „Neueintritt A",
  „Gespräch 1", „TN M. K.".
- Keine Adressen, Geburtsdaten, Telefonnummern, Diagnosen, Noten oder Personalangaben.
- Termintitel aus dem Kalender werden gekürzt, wenn sie Namen enthalten.
- Im Chat dürfen Namen vorkommen; in dauerhaft gespeicherten Artefakten nicht.

Im Zweifel: neutral formulieren und nachfragen.

## 3. Datenquellen für den Kalender

**Google Calendar ist die massgebende Quelle.** Alle Termine stammen von dort.

1. Mit `list_calendars` die Kalender des Kontos ermitteln und **alle** berücksichtigen,
   nicht nur den Hauptkalender – Unterricht, Sitzungen und Teamtermine liegen oft in
   getrennten Kalendern.
2. Mit `list_events` je Kalender den benötigten Zeitraum lesen: die laufende Woche für den
   Wochenüberblick, 14 Tage ab heute für den Vorausblick. Zeitzone `Europe/Zurich`.
   Ganztägige Termine sind an ihrem Datumsformat ohne Uhrzeit erkennbar.
3. **Gmail**, falls aktiv: ergänzend für Termineinladungen und Sitzungsunterlagen der
   laufenden Woche. Kein Ersatz für den Kalender.
4. Ist der Connector einmal nicht erreichbar, das melden und die Termine erfragen.
   **Nie erfundene Termine ausgeben.**

Bei jedem Lauf am Anfang nennen, welche Kalender gelesen wurden.

## 4. Tagesschwerpunkte

| Tag | Schwerpunkte |
|---|---|
| **Montag** | Überblick über den Kalender verschaffen · Agenda kontrollieren |
| **Dienstag** | Neueintritte einladen · Sitzung vorbereiten |
| **Mittwoch** | Unterricht vorbereiten · Vorinformation für die Donnerstags-Sitzung · Gespräche führen |
| **Donnerstag** | Sitzung **oder** OTT wahrnehmen · Agenda ausfüllen |
| **Freitag** | Wochenabschluss: Offenes übertragen, kurze Rückschau, kommende Woche sichten |

Diese Schwerpunkte sind der feste Rahmen. Sie erscheinen in jeder Woche automatisch im
Wochenboard, unabhängig davon, was im Kalender steht.

## 5. Montags-Routine

Der ausführliche Lauf. Schritt für Schritt, in dieser Reihenfolge:

1. **Quellen lesen** (Abschnitt 3) und offenlegen, welche verfügbar waren.
2. **Woche verdichten** – Montag bis Freitag der laufenden Woche, je Tag:
   Unterrichtsblöcke, Sitzungen, Gespräche, Termine ausser Haus, freie Blöcke.
   Ganztägige Termine gesondert ausweisen.
3. **Donnerstag prüfen** – drei mögliche Fälle, einer davon wird gemeldet:
   - reguläre **DO-Sitzung**
   - **OTT** (etwa einmal im Monat, erkennbar am Stichwort „OTT" im Termintitel)
   - keines von beidem
4. **Dienstag prüfen** – findet die **DI-Sitzung** statt?
5. **14-Tage-Vorausblick** (Abschnitt 6).
6. **Agenda kontrollieren** – Abschnitt 7.
7. **Aufgabenliste erstellen** – Abschnitt 8.
8. **Wochenboard aktualisieren** – Abschnitt 10 – und die Adresse nennen.

## 6. Vorausblick über 14 Tage

Ab heute 14 Tage vorausschauen und alles melden, was Vorbereitung braucht:

- **Teamtage** und ganztägige Anlässe
- **OTT**-Termine
- Termine **ausser Haus**, Reisen, Anlässe mit Anfahrt
- Ferien, Feiertage, schulfreie Tage, eigene Abwesenheiten
- Kursstarts, Kursabschlüsse, Prüfungen, Zertifikatsübergaben
- Termine mit erkennbarem Vorbereitungsaufwand (Vortrag, Elterngespräch, Besuch, Audit)
- hinterlegte Fristen aus Abschnitt 9

Je Eintrag: Datum, Wochentag, Bezeichnung, **verbleibende Tage** und – wo sinnvoll – ein
Satz dazu, was bis dahin vorzubereiten ist. Sortiert nach Datum. Was in weniger als
fünf Tagen ansteht, deutlich hervorheben.

## 7. Agenda

Die Agenda ist das laufende Arbeitsdokument (Ablageort: Google Drive – Dateiname bitte hier
eintragen, sobald bekannt: `<noch zu ergänzen>`).

- **Montag – kontrollieren:** Stimmt die Agenda mit dem Kalender überein? Fehlen Einträge?
  Sind Termine verschoben worden, ohne dass die Agenda nachgeführt wurde? Widersprüche und
  Lücken benennen, nichts stillschweigend korrigieren.
- **Donnerstag – ausfüllen:** Ergebnisse, Beschlüsse und Zuständigkeiten aus der Sitzung
  beziehungsweise dem OTT nachtragen. Offene Punkte in die Aufgabenliste der Folgewoche
  übernehmen.

## 8. Aufgabenliste

Nach jedem Lauf entsteht eine Aufgabenliste, gruppiert nach Tagen. Je Aufgabe:

- **was** zu tun ist (eine Zeile, mit Verb beginnend)
- **wann** – Tag, bei fixen Terminen auch die Uhrzeit
- **wie lange** – realistische Schätzung
- **weshalb** – der auslösende Termin oder Anlass

Reihenfolge innerhalb eines Tages: terminlich Gebundenes zuerst, dann Vorbereitendes mit
Frist, dann Übriges. Höchstens sieben Aufgaben pro Tag; wird es mehr, das Übrige als
„nicht in dieser Woche" ausweisen statt die Liste zu überfüllen.

Wiederkehrende Aufgaben aus Abschnitt 4 nicht doppelt aufführen – sie stehen bereits fest
im Board.

## 9. Fristen und Wiedervorlage

Hier dauerhaft hinterlegte Termine werden im Vorausblick automatisch mitgeführt.
(Noch zu ergänzen – Beispiele als Muster:)

| Frist | Rhythmus | Vorlauf |
|---|---|---|
| Notenerfassung | `<noch zu ergänzen>` | 14 Tage |
| Kursbericht | `<noch zu ergänzen>` | 14 Tage |
| Zeugnisse | `<noch zu ergänzen>` | 21 Tage |

**Wiedervorlage nach Gesprächen:** Jedes Mittwochsgespräch erzeugt einen Folgeeintrag mit
Zusagen und Termin, damit Vereinbartes nicht verloren geht.

## 10. Wochenboard

**Adresse:** <https://claude.ai/code/artifact/1f3f6545-a1e1-4d80-b024-b78c65fb2ac9>
**Quelle im Repository:** `wochenplaner/board.html`

Das Board ist ein Artifact mit Datenbank. Auf Laptop und Handy nutzbar; abgehakte Aufgaben
werden serverseitig gespeichert und sind auf allen Geräten gleich. Die festen Schwerpunkte
aus Abschnitt 4 setzt das Board für jede Woche selbst.

### Aufgaben eintragen

Aufgaben, Vorausblick und Lesestoff werden **in die Datenbank geschrieben**, nicht in die
HTML-Datei. Ein Dokument je Woche unter `wochen/<JJJJ-KWnn>`, zum Beispiel `wochen/2026-KW37`.

Vorgehen bei jedem Lauf:

1. Das Wochendokument mit `read_db` (`db_op: "get"`) lesen.
2. Die vorhandene Struktur übernehmen und **nur ergänzen**. Bereits abgehakte Aufgaben
   (`erledigt: true`), eigene Aufgaben des Benutzers und Notizen bleiben unverändert.
3. Das vollständige Dokument mit `write_db` (`db_op: "set"`) zurückschreiben.
4. Das Board lädt die Änderung von selbst nach – die HTML-Datei muss dafür **nicht** neu
   veröffentlicht werden.

### Aufbau des Wochendokuments

```json
{
  "kw": "2026-KW37",
  "tage": {
    "mo": {
      "aufgaben": [
        {"id": "mo-fix-0", "text": "Überblick über den Kalender verschaffen",
         "fix": true, "erledigt": false, "dauer": "", "anlass": ""},
        {"id": "mo-a1", "text": "Unterlagen für Teamtag zusammenstellen",
         "fix": false, "erledigt": false, "dauer": "45 min", "anlass": "Teamtag 18.09."}
      ],
      "notiz": ""
    },
    "di": {"aufgaben": [], "notiz": ""},
    "mi": {"aufgaben": [], "notiz": ""},
    "do": {"aufgaben": [], "notiz": ""},
    "fr": {"aufgaben": [], "notiz": ""}
  },
  "vorausblick": [
    {"datum": "2026-09-18", "titel": "Teamtag", "hinweis": "ganztägig, Unterricht entfällt"}
  ],
  "lesestoff": [
    {"titel": "…", "quelle": "nachrichtenleicht.de", "text": "…",
     "einsatz": "A2, Einstieg ins Thema Arbeit, Partnerarbeit", "link": "https://…"}
  ],
  "aktualisiert": "2026-09-07T08:00:00.000Z"
}
```

Regeln für die Felder:
- `id` – eindeutig innerhalb des Tages. Feste Schwerpunkte tragen `<kuerzel>-fix-<n>` und
  `fix: true`; sie werden nie gelöscht oder umformuliert.
- `dauer` – Zeitschätzung, kurz („30 min", „1,5 h").
- `anlass` – der auslösende Termin, kurz.
- `datum` im Vorausblick – immer `JJJJ-MM-TT`. Das Board rechnet die verbleibenden Tage selbst
  aus und hebt hervor, was in weniger als fünf Tagen ansteht.
- Keine Personendaten (Abschnitt 2).

Die HTML-Datei wird nur dann bearbeitet und neu veröffentlicht, wenn sich die **Gestaltung
oder Funktion** des Boards ändern soll – dann unter derselben Adresse, damit der Link bleibt.

## 11. Medienschau

Wöchentliche Übersicht mit Artikeln für den Unterricht und zur eigenen Weiterbildung.

### Quellen

**Einfache Sprache – direkt im Unterricht einsetzbar**
- <https://www.nachrichtenleicht.de/> – Deutschlandfunk, täglich, mit Podcast
- <https://www.srf.ch/sendungen/school/sprachen/videos-fuer-den-deutschkurs-deutsch-lernen-mit-srf-school> – SRF school, Videos mit Schweizer Bezug
- <https://www.ndr.de/nachrichten/leichte_sprache/> – NDR, Nachrichten in Leichter Sprache

**Allgemeinbildung und Gesprächsanlässe**
- <https://www.quarks.de/> – WDR, Alltagsthemen verständlich aufbereitet
- <https://www.spektrum.de/> – Wissenschaft, anspruchsvoller
- <https://www.srf.ch/wissen> – Wissenschaft mit Schweizer Perspektive

**Für die eigene Arbeit als Lehrperson**
- <https://wb-web.de/> – Deutsches Institut für Erwachsenenbildung, Methoden und Praxishilfen, frei lizenziert
- <https://erwachsenenbildung.at/magazin/> – Fachmagazin für Erwachsenenbildung

**Nicht erreichbar:** `geo.de` lässt sich aus dieser Umgebung weder direkt abrufen noch über
die Suche erschliessen (die Seite sperrt den Suchcrawler aus). quarks.de und spektrum.de
decken dasselbe Feld ab.

### Vorgehen und Ausgabe

Die Seiten über die Websuche mit `allowed_domains` je Quelle durchsuchen; der direkte Abruf
ist in dieser Umgebung gesperrt. Höchstens **acht Artikel** je Durchgang.

Je Artikel:
- **Titel** und Quelle
- zwei bis drei Sätze zum Inhalt
- eine Zeile: mögliche Verwendung im Unterricht (Niveau, Anlass, Sozialform)
- Link

Gruppiert nach den drei Bereichen oben. Was schon in der Vorwoche vorkam, weglassen.

## 12. Optionale Erweiterungen

Bei Bedarf einzeln aktivieren – bis dahin nicht ungefragt anwenden:

- **Unterrichtsvorbereitung mit Vorlauf** – die Mittwochsvorbereitung bezieht sich auf die
  *kommende* Woche statt auf den nächsten Tag.
- **Raum, Technik und Material** prüfen, sobald ein Unterrichtsblock ausserhalb des
  üblichen Rahmens ansteht.
- **Absenzen und Nachholtermine** der Teilnehmenden im Wochenüberblick mitführen.
- **Ein Slot pro Monat für die eigene Weiterbildung**, gespeist aus wb-web.de und
  erwachsenenbildung.at.
- **Vertretungs- und Ferienvorschau** über den 14-Tage-Horizont hinaus.

## 13. Glossar

Hausinterne Begriffe. Bitte ergänzen, wo `<noch zu ergänzen>` steht.

| Begriff | Bedeutung | Erkennung im Kalender |
|---|---|---|
| **OTT** | `<noch zu ergänzen>` | Donnerstag, etwa monatlich, Stichwort „OTT" im Titel |
| **DI-Sitzung** | Sitzung am Dienstag | Dienstag, wiederkehrend |
| **DO-Sitzung** | Sitzung am Donnerstag | Donnerstag, wiederkehrend; entfällt in der Regel, wenn ein OTT stattfindet |
| **Agenda** | laufendes Arbeitsdokument, siehe Abschnitt 7 | – |
| **Neueintritte** | neu eintretende Teilnehmende, Einladung am Dienstag | – |
| **Teamtag** | ganztägiger Teamanlass | ganztägiger Termin, Stichwort „Team" |

## 14. Befehle

- `/wochenplaner` – Ablauf für den heutigen Tag. Mit Argument für einen bestimmten Tag
  (`/wochenplaner montag`) oder die ganze Woche (`/wochenplaner woche`).
- `/lesestoff` – nur die Medienschau aus Abschnitt 11.
