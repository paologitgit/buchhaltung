/* Finanzblick – CSV-Erkennung und -Auswertung.
 *
 * Bank-Exporte sind praktisch nie einheitlich: Trennzeichen, Kodierung,
 * Kopfzeilen vor der Tabelle, Zahlen- und Datumsformate unterscheiden sich pro
 * Institut. Dieses Modul rät das Format und legt die Vermutung offen, damit sie
 * in der Oberfläche korrigiert werden kann.
 */
(function (FB) {
  "use strict";

  /* ---------------------------------------------------------------- Text -- */

  /** Viele Schweizer und deutsche Exporte sind Windows-1252, nicht UTF-8. */
  function decode(buffer) {
    var bytes = new Uint8Array(buffer);
    try {
      var text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
      return { text: stripBom(text), encoding: "UTF-8" };
    } catch (e) {
      return {
        text: stripBom(new TextDecoder("windows-1252").decode(bytes)),
        encoding: "Windows-1252",
      };
    }
  }

  function stripBom(text) {
    return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
  }

  /** Normalisiert Spaltennamen für den Vergleich mit den Synonymlisten. */
  function normalizeKey(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/ä/g, "ae")
      .replace(/ö/g, "oe")
      .replace(/ü/g, "ue")
      .replace(/ß/g, "ss")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]/g, "");
  }

  /* ----------------------------------------------------------------- CSV -- */

  var DELIMITERS = [";", ",", "\t", "|"];

  function parseCsv(text, delimiter) {
    var rows = [];
    var row = [];
    var field = "";
    var inQuotes = false;
    var i = 0;

    while (i < text.length) {
      var c = text[i];
      if (inQuotes) {
        if (c === '"') {
          if (text[i + 1] === '"') {
            field += '"';
            i += 2;
            continue;
          }
          inQuotes = false;
          i++;
          continue;
        }
        field += c;
        i++;
        continue;
      }
      if (c === '"' && field === "") {
        inQuotes = true;
        i++;
        continue;
      }
      if (c === delimiter) {
        row.push(field);
        field = "";
        i++;
        continue;
      }
      if (c === "\r") {
        i++;
        continue;
      }
      if (c === "\n") {
        row.push(field);
        rows.push(row);
        row = [];
        field = "";
        i++;
        continue;
      }
      field += c;
      i++;
    }
    if (field !== "" || row.length) {
      row.push(field);
      rows.push(row);
    }
    return rows.map(function (r) {
      return r.map(function (cell) {
        return cell.trim();
      });
    });
  }

  /**
   * Wählt das Trennzeichen, das die gleichmässigsten Zeilen erzeugt. Ein Komma
   * in einem Buchungstext soll nicht als Trennzeichen durchgehen, deshalb zählt
   * nicht die Spaltenzahl allein, sondern wie oft sie sich wiederholt.
   */
  function detectDelimiter(text) {
    var sample = text.split("\n").slice(0, 40).join("\n");
    var best = { delimiter: ";", score: -1 };

    DELIMITERS.forEach(function (delimiter) {
      var rows = parseCsv(sample, delimiter).filter(function (r) {
        return r.join("").length > 0;
      });
      if (!rows.length) return;

      var counts = {};
      rows.forEach(function (r) {
        counts[r.length] = (counts[r.length] || 0) + 1;
      });
      var modal = 1;
      var modalHits = 0;
      Object.keys(counts).forEach(function (len) {
        if (counts[len] > modalHits || (counts[len] === modalHits && +len > modal)) {
          modal = +len;
          modalHits = counts[len];
        }
      });
      if (modal < 2) return;

      var score = modal * (modalHits / rows.length);
      if (score > best.score) best = { delimiter: delimiter, score: score };
    });

    return best.delimiter;
  }

  /* ------------------------------------------------------------ Synonyme -- */

  var SYNONYMS = {
    date: [
      "datum", "buchungsdatum", "buchungstag", "valuta", "valutadatum",
      "wertstellung", "transaktionsdatum", "date", "bookingdate", "valuedate",
      "postingdate", "transactiondate", "datumbuchung", "buchung",
    ],
    amount: [
      "betrag", "amount", "umsatz", "betragchf", "betrageur", "betragin",
      "betragfw", "wert", "value", "einzelbetrag", "transaktionsbetrag",
    ],
    debit: [
      "belastung", "soll", "sollchf", "lastschrift", "ausgang", "debit",
      "auszahlung", "abgang", "ausgabe", "belastungchf", "aus",
    ],
    credit: [
      "gutschrift", "haben", "habenchf", "eingang", "credit", "einzahlung",
      "zugang", "einnahme", "gutschriftchf", "ein",
    ],
    description: [
      "beschreibung", "buchungstext", "text", "verwendungszweck", "details",
      "description", "mitteilung", "buchungsinformationen", "buchungsinformation",
      "zahlungsempfaenger", "beguenstigter", "empfaenger", "auftraggeber",
      "namezahlungsbeteiligter", "gegenpartei", "avistext", "zweck",
      "payee", "narrative", "memo", "name",
    ],
    /* Die Belegnummer der Bank. Sie gehört nicht in den Buchungstext, sondern
     * ist der verlässlichste Weg, dieselbe Buchung in zwei Exporten wieder-
     * zuerkennen. */
    reference: [
      "transaktionsnr", "transaktionsnummer", "transaktion", "referenz",
      "referenznr", "reference", "belegnr", "belegnummer", "buchungsnr",
      "auftragsnr", "endtoendid", "transactionid", "id",
    ],
    balance: ["saldo", "kontostand", "balance", "saldochf", "laufendersaldo"],
    currency: ["waehrung", "currency", "wkz", "waehrungcode", "iso"],
  };

  function matchesSynonym(key, list) {
    if (!key) return 0;
    for (var i = 0; i < list.length; i++) {
      if (key === list[i]) return 2; // exakte Treffer schlagen Teiltreffer
      if (key.indexOf(list[i]) === 0 && list[i].length >= 4) return 1;
    }
    return 0;
  }

  /* ---------------------------------------------------------- Kopfzeile -- */

  /**
   * Bank-Exporte stellen der Tabelle oft Kontonummer, Adresse und Saldo voran.
   * Gesucht ist die Zeile, deren Zellen wie Spaltennamen aussehen.
   */
  function findHeaderIndex(rows) {
    var limit = Math.min(rows.length, 30);
    var best = { index: -1, score: 0 };

    for (var i = 0; i < limit; i++) {
      var row = rows[i];
      var filled = row.filter(function (c) {
        return c !== "";
      }).length;
      if (filled < 2) continue;

      var score = 0;
      row.forEach(function (cell) {
        var key = normalizeKey(cell);
        Object.keys(SYNONYMS).forEach(function (role) {
          score += matchesSynonym(key, SYNONYMS[role]);
        });
      });
      // Eine Kopfzeile enthält keine Beträge oder Daten als Werte.
      if (row.some(looksLikeDate) || row.filter(looksLikeNumber).length > 1) score -= 3;

      if (score > best.score) best = { index: i, score: score };
    }
    return best.index;
  }

  /* ------------------------------------------------------------- Zahlen -- */

  var NUMBER_RE = /^-?[\d'’.,\s]*\d[\d'’.,\s]*-?$/;

  function looksLikeNumber(value) {
    var raw = String(value || "").trim();
    if (!raw) return false;
    raw = raw.replace(/^[A-Za-z]{3}\s*/, "").replace(/[+()]/g, "");
    return NUMBER_RE.test(raw) && /\d/.test(raw);
  }

  /**
   * Erkennt CHF 1'234.50, 1.234,50, 1,234.50, 1234.50-, (1234.50) und -1234.
   * Rückgabe null, wenn sich kein Betrag lesen lässt.
   */
  function parseAmount(value) {
    var raw = String(value == null ? "" : value).trim();
    if (!raw) return null;

    var negative = false;
    if (/^\(.*\)$/.test(raw)) {
      negative = true;
      raw = raw.slice(1, -1);
    }
    raw = raw.replace(/[A-Za-z]{3}/g, "").replace(/[\s '’]/g, "");
    if (/-$/.test(raw)) {
      negative = true;
      raw = raw.slice(0, -1);
    }
    if (/^[-+]/.test(raw)) {
      negative = negative || raw[0] === "-";
      raw = raw.slice(1);
    }
    if (!/^[\d.,]*\d[\d.,]*$/.test(raw)) return null;

    var lastComma = raw.lastIndexOf(",");
    var lastDot = raw.lastIndexOf(".");
    if (lastComma > -1 && lastDot > -1) {
      // Das hintere Zeichen ist das Dezimaltrennzeichen.
      if (lastComma > lastDot) raw = raw.replace(/\./g, "").replace(",", ".");
      else raw = raw.replace(/,/g, "");
    } else if (lastComma > -1) {
      raw = /^\d{1,3}(,\d{3})+$/.test(raw) ? raw.replace(/,/g, "") : raw.replace(",", ".");
    } else if (lastDot > -1) {
      if (/^\d{1,3}(\.\d{3})+$/.test(raw)) raw = raw.replace(/\./g, "");
    }

    var num = Number(raw);
    if (!isFinite(num)) return null;
    return negative ? -num : num;
  }

  /* -------------------------------------------------------------- Datum -- */

  var DATE_PATTERNS = [
    { re: /^(\d{4})-(\d{1,2})-(\d{1,2})/, order: "ymd" },
    { re: /^(\d{4})\/(\d{1,2})\/(\d{1,2})/, order: "ymd" },
    { re: /^(\d{1,2})\.(\d{1,2})\.(\d{2,4})/, order: "dmy" },
    { re: /^(\d{1,2})\/(\d{1,2})\/(\d{2,4})/, order: "slash" },
    { re: /^(\d{1,2})-(\d{1,2})-(\d{2,4})/, order: "slash" },
  ];

  function looksLikeDate(value) {
    var raw = String(value || "").trim();
    if (!raw) return false;
    return DATE_PATTERNS.some(function (p) {
      return p.re.test(raw);
    });
  }

  function fullYear(year) {
    if (year >= 1000) return year;
    return year < 70 ? 2000 + year : 1900 + year;
  }

  /**
   * dd/mm/yyyy und mm/dd/yyyy sind nur am Datenbestand unterscheidbar: taucht
   * irgendwo eine erste Zahl > 12 auf, ist es europäisch; ist die zweite > 12,
   * amerikanisch. Ohne Hinweis bleibt es beim europäischen Format.
   */
  function detectSlashOrder(samples) {
    var firstOver12 = false;
    var secondOver12 = false;
    samples.forEach(function (value) {
      var m = /^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})/.exec(String(value || "").trim());
      if (!m) return;
      if (+m[1] > 12) firstOver12 = true;
      if (+m[2] > 12) secondOver12 = true;
    });
    if (secondOver12 && !firstOver12) return "mdy";
    return "dmy";
  }

  function makeDateParser(samples) {
    var slashOrder = detectSlashOrder(samples);

    return function parseDate(value) {
      var raw = String(value == null ? "" : value).trim();
      if (!raw) return null;

      for (var i = 0; i < DATE_PATTERNS.length; i++) {
        var m = DATE_PATTERNS[i].re.exec(raw);
        if (!m) continue;
        var order = DATE_PATTERNS[i].order;
        if (order === "slash") order = slashOrder;

        var y, mo, d;
        if (order === "ymd") {
          y = +m[1]; mo = +m[2]; d = +m[3];
        } else if (order === "mdy") {
          mo = +m[1]; d = +m[2]; y = fullYear(+m[3]);
        } else {
          d = +m[1]; mo = +m[2]; y = fullYear(+m[3]);
        }
        if (mo < 1 || mo > 12 || d < 1 || d > 31) return null;

        var date = new Date(y, mo - 1, d);
        if (date.getFullYear() !== y || date.getMonth() !== mo - 1 || date.getDate() !== d) {
          return null;
        }
        return date;
      }
      return null;
    };
  }

  /* --------------------------------------------------------- Zuordnung --- */

  /**
   * Ordnet Rollen anhand der Spaltennamen zu. Spalten, die in den Daten
   * durchgehend leer sind, kommen nicht in Frage: Exporte führen oft Spalten
   * mit, die für die eigene Kontoart gar nicht befüllt werden, und eine leere
   * "Belastung" darf die gefüllte "Betrag"-Spalte nicht verdrängen.
   */
  function scoreColumnsByName(header, stats) {
    var picks = {};
    var used = {};

    ["date", "amount", "debit", "credit", "balance", "currency", "reference", "description"].forEach(
      function (role) {
        var best = { index: -1, score: 0 };
        header.forEach(function (name, index) {
          if (used[index]) return;
          if (stats && stats[index] && stats[index].filled === 0) return;
          var score = matchesSynonym(normalizeKey(name), SYNONYMS[role]);
          if (score > best.score) best = { index: index, score: score };
        });
        if (best.index > -1) {
          picks[role] = best.index;
          used[best.index] = true;
        }
      }
    );
    return picks;
  }

  function columnStats(rows, index) {
    var dates = 0;
    var numbers = 0;
    var texts = 0;
    var filled = 0;
    var negatives = 0;

    rows.forEach(function (row) {
      var value = row[index];
      if (value == null || value === "") return;
      filled++;
      if (looksLikeDate(value)) dates++;
      else if (looksLikeNumber(value)) {
        numbers++;
        var n = parseAmount(value);
        if (n != null && n < 0) negatives++;
      } else texts++;
    });

    return {
      filled: filled,
      dateRatio: filled ? dates / filled : 0,
      numberRatio: filled ? numbers / filled : 0,
      textRatio: filled ? texts / filled : 0,
      negatives: negatives,
      avgLength:
        rows.reduce(function (sum, row) {
          return sum + String(row[index] || "").length;
        }, 0) / Math.max(rows.length, 1),
    };
  }

  /**
   * Ergänzt fehlende Zuordnungen anhand des Inhalts – nützlich bei Exporten mit
   * kryptischen oder fehlenden Spaltennamen.
   */
  /**
   * Findet die Saldospalte am Inhalt: ihr Zuwachs von Zeile zu Zeile
   * entspricht dem Betrag der Buchung. Das ist ein eindeutiges Merkmal und
   * funktioniert auch bei Spaltennamen, die in keiner Synonymliste stehen.
   */
  function findBalanceByContent(rows, mapping, stats) {
    var taken = [mapping.date, mapping.amount, mapping.debit, mapping.credit];
    var best = { index: -1, ratio: 0 };

    stats.forEach(function (stat, index) {
      if (taken.indexOf(index) > -1) return;
      if (stat.numberRatio < 0.7 || stat.filled < 3) return;

      var forward = 0;
      var backward = 0;
      var checks = 0;
      var previous = null;
      var since = 0; // Beträge seit dem letzten gefüllten Saldo

      rows.forEach(function (row) {
        var amount = rowAmount(row, mapping);
        if (amount != null) since += amount;

        var value = parseAmount(row[index]);
        if (value == null) return; // Lücke: der nächste Sprung umfasst mehrere Beträge

        if (previous != null) {
          checks++;
          // Je nach Sortierung der Datei wächst der Saldo mit oder gegen die Beträge.
          if (Math.abs(value - previous - since) < 0.05) forward++;
          if (Math.abs(previous - value - since) < 0.05) backward++;
        }
        previous = value;
        since = 0;
      });

      if (checks < 3) return;
      var ratio = Math.max(forward, backward) / checks;
      if (ratio > 0.7 && ratio > best.ratio) best = { index: index, ratio: ratio };
    });

    return best.index > -1 ? best.index : null;
  }

  function mapColumns(header, dataRows) {
    var sample = dataRows.slice(0, 200);
    var stats = header.map(function (_, index) {
      return columnStats(sample, index);
    });
    var mapping = scoreColumnsByName(header, stats);

    if (mapping.date == null) {
      var bestDate = { index: -1, ratio: 0.6 };
      stats.forEach(function (s, index) {
        if (s.dateRatio > bestDate.ratio) bestDate = { index: index, ratio: s.dateRatio };
      });
      if (bestDate.index > -1) mapping.date = bestDate.index;
    }

    if (mapping.amount == null && mapping.debit == null && mapping.credit == null) {
      // Betragsspalten enthalten typischerweise Vorzeichen; ein reiner Saldo
      // läuft dagegen monoton und wird deshalb nachrangig behandelt.
      var candidates = [];
      stats.forEach(function (s, index) {
        if (index === mapping.date) return;
        if (s.numberRatio > 0.7 && s.filled > 0) {
          candidates.push({ index: index, negatives: s.negatives, filled: s.filled });
        }
      });
      candidates.sort(function (a, b) {
        return b.negatives - a.negatives;
      });
      if (candidates.length) mapping.amount = candidates[0].index;
    }

    // Exporte führen teils beides: ein Paar Belastung/Gutschrift für die
    // Buchungen und eine Betragsspalte für die Detailzeilen von
    // Sammelbuchungen (UBS: "Einzelbetrag"). Beides zusammen zu lesen zählt
    // die Sammelbuchung doppelt, deshalb gewinnt die Darstellung, die mehr
    // Zeilen abdeckt – und nur sie wird gelesen.
    if ((mapping.debit != null || mapping.credit != null) && mapping.amount != null) {
      var pairRows = 0;
      var amountRows = 0;
      sample.forEach(function (row) {
        var debit = mapping.debit != null ? parseAmount(row[mapping.debit]) : null;
        var credit = mapping.credit != null ? parseAmount(row[mapping.credit]) : null;
        if (debit || credit) pairRows++;
        if (parseAmount(row[mapping.amount])) amountRows++;
      });
      if (pairRows >= amountRows) {
        delete mapping.amount;
      } else {
        delete mapping.debit;
        delete mapping.credit;
      }
    }

    if (mapping.balance == null) {
      var byContent = findBalanceByContent(sample, mapping, stats);
      if (byContent != null) mapping.balance = byContent;
    }

    if (mapping.description == null) {
      var bestText = { index: -1, score: 0 };
      stats.forEach(function (s, index) {
        if (index === mapping.date || index === mapping.amount) return;
        var score = s.textRatio * s.avgLength;
        if (score > bestText.score) bestText = { index: index, score: score };
      });
      if (bestText.index > -1) mapping.description = bestText.index;
    }

    // Eine zweite Textspalte (z.B. Empfänger + Verwendungszweck) ergänzt den Text.
    if (mapping.description != null && mapping.description2 == null) {
      var bestSecond = { index: -1, score: 0 };
      stats.forEach(function (s, index) {
        if (index === mapping.description || index === mapping.date) return;
        if (index === mapping.amount || index === mapping.debit) return;
        if (index === mapping.credit || index === mapping.balance) return;
        if (index === mapping.reference) return;
        var score = s.textRatio * s.avgLength;
        if (score > bestSecond.score && s.avgLength > 6) {
          bestSecond = { index: index, score: score };
        }
      });
      if (bestSecond.index > -1) mapping.description2 = bestSecond.index;
    }

    return mapping;
  }

  /* ---------------------------------------------------------- Kontoname -- */

  var IBAN_COUNTRY = /^(CH|LI|DE|AT|FR|IT|NL|BE|LU|ES|PT|GB|IE|DK|SE|NO|FI|PL|CZ|HU|SI|SK|HR|GR|EE|LV|LT|MT|CY|BG|RO|IS|MC|SM|AD)\d{2}[A-Z0-9]+$/;

  /**
   * Prüft eine IBAN über ihre Prüfsumme (ISO 13616: die ersten vier Zeichen
   * nach hinten, Buchstaben zu Zahlen, Rest bei Division durch 97 muss 1 sein).
   *
   * Mustersuche allein genügt nicht: "SBB BILLETT" sieht nach zwei Buchstaben,
   * zwei Ziffern und Blöcken aus und ging als IBAN durch. Die Prüfsumme macht
   * die Erkennung eindeutig.
   */
  function isValidIban(candidate) {
    var value = String(candidate).replace(/\s/g, "").toUpperCase();
    if (value.length < 15 || value.length > 34) return false;
    if (!IBAN_COUNTRY.test(value)) return false;

    var rearranged = value.slice(4) + value.slice(0, 4);
    var remainder = 0;
    for (var i = 0; i < rearranged.length; i++) {
      var ch = rearranged.charAt(i);
      var digits = ch >= "0" && ch <= "9" ? ch : String(ch.charCodeAt(0) - 55);
      if (!/^\d+$/.test(digits)) return false;
      // Stückweise rechnen, sonst überschreitet die Zahl den Wertebereich.
      remainder = Number(String(remainder) + digits) % 97;
    }
    return remainder === 1;
  }

  /**
   * Sucht eine IBAN im Text. Geschriebene IBAN stehen mal am Stück, mal in
   * Vierergruppen, deshalb werden aufeinanderfolgende Wörter zusammengesetzt
   * und jede Stufe geprüft.
   */
  function findIban(haystack) {
    var tokens = haystack.split(/[^A-Z0-9]+/).filter(Boolean);
    for (var i = 0; i < tokens.length; i++) {
      if (!/^[A-Z]{2}\d{2}/.test(tokens[i])) continue;
      var candidate = "";
      for (var j = i; j < tokens.length && j < i + 9; j++) {
        candidate += tokens[j];
        if (candidate.length > 34) break;
        if (isValidIban(candidate)) return candidate;
      }
    }
    return null;
  }

  function detectAccountName(rows, filename) {
    var haystack = rows
      .slice(0, 40)
      .map(function (row) {
        return row.join(" ");
      })
      .join(" ")
      .toUpperCase();

    var iban = findIban(haystack);
    if (iban) {
      // Nur die letzten vier Stellen anzeigen: identifiziert das Konto
      // eindeutig, ohne die vollständige IBAN in jeder Tabelle zu wiederholen.
      return "Konto ••" + iban.slice(-4);
    }

    var cleaned = filename
      .replace(/\.[^.]+$/, "")
      // Trennzeichen zuerst: ein Unterstrich zählt als Wortzeichen, sonst
      // greifen die Wortgrenzen der folgenden Muster nicht und aus
      // "Auszug_2024" und "Auszug_2025" würden zwei Konten.
      .replace(/[_\-.]+/g, " ")
      .replace(/\b\d{1,4}[ /]\d{1,2}[ /]\d{1,4}\b/g, " ")
      .replace(/\b(19|20)\d{2}\b/g, " ")
      .replace(/\b(kontoauszug|auszug|export|umsaetze|umsatz|umsätze|buchungen|transactions|statement|bis|von|nr|q[1-4]|h[12])\b/gi, " ")
      .replace(/\s+/g, " ")
      .trim();

    // Bleibt nichts Kennzeichnendes übrig (z.B. "Kontoauszug_2024.csv"), ist
    // ein gemeinsamer Name das kleinere Übel: zwei Auszüge desselben Kontos
    // gehören zusammen, und der Name lässt sich pro Datei überschreiben.
    return cleaned || "Konto";
  }

  /* -------------------------------------------------------- Buchungen ---- */

  function buildDescription(row, mapping) {
    var parts = [];
    [mapping.description, mapping.description2].forEach(function (index) {
      if (index == null) return;
      var value = String(row[index] || "").trim();
      if (value && parts.indexOf(value) === -1) parts.push(value);
    });
    return parts.join(" · ").replace(/\s+/g, " ").trim();
  }

  function rowAmount(row, mapping) {
    if (mapping.debit != null || mapping.credit != null) {
      var debit = mapping.debit != null ? parseAmount(row[mapping.debit]) : null;
      var credit = mapping.credit != null ? parseAmount(row[mapping.credit]) : null;
      if (debit) return -Math.abs(debit);
      if (credit) return Math.abs(credit);
      // Keine Belastung und keine Gutschrift: das ist keine eigene Buchung,
      // sondern die Detailzeile einer Sammelbuchung. Sie zu übernehmen würde
      // den Betrag der Sammelbuchung ein zweites Mal zählen.
      return null;
    }
    if (mapping.amount == null) return null;
    return parseAmount(row[mapping.amount]);
  }

  /**
   * Schlüssel für die Dublettenerkennung. Gibt es eine Belegnummer, trägt sie
   * den Schlüssel: sie bleibt über Exporte hinweg gleich, während der
   * Buchungstext je nach Spaltenzuordnung abweichen kann. Sonst identifiziert
   * die Buchung sich über Datum, Betrag und Text.
   */
  function transactionKey(tx) {
    if (tx.reference) return "ref|" + tx.reference.toLowerCase();
    return [tx.dateKey, tx.amount.toFixed(2), tx.description.toLowerCase().replace(/\s+/g, " ")].join("|");
  }

  function toDateKey(date) {
    var m = String(date.getMonth() + 1).padStart(2, "0");
    var d = String(date.getDate()).padStart(2, "0");
    return date.getFullYear() + "-" + m + "-" + d;
  }

  /**
   * Setzt aus Rohzeilen und Zuordnung die Buchungsliste zusammen. Zeilen ohne
   * lesbares Datum oder Betrag landen in `skipped` und werden gemeldet, statt
   * stillschweigend zu verschwinden.
   */
  function buildTransactions(rows, mapping, meta) {
    var dateSamples = rows
      .slice(0, 200)
      .map(function (row) {
        return mapping.date != null ? row[mapping.date] : "";
      })
      .filter(Boolean);
    var parseDate = makeDateParser(dateSamples);

    var transactions = [];
    var skipped = 0;

    rows.forEach(function (row) {
      if (!row.some(function (cell) { return cell !== ""; })) return;

      var date = mapping.date != null ? parseDate(row[mapping.date]) : null;
      var amount = rowAmount(row, mapping);
      if (!date || amount == null || amount === 0) {
        // Auch Zeilen ohne jede brauchbare Angabe zählen: sonst meldet der
        // Import "keine Buchungen erkannt", ohne zu sagen, wie viele Zeilen
        // daran gescheitert sind.
        skipped++;
        return;
      }
      if (meta.invertSign) amount = -amount;

      var tx = {
        date: date,
        dateKey: toDateKey(date),
        month: date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0"),
        amount: amount,
        description: buildDescription(row, mapping) || "(ohne Text)",
        reference: mapping.reference != null ? String(row[mapping.reference] || "").trim() : "",
        balance: mapping.balance != null ? parseAmount(row[mapping.balance]) : null,
        currency:
          (mapping.currency != null && String(row[mapping.currency] || "").trim()) ||
          meta.currency ||
          "CHF",
        account: meta.account,
      };
      tx.key = transactionKey(tx);
      transactions.push(tx);
    });

    transactions.sort(function (a, b) {
      return a.date - b.date;
    });
    return { transactions: transactions, skipped: skipped };
  }

  /**
   * Liest eine Datei komplett: Kodierung, Trennzeichen, Kopfzeile, Zuordnung,
   * Buchungen. Die Vermutungen bleiben im Ergebnis erhalten, damit sie in der
   * Oberfläche angezeigt und korrigiert werden können.
   */
  function readFile(buffer, filename, overrides) {
    var decoded = decode(buffer);
    var delimiter = (overrides && overrides.delimiter) || detectDelimiter(decoded.text);
    var allRows = parseCsv(decoded.text, delimiter);
    if (!allRows.length) throw new Error("Die Datei enthält keine lesbaren Zeilen.");

    var headerIndex = overrides && overrides.headerIndex != null
      ? overrides.headerIndex
      : findHeaderIndex(allRows);

    var header;
    var dataRows;
    if (headerIndex > -1) {
      header = allRows[headerIndex];
      dataRows = allRows.slice(headerIndex + 1);
    } else {
      // Ohne erkennbare Kopfzeile werden Platzhalternamen vergeben.
      header = allRows[0].map(function (_, i) {
        return "Spalte " + (i + 1);
      });
      dataRows = allRows;
    }

    var width = header.length;
    dataRows = dataRows.filter(function (row) {
      return row.some(function (cell) { return cell !== ""; });
    }).map(function (row) {
      var copy = row.slice(0, width);
      while (copy.length < width) copy.push("");
      return copy;
    });

    var mapping = (overrides && overrides.mapping) || mapColumns(header, dataRows);
    var meta = {
      account: (overrides && overrides.account) || detectAccountName(allRows, filename),
      currency: overrides && overrides.currency,
      invertSign: !!(overrides && overrides.invertSign),
    };
    var built = buildTransactions(dataRows, mapping, meta);

    return {
      filename: filename,
      encoding: decoded.encoding,
      delimiter: delimiter,
      headerIndex: headerIndex,
      header: header,
      rowCount: dataRows.length,
      mapping: mapping,
      account: meta.account,
      invertSign: meta.invertSign,
      transactions: built.transactions,
      skipped: built.skipped,
      rawRows: dataRows,
    };
  }

  FB.parse = {
    decode: decode,
    parseCsv: parseCsv,
    detectDelimiter: detectDelimiter,
    findHeaderIndex: findHeaderIndex,
    mapColumns: mapColumns,
    parseAmount: parseAmount,
    makeDateParser: makeDateParser,
    buildTransactions: buildTransactions,
    detectAccountName: detectAccountName,
    readFile: readFile,
    normalizeKey: normalizeKey,
    toDateKey: toDateKey,
  };
})(window.FB || (window.FB = {}));
