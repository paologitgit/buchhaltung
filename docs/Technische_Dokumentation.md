# Technische Dokumentation – Buchhaltung

Zielgruppe: Entwickler:innen, die das Projekt warten oder erweitern.
Für die Anwendung selbst siehe `anleitung/Benutzeranleitung.md`.

## 1. Stack

| Komponente     | Wahl                                    |
|-----------------|------------------------------------------|
| Backend         | Django 5 (Python 3.11)                  |
| Datenbank       | PostgreSQL 16                           |
| Webserver (prod)| Gunicorn hinter nginx (TLS-Terminierung) |
| Auth            | Django-eigenes Auth + django-axes (Brute-Force-Schutz) |
| Passwort-Hash   | Argon2 (via argon2-cffi)                |
| Deployment      | Docker Compose (web, db, nginx, certbot)|

## 2. App-Struktur

```
accounts/    Custom User-Modell (Rolle: OWNER / TRUSTEE), Login/Logout/Passwort
core/        Dashboard, gemeinsame Decorators (owner_required)
ledger/      Kontenplan, Geschäftsjahr, Buchungen (JournalEntry/JournalLine), Export
vat/         MWST-Codes
bank/        Bankkonten, CSV-Import, Bewegungen, Liste/Filter/Sortierung
documents/   Beleg-Upload und geschützte Auslieferung
```

Abhängigkeitsrichtung: `bank` und `vat` referenzieren `ledger.Account`
per String-FK (`"ledger.Account"`), `documents.Beleg` referenziert
`bank.Bewegung`. Keine zirkulären Python-Importe zwischen Apps.

## 3. Datenmodell (Kernentitäten)

- **accounts.User** – `role` (OWNER/TRUSTEE). `has_write_access()` ist
  die zentrale Berechtigungsprüfung, siehe unten.
- **ledger.Account** – Konto aus dem Kontenplan (`code`, `name`,
  `account_type`: AKTIVA/PASSIVA/AUFWAND/ERTRAG, `is_bank_account`).
- **ledger.FiscalYear** – Geschäftsjahr mit `is_closed`; `close()` sperrt
  alle zugehörigen `JournalEntry`-Objekte (`is_locked=True`).
- **ledger.JournalEntry / JournalLine** – Eine Buchung besteht aus ≥2
  Zeilen. `JournalLine` hat einen DB-CHECK-Constraint
  (`journalline_debit_xor_credit`), der erzwingt, dass pro Zeile genau
  eine Seite (Soll **oder** Haben) > 0 ist – nicht beide, nicht keine.
- **vat.VatCode** – `rate_percent`, `direction` (INPUT=Vorsteuer,
  OUTPUT=Umsatzsteuer, NONE), `clearing_account` (Verrechnungskonto).
- **bank.BankAccount** – verknüpft mit einem `ledger.Account`
  (`is_bank_account=True`) und trägt die CSV-Spalten-Zuordnung
  (`csv_date_column`, `csv_amount_column`, `csv_description_column`,
  `csv_date_format`, `csv_delimiter`).
- **bank.ImportBatch** – Protokoll jedes CSV-Imports (Zeilen/erstellt/
  Duplikate), referenziert von den erzeugten `Bewegung`-Objekten.
- **bank.Bewegung** – eine Bank-Zeile. `source` (CSV/API/MANUAL) ist
  bewusst als eigenes Feld modelliert, um eine spätere Live-Bankanbindung
  ohne Schemaänderung zu ermöglichen (`source=API` statt `CSV`).
  `dedup_hash` (SHA-256 aus Bankkonto+Datum+Betrag+Text) verhindert
  doppelte Bewegungen bei überlappenden CSV-Exporten.
- **documents.Beleg** – Datei-Upload, referenziert eine `Bewegung`.

## 4. Buchungslogik (`ledger/services.py::book_bewegung`)

Läuft transaktional (`@transaction.atomic`). Ablauf:

1. Sucht das offene `FiscalYear`, das `bewegung.booking_date` enthält –
   wirft `ValidationError`, falls keins existiert.
2. Bestimmt Brutto-Betrag (`abs(bewegung.amount)`), berechnet bei
   gesetztem `vat_code` den Netto-Betrag:
   `net = gross / (1 + rate/100)`, gerundet auf 2 Stellen
   (`ROUND_HALF_UP`); `vat_amount = gross - net` (keine zweite Rundung,
   damit die Summe exakt aufgeht).
3. Ausgang (`amount < 0`): Soll = Gegenkonto (netto) + ggf. Vorsteuer,
   Haben = Bankkonto (brutto).
   Eingang (`amount > 0`): Soll = Bankkonto (brutto), Haben = Gegenkonto
   (netto) + ggf. Umsatzsteuer.
4. Nach dem Erstellen aller Zeilen wird `entry.is_balanced` geprüft
   (zusätzliche Absicherung neben dem DB-Constraint).
5. `Bewegung` wird auf `status=BOOKED` gesetzt und mit der `JournalEntry`
   verknüpft (`OneToOneField`, verhindert doppeltes Verbuchen).

**Bekannte Einschränkung:** Es wird nur ein einziger VAT-Code pro
Bewegung unterstützt (keine gemischten Steuersätze in einer Buchung).

## 5. CSV-Import (`bank/services.py::import_csv`)

- Liest die Datei als UTF-8 (mit BOM-Toleranz), nutzt `csv.DictReader`
  mit dem pro Bankkonto konfigurierten Trennzeichen.
- Betragsparsing (`_parse_amount`) toleriert sowohl
  `1'234.50` (CH) als auch `1.234,50` (DE/AT)-Notation.
- Dedup über `dedup_hash`; `get_or_create` sorgt dafür, dass ein
  wiederholter Import derselben Datei keine Duplikate erzeugt.
- Wirft `ValidationError` bei fehlender Spalte oder ungültigem Datum –
  wird in `bank/views.py::import_view` abgefangen und als
  Django-Message angezeigt.

## 6. Rollen & Zugriffskontrolle

- `accounts.User.role`: `OWNER` (voller Zugriff) oder `TRUSTEE`
  (nur Lesen).
- `core.decorators.owner_required`: wirft `PermissionDenied` (→ HTTP 403),
  falls `request.user.has_write_access()` falsch ist. Wird mit
  `@login_required` kombiniert auf allen schreibenden Views
  (`bewegung_import`, `beleg_upload`, `beleg_delete`,
  `fiscal_year_create`, `fiscal_year_close`).
- In `bewegung_detail` wird zusätzlich serverseitig geprüft
  (nicht nur im Template versteckt), dass ein Buchungs-POST nur bei
  `has_write_access()` verarbeitet wird – ein manuell abgeschicktes
  POST einer Treuhänderin hat also keine Wirkung.

## 7. Sicherheit

- **Transport**: `SECURE_SSL_REDIRECT`, `SECURE_HSTS_*` in
  `config/settings/prod.py`; `SECURE_PROXY_SSL_HEADER` liest
  `X-Forwarded-Proto` von nginx.
- **Login**: Argon2-Hashing, `django-axes` (5 Fehlversuche → 1h Sperre,
  pro Username+IP), Passwort-Mindestlänge 12 Zeichen.
- **Session/CSRF**: `HttpOnly`, `SameSite=Lax`, `Secure` (prod),
  Session-Ablauf 8h / beim Schliessen des Browsers.
- **Belege**: `MEDIA_ROOT` wird **nicht** über eine öffentliche URL
  ausgeliefert. `documents/views.py::beleg_download` ist
  `@login_required` und liest die Datei serverseitig
  (`FileResponse`) – es existiert keine direkte Static-Route auf
  `/media/`, weder in nginx noch in `config/urls.py`.
- **Datenbank**: Im `docker-compose.yml` hat der `db`-Service keinen
  `ports:`-Eintrag – von aussen nicht erreichbar, nur im internen
  Docker-Netzwerk (`internal`).
- **Datei-Uploads**: `documents/forms.py` prüft `content_type`
  (Whitelist PDF/JPEG/PNG/WEBP) und Grösse (`MAX_UPLOAD_SIZE_BYTES`,
  15 MB) serverseitig.
- Verifiziert via `python manage.py check --deploy` unter
  `config.settings.prod` (nur die erwartete `SECRET_KEY`-Warnung, die
  durch einen echten Produktions-Key behoben wird).

## 8. Deployment

### Lokal/Dev (Mac, ohne HTTPS)

`docker-compose.override.yml` wird von `docker compose` automatisch
zusätzlich geladen: überschreibt `DJANGO_SETTINGS_MODULE` auf
`config.settings.dev` (kein SSL-Zwang) und published Port 8000 direkt.
→ `docker compose up -d db web`, erreichbar unter `http://localhost:8000`.

**Für einen echten Server-Deploy diese Override-Datei entfernen** oder
explizit umgehen (`docker compose -f docker-compose.yml up -d`), sonst
läuft der Server ohne HTTPS-Erzwingung.

### Produktiv (mit HTTPS)

Siehe Kommentarkopf in `docker-compose.yml` bzw. `nginx/nginx.conf`:

1. Domain in `nginx/nginx.conf` eintragen, 443-Block zunächst
   auskommentieren.
2. `docker compose up -d nginx web db`.
3. Zertifikat holen:
   `docker compose run --rm certbot certonly --webroot -w /var/www/certbot -d DEINE-DOMAIN`.
4. 443-Block aktivieren, `docker compose restart nginx`.
5. Der `certbot`-Service läuft dauerhaft und erneuert automatisch.

`entrypoint.sh` führt bei jedem Start automatisch `migrate`,
`loaddata kontenrahmen_ch_kmu vat_codes_ch` (idempotent) und
`collectstatic` aus, bevor Gunicorn startet.

## 9. Wichtige Management-Befehle

```
python manage.py migrate
python manage.py loaddata kontenrahmen_ch_kmu vat_codes_ch
python manage.py createsuperuser
python manage.py makemigrations <app>   # nach Modelländerungen
python manage.py check --deploy         # Security-Check für prod-Settings
```

## 10. Bekannte Grenzen / nächste Schritte

- Keine PDF-Export-Option (nur CSV/Excel in `ledger/export.py`).
- Keine automatische Bank-API-Anbindung; `Bewegung.source` und die
  `ImportBatch`-Struktur sind aber so angelegt, dass ein zusätzlicher
  Import-Pfad (`source=API`) ohne Schemaänderung ergänzt werden kann.
- Nur ein VAT-Code pro Buchung (keine gemischten Steuersätze).
- Kein UI zum Anlegen von Bankkonten/Benutzern – läuft über
  `/admin/`. Für den täglichen Gebrauch ist das ausreichend, für eine
  breitere Nutzerbasis wäre ein eigenes Formular sinnvoll.
- Keine automatisierten Tests im Repo; Verifikation bisher über einen
  manuellen End-to-End-Smoke-Test (Login → Import → Buchen → Beleg →
  Export → Rollenprüfung).
