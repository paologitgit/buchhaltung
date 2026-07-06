# Benutzeranleitung – Buchhaltung

Diese Anleitung richtet sich an dich als Anwender:in (Inhaber:in) und an
deine Treuhänderin. Sie beschreibt den täglichen/monatlichen Gebrauch der
App, nicht die technische Funktionsweise (dafür siehe
`docs/Technische_Dokumentation.md`).

## 1. Zweck der App

Die App ersetzt den physischen Buchhaltungsordner:

- Du importierst monatlich den CSV-Kontoauszug deiner Bank.
- Jede Bewegung wird einem Konto und (falls nötig) einem MWST-Code
  zugeordnet und dadurch automatisch als doppelte Buchung verbucht.
- Zu jeder Bewegung kannst du den Beleg (PDF/Foto) direkt hochladen.
- Die App zeigt dir, wo noch ein Beleg fehlt.
- Am Ende exportierst du das Journal für deine Treuhänderin, oder sie
  loggt sich selbst (lesend) ein.

## 2. App lokal starten (Mac, zum Testen)

Voraussetzung: Docker Desktop ist installiert.

1. Docker Desktop öffnen (Icon in der Menüleiste, keine Warnung mehr).
2. Terminal öffnen, in den Projektordner wechseln:
   ```
   cd ~/Downloads/buchhaltung
   ```
3. Starten:
   ```
   docker compose up -d db web
   ```
4. Im Browser öffnen: `http://localhost:8000`

**Stoppen**, wenn du fertig bist (deine Daten bleiben erhalten):
```
docker compose stop
```

**Wieder starten**:
```
docker compose start
```

Docker Desktop selbst muss nur laufen, während du die App benutzt – du
kannst es jederzeit schliessen, wenn du fertig bist.

## 3. Einloggen

Mit dem Benutzernamen/Passwort einloggen, das beim ersten Einrichten via
```
docker compose exec web python manage.py createsuperuser
```
erstellt wurde. Passwort später jederzeit über den Link „Passwort" oben
in der Navigation änderbar.

## 4. Einmalige Einrichtung

Diese Schritte machst du einmalig, bevor du den ersten CSV-Import machst.

### 4.1 Bankkonto anlegen

Aktuell nur über den technischen Admin-Bereich möglich:

1. Browser: `http://localhost:8000/admin/`, mit gleichem Login anmelden.
2. „BANK" → „Bankkonten" → „Bankkonto hinzufügen".
3. Ausfüllen:
   - **Name**: z. B. „Hauptkonto"
   - **Buchhaltungskonto**: „1020 – Bank" auswählen
   - **CSV-Spalte Datum / Betrag / Beschreibung**: müssen exakt den
     Spaltennamen (Kopfzeile) deiner Bank-CSV entsprechen
   - **CSV-Datumsformat**: z. B. `%d.%m.%Y` für „31.12.2026“, oder
     `%Y-%m-%d` für „2026-12-31“
4. „Sichern“.

Tipp: Öffne deine CSV-Datei einmal in einem Texteditor und schau dir die
erste Zeile an, bevor du das Formular ausfüllst.

### 4.2 Geschäftsjahr anlegen

„Geschäftsjahre“ in der Navigation → „Neues Geschäftsjahr“ → Start- und
Enddatum eingeben (z. B. 01.01.2026–31.12.2026). Ohne offenes
Geschäftsjahr kann keine Bewegung verbucht werden.

### 4.3 Zugang für die Treuhänderin einrichten (optional)

Admin-Bereich → „Benutzer“ → „Benutzer hinzufügen“:
- Benutzername/Passwort vergeben
- Rolle auf „Treuhänder:in (nur Lesen)“ setzen

Damit kann sie sich selbst einloggen, alles einsehen und exportieren,
aber nichts verändern, importieren oder verbuchen.

## 5. Monatlicher Ablauf

1. **CSV-Kontoauszug bei der Bank herunterladen** (E-Banking, meist unter
   „Kontoauszug“ oder „Bewegungen exportieren“).
2. In der App: „CSV-Import“ → Bankkonto wählen → Datei auswählen →
   „Importieren“. Bereits importierte Bewegungen werden automatisch
   erkannt und nicht doppelt angelegt.
3. „Bewegungen“ öffnen. Für jede offene Bewegung:
   - Bewegung anklicken
   - **Gegenkonto** wählen (z. B. „6500 Verwaltungsaufwand“)
   - **MWST-Code** wählen, falls MWST-pflichtig, sonst leer lassen
   - „Buchen“ klicken → die Buchung wird automatisch im Soll/Haben
     erstellt (inkl. MWST-Aufteilung, falls ein Code gewählt wurde)
   - **Beleg hochladen** (PDF oder Foto der Rechnung/Quittung)
   - Bewegungen, die nicht in die Buchhaltung gehören (z. B. interne
     Umbuchungen), kannst du stattdessen „Als ignoriert markieren“.
4. Auf dem Dashboard („Übersicht“) siehst du, ob noch Bewegungen mit
   **fehlendem Beleg** offen sind – Klick auf die Kachel zeigt dir genau
   diese Liste.

## 6. Bewegungen sortieren und filtern

Auf der Seite „Bewegungen“:
- Spaltentitel anklicken (Datum, Beschreibung, Betrag, Status) sortiert
  danach; nochmal klicken kehrt die Reihenfolge um.
- Filterleiste oben: nach Suchtext, Status, Bankkonto, Zeitraum, und
  „nur fehlende Belege“ filtern.

## 7. Journal & Export für die Treuhänderin

„Journal“ zeigt alle Buchungen. Oben „Export CSV“ oder „Export Excel“
lädt die aktuell gefilterte Ansicht herunter (z. B. nach Geschäftsjahr
gefiltert) – diese Datei kannst du deiner Treuhänderin schicken.
Alternativ gibst du ihr einen eigenen Lese-Login (siehe 4.3).

## 8. Geschäftsjahr abschliessen

Wenn ein Geschäftsjahr fertig verbucht ist: „Geschäftsjahre“ →
„abschliessen“. Danach sind alle Buchungen dieses Zeitraums gesperrt und
können nicht mehr verändert werden (Revisionssicherheit).

## 9. Kontenplan

„Kontenplan“ zeigt den Schweizer KMU-Kontenrahmen, der bereits
vorinstalliert ist. Weitere Konten kannst du im Admin-Bereich unter
„Buchhaltung“ → „Kontenplan“ hinzufügen, falls die Treuhänderin
zusätzliche Konten wünscht.

## 10. Was die App aktuell nicht kann

- Keine automatische Bankanbindung (Import läuft über manuellen
  CSV-Export/Import) – ist aber technisch vorbereitet.
- Kein PDF-Export, nur CSV/Excel.
- Nur eine Währung (CHF) im Alltagsgebrauch getestet.
