# 🎸 Gig-Finder

Findet Auftrittsorte für Musiker in der Schweiz: PLZ und Umkreis eingeben,
Kategorien wählen – das Tool sucht Locations (Bars, Cafés, Weingüter,
Eventlocations, Kulturbühnen …), liest deren Websites, extrahiert
E-Mail-Adressen und Ansprechpartner und zeigt alles in einer sortierbaren
Tabelle mit CSV-Export.

## Funktionsweise

1. **Finden** – Locations im Umkreis kommen aus OpenStreetMap (kostenlos,
   immer aktiv) und optional aus der Google Places API (bessere Abdeckung,
   findet auch Hochzeitsplaner und Eventagenturen).
2. **Anreichern** – Das Tool besucht die Website jeder Location inklusive
   Kontakt-/Impressumsseite und extrahiert E-Mail, Telefon und – wo
   auffindbar – die Kontaktperson.
3. **Beschreiben** (optional, mit Claude-API-Key) – Claude liest den
   Website-Auszug und liefert eine Kurzbeschreibung plus einen
   Eignungs-Score (1–5 Sterne) für Akustik-Auftritte mit Gitarre und Gesang.

Ohne API-Keys läuft alles – nur mit weniger Abdeckung und ohne
Beschreibungen.

## Schnellstart mit Docker

```bash
cp .env.example .env      # Keys eintragen (optional)
docker compose up --build
```

Dann im Browser: **http://localhost:8090**

## Ohne Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # Keys eintragen (optional)
python app.py
```

## Google-API-Key einrichten (optional, empfohlen)

1. Auf https://console.cloud.google.com ein Konto bzw. Projekt anlegen
   (Kreditkarte nötig, aber es gibt ein monatliches Gratis-Kontingent, das
   für den privaten Gebrauch normalerweise locker reicht).
2. Im Menü **APIs & Services → Library** die **«Places API (New)»**
   aktivieren.
3. Unter **APIs & Services → Credentials → Create Credentials → API key**
   einen Key erstellen.
4. Empfohlen: den Key unter «API restrictions» auf die Places API (New)
   einschränken.
5. Key in die `.env` eintragen: `GOOGLE_PLACES_API_KEY=...`

Kosten-Hinweis: Eine Suche mit allen Kategorien macht ca. 15–20
Text-Suchen. Bei gelegentlicher Nutzung bleibst Du im Gratis-Kontingent.
Zur Sicherheit kannst Du in der Google-Konsole ein Budget-Limit setzen.

## Claude-API-Key einrichten (optional, empfohlen)

1. Auf https://platform.claude.com ein Konto anlegen und ein kleines
   Guthaben laden (z. B. 5 $).
2. Unter **API Keys** einen Key erstellen.
3. Key in die `.env` eintragen: `ANTHROPIC_API_KEY=sk-ant-...`

Kosten-Hinweis: Die Anreicherung kostet grob 1–2 Rappen pro Location,
eine volle Suche mit 60 Locations also etwa 1 Franken. Standard-Modell ist
`claude-opus-5`; mit `CLAUDE_MODEL=claude-haiku-4-5` in der `.env` wird es
deutlich günstiger (dafür etwas weniger treffsicher).

## CSV-Export

Der Export ist Semikolon-getrennt mit UTF-8-BOM und öffnet damit direkt
sauber in Excel (Schweizer Gebietsschema). Spalten: Name, Kategorie,
Adresse, PLZ, Ort, Distanz, E-Mail, Kontaktperson, Telefon, Website,
Beschreibung, Eignung, Quelle.

## Ehrliche Grenzen

- E-Mail-Adressen findet das Tool bei grob 70–80 % der Locations mit
  Website; konkrete Ansprechpartner-Namen eher bei 30–40 % (meist aus dem
  Impressum). Der Rest bleibt `info@…` – das ist die Datenlage, kein Bug.
- OpenStreetMap deckt Bars/Restaurants gut ab, Hochzeitsplaner und
  Eventagenturen praktisch gar nicht – dafür braucht es den Google-Key.
- Bitte massvoll suchen: Overpass (OSM) ist ein Gemeinschaftsdienst.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## In ein eigenes GitHub-Repository überführen

Dieses Projekt liegt momentan als eigenständiger Branch
(`claude/gig-finder-tool-xx1u9s`) in der Buchhaltungs-Repo, weil beim
Erstellen kein neues Repository angelegt werden konnte. Der Branch teilt
**keine** Historie und keinen Code mit der Buchhaltung – bitte **nicht** in
deren `main` mergen. So ziehst Du ihn in ein eigenes Repo um:

1. Auf github.com ein neues, leeres Repository anlegen (z. B.
   `gig-finder`, ohne README).
2. Lokal:

   ```bash
   git clone --branch claude/gig-finder-tool-xx1u9s \
       https://github.com/paologitgit/buchhaltung.git gig-finder
   cd gig-finder
   git remote set-url origin https://github.com/paologitgit/gig-finder.git
   git push -u origin claude/gig-finder-tool-xx1u9s:main
   ```

3. Danach kann der Branch in der Buchhaltungs-Repo gelöscht werden.

## Lizenzen der Daten

- PLZ-Koordinaten: [GeoNames](https://www.geonames.org/) (CC-BY 4.0)
- Locations: © OpenStreetMap-Mitwirkende (ODbL), abgefragt über die
  Overpass API
