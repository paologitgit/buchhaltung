---
description: Wochenüberblick, Terminprüfung, 14-Tage-Vorausblick und Aufgabenliste erstellen
argument-hint: [montag|dienstag|mittwoch|donnerstag|freitag|woche]
---

Führen Sie den Wochenplaner aus. Alle Regeln stehen in `CLAUDE.md` – lesen Sie diese Datei,
bevor Sie beginnen, und halten Sie sich an Ton (Abschnitt 1), Datenschutz (Abschnitt 2) und
Quellenreihenfolge (Abschnitt 3).

**Umfang:** $ARGUMENTS
Ohne Angabe: der heutige Tag. Bei `woche`: alle fünf Tage.

## Ablauf

1. **Datum bestimmen.** Ermitteln Sie das heutige Datum und den Wochentag, ohne zu raten
   (`date +"%A, %d.%m.%Y (KW %V)"`).

2. **Kalender lesen** nach CLAUDE.md Abschnitt 3, in dieser Reihenfolge:
   Google Calendar → `.ics` aus dem Drive-Ordner `Wochenplaner/Kalender/` → Gmail → Nachfrage.
   Nennen Sie zu Beginn der Antwort in einer Zeile, welche Quellen tatsächlich gelesen wurden
   und welche fehlten. Fehlt der Google-Calendar-Connector, weisen Sie darauf hin, dass er in
   den Connector-Einstellungen dieses Chats eingeschaltet werden muss.
   **Erfinden Sie unter keinen Umständen Termine.**

3. **Immer ausgeben, unabhängig vom gewählten Tag:**
   - Wochenübersicht Montag bis Freitag der laufenden Woche, je Tag verdichtet:
     Unterrichtsblöcke, Sitzungen, Gespräche, Termine ausser Haus, freie Blöcke.
     Ganztägige Termine gesondert.
   - **Donnerstagsprüfung:** DO-Sitzung, OTT oder keines von beidem – einen der drei Fälle
     ausdrücklich melden. OTT erkennen Sie am Stichwort im Termintitel; er tritt etwa
     monatlich auf.
   - **Dienstagsprüfung:** findet die DI-Sitzung statt?
   - **Vorausblick über 14 Tage** nach CLAUDE.md Abschnitt 6, sortiert nach Datum, je Eintrag
     mit verbleibenden Tagen. Was in weniger als fünf Tagen ansteht, hervorheben.

4. **Schwerpunkte des gewählten Tages** aus CLAUDE.md Abschnitt 4 abarbeiten. Bei `woche`
   alle fünf Tage. Am Montag zusätzlich die Agenda kontrollieren (Abschnitt 7), am Donnerstag
   die Agenda ausfüllen.

5. **Aufgabenliste** nach CLAUDE.md Abschnitt 8: nach Tagen gruppiert, je Aufgabe mit
   Zeitschätzung und auslösendem Anlass, höchstens sieben pro Tag.

6. **Wochenboard aktualisieren** nach CLAUDE.md Abschnitt 10: Wochendokument
   `wochen/<JJJJ-KWnn>` mit `read_db` lesen, Aufgaben und Vorausblick ergänzen, mit
   `write_db` zurückschreiben. Bereits abgehakte Aufgaben, eigene Einträge und Notizen
   nicht überschreiben. Anschliessend die Adresse des Boards nennen.

7. **Abschluss:** Nennen Sie in zwei bis drei Sätzen, worauf in dieser Woche besonders zu
   achten ist. Falls Angaben fehlen (Agenda-Ablageort, Fristen, Glossareinträge), fragen Sie
   gezielt nach – höchstens drei Fragen.
