# Popup Manager – WordPress-Plugin

Einfaches Popup-Plugin: Inhalt kommt aus dem normalen WordPress-Editor
(Text und Bilder), das Popup erscheint immer mittig im Bildschirm.

## Funktionen

| Anforderung | Umsetzung |
|---|---|
| Wo soll das Popup erscheinen | Ganze Website, nur Startseite, nur ausgewählte Seiten oder überall ausser den ausgewählten Seiten |
| Wegklicken oder von selbst verschwinden | Schliessen-Button, Klick auf den Hintergrund, Escape-Taste, automatisch nach X Sekunden – frei kombinierbar |
| Bilder oder Text mit CSS | WordPress-Editor für den Inhalt, pro Popup ein eigenes CSS-Feld |
| Platzierung | Immer mittig, auf schmalen Bildschirmen automatisch schmaler |
| Grösse | Breite in Pixel, optional maximale Höhe |

Zusätzlich: Verzögerung in Sekunden vor dem Erscheinen und die Häufigkeit
pro Besucher (jeder Aufruf / einmal pro Besuch / einmal alle X Tage).

## Installation

1. Den Ordner `popup-manager` nach `wp-content/plugins/` kopieren.
   Alternativ den Ordner als ZIP packen und über *Plugins → Installieren →
   Plugin hochladen* einspielen.
2. Unter *Plugins* das Plugin „Popup Manager" aktivieren.
3. Im Menü erscheint der Punkt **Popups**.

## Ein Popup anlegen

1. *Popups → Erstellen*.
2. **Titel**: nur interne Bezeichnung, für Besucher unsichtbar.
3. **Editor**: Inhalt des Popups. Bilder über *Medien hinzufügen* einfügen,
   Text ganz normal schreiben.
4. **Popup-Einstellungen** darunter ausfüllen.
5. **Veröffentlichen**. Ein Popup ist nur aktiv, solange es veröffentlicht
   ist – als Entwurf oder im Papierkorb erscheint es nicht.

Mit *Vorschau auf der Website öffnen* lässt sich das Popup testen. Die
Vorschau ignoriert Platzierung und Häufigkeit und ist nur für angemeldete
Bearbeiter sichtbar.

## Einstellungen im Detail

### Wo soll das Popup erscheinen?

* **Auf der ganzen Website** – jede Seite, jeder Beitrag, auch Archive.
* **Nur auf der Startseite**
* **Nur auf ausgewählten Seiten** – Mehrfachauswahl aus Seiten und Beiträgen.
* **Überall ausser auf ausgewählten Seiten**

### Erscheinen und Schliessen

* **Anzeigen nach** – Sekunden nach dem Laden der Seite, `0` = sofort.
* **Automatisch schliessen nach** – Sekunden, `0` = bleibt offen.
* **Schliessen-Button (×)**
* **Klick auf den Hintergrund schliesst das Popup**

Die Escape-Taste schliesst das Popup immer, sobald eine der beiden manuellen
Schliessmöglichkeiten aktiv ist. Wird alles deaktiviert und ist kein
automatisches Schliessen eingestellt, aktiviert das Plugin beim Speichern
den Schliessen-Button – sonst käme der Besucher nicht mehr weiter.

### Wie oft pro Besucher?

Gespeichert wird im Browser des Besuchers (`sessionStorage` bzw.
`localStorage`), nicht auf dem Server. Das funktioniert auch mit
Caching-Plugins. Wer seine Browserdaten löscht, sieht das Popup erneut.

### Grösse

Breite in Pixel; das Popup wird nie breiter als das Fenster. Maximale Höhe
`0` bedeutet: so hoch wie der Inhalt, maximal die Fensterhöhe. Längerer
Inhalt wird im Popup scrollbar.

### Eigenes CSS

Gilt nur für das jeweilige Popup. Nützliche Selektoren – `123` durch die
ID des Popups ersetzen, sie steht in der Beschriftung des Feldes:

```css
/* Rahmen des Popups */
#pm-popup-123 .pm-popup__box {
	background: #0f172a;
	color: #f8fafc;
	border-radius: 16px;
	padding: 40px;
}

/* Inhaltsbereich */
#pm-popup-123 .pm-popup__content h2 {
	margin-bottom: 12px;
}

/* Abdunkelung dahinter */
#pm-popup-123 .pm-popup__overlay {
	background: rgba(0, 0, 0, 0.85);
}

/* Schliessen-Button */
#pm-popup-123 .pm-popup__close {
	color: #fff;
}
```

## Mehrere Popups gleichzeitig

Treffen auf einer Seite mehrere Popups zu, erscheinen sie nacheinander: das
nächste öffnet sich erst, wenn das vorherige geschlossen wurde.

## Wenn nichts erscheint

Der Reihe nach prüfen:

1. **Ist das Popup veröffentlicht?** Entwürfe und Papierkorb-Einträge
   erscheinen nie.
2. **Vorschau-Link testen** (in der Popup-Liste oder im Editor). Erscheint
   das Popup dort, liegt es an Platzierung oder Häufigkeit, nicht am Plugin.
3. **Platzierung**: Steht „Nur auf ausgewählten Seiten", ohne dass eine
   Seite markiert ist, erscheint das Popup nirgends.
4. **Häufigkeit**: Bei „einmal pro Besuch" oder „alle X Tage" wurde das
   Popup womöglich schon gezeigt. Ein privates Browserfenster zeigt es
   wieder.
5. **Caching-Plugin** leeren, falls eines aktiv ist.
6. **Theme**: Das Plugin hängt sich in `wp_footer()` ein. Themes, die
   diesen Aufruf weglassen, sind fehlerhaft und verhindern die Ausgabe.

## Aufbau

```
popup-manager/
├── popup-manager.php          Plugin-Header, Autoloader
├── uninstall.php              Löscht die Popups beim Deinstallieren
├── includes/
│   ├── class-plugin.php       Feld-Schema, Defaults, Bereinigung
│   ├── class-post-type.php    Post Type "Popups" und Übersichtsliste
│   ├── class-meta-boxes.php   Einstellungsformular und Speichern
│   └── class-frontend.php     Auswahl der Popups und Ausgabe
└── assets/
    ├── css/popup.css          Darstellung im Frontend
    ├── css/admin.css          Formular im Backend
    ├── js/popup.js            Öffnen, Schliessen, Häufigkeit
    └── js/admin.js            Ein- und Ausblenden der Formularfelder
```

Ein neues Einstellungsfeld braucht drei Stellen: Eintrag in
`Plugin::fields()`, Eingabefeld in `Meta_Boxes::render()` und Auswertung in
`class-frontend.php`.

## Hinweise

* Benötigt WordPress 6.0 und PHP 7.4 oder neuer.
* Die Popups werden im klassischen Editor bearbeitet, damit Inhalt und
  Einstellungen in einer Maske liegen.
* Barrierefreiheit: `role="dialog"`, Fokus bleibt im offenen Popup, Escape
  schliesst, der Fokus kehrt danach an die vorherige Stelle zurück.
  Animationen entfallen bei aktivierter Einstellung „Bewegung reduzieren".
* **Löschen des Plugins** (nicht Deaktivieren) entfernt auch alle
  angelegten Popups.

## Übersetzung

Alle Texte laufen über die Textdomain `popup-manager`. Vorlage erzeugen mit
WP-CLI:

```bash
wp i18n make-pot wordpress/popup-manager wordpress/popup-manager/languages/popup-manager.pot
```
