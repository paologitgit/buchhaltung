/* Finanzblick – Kategorien, Regeln und Erkennung wiederkehrender Zahlungen.
 *
 * Die Kategorisierung ist bewusst simpel und nachvollziehbar: eine geordnete
 * Liste von Stichwortregeln, erste Übereinstimmung gewinnt. Alles ist in der
 * Oberfläche editierbar, damit die Zuordnung zur eigenen Bank passt.
 */
(function (FB) {
  "use strict";

  var CATEGORIES = [
    "Einkommen",
    "Wohnen",
    "Lebensmittel",
    "Restaurant & Ausgang",
    "Transport",
    "Versicherung",
    "Gesundheit",
    "Kommunikation & Abos",
    "Shopping",
    "Freizeit & Reisen",
    "Bildung",
    "Steuern & Gebühren",
    "Bargeld",
    "Umbuchung & Sparen",
    "Sonstiges",
  ];

  /* Stichwörter sind auf den DACH-Raum ausgelegt (CH/DE/AT). Ergänzungen macht
   * man am besten in der Oberfläche – sie landen dann im lokalen Speicher. */
  var DEFAULT_RULES = [
    { pattern: "lohn", category: "Einkommen", sign: "in" },
    { pattern: "salär", category: "Einkommen", sign: "in" },
    { pattern: "gehalt", category: "Einkommen", sign: "in" },
    { pattern: "honorar", category: "Einkommen", sign: "in" },
    { pattern: "rente", category: "Einkommen", sign: "in" },
    { pattern: "ahv", category: "Einkommen", sign: "in" },
    { pattern: "dividende", category: "Einkommen", sign: "in" },
    { pattern: "zinsgutschrift", category: "Einkommen", sign: "in" },
    { pattern: "zins", category: "Einkommen", sign: "in" },
    { pattern: "rückerstattung", category: "Einkommen", sign: "in" },

    { pattern: "miete", category: "Wohnen" },
    { pattern: "mietzins", category: "Wohnen" },
    { pattern: "hypothek", category: "Wohnen" },
    { pattern: "nebenkosten", category: "Wohnen" },
    { pattern: "strom", category: "Wohnen" },
    { pattern: "ewz", category: "Wohnen" },
    { pattern: "energie", category: "Wohnen" },
    { pattern: "stadtwerke", category: "Wohnen" },
    { pattern: "wasser", category: "Wohnen" },
    { pattern: "hausrat", category: "Versicherung" },

    { pattern: "migros", category: "Lebensmittel" },
    { pattern: "coop", category: "Lebensmittel" },
    { pattern: "denner", category: "Lebensmittel" },
    { pattern: "aldi", category: "Lebensmittel" },
    { pattern: "lidl", category: "Lebensmittel" },
    { pattern: "volg", category: "Lebensmittel" },
    { pattern: "spar", category: "Lebensmittel" },
    { pattern: "edeka", category: "Lebensmittel" },
    { pattern: "rewe", category: "Lebensmittel" },
    { pattern: "billa", category: "Lebensmittel" },
    { pattern: "bäckerei", category: "Lebensmittel" },
    { pattern: "metzgerei", category: "Lebensmittel" },
    { pattern: "supermarkt", category: "Lebensmittel" },
    { pattern: "getränke", category: "Lebensmittel" },
    { pattern: "traiteur", category: "Lebensmittel" },

    { pattern: "restaurant", category: "Restaurant & Ausgang" },
    { pattern: "café", category: "Restaurant & Ausgang" },
    { pattern: "cafe", category: "Restaurant & Ausgang" },
    { pattern: "bar", category: "Restaurant & Ausgang" },
    { pattern: "pizzeria", category: "Restaurant & Ausgang" },
    { pattern: "ristorante", category: "Restaurant & Ausgang" },
    { pattern: "trattoria", category: "Restaurant & Ausgang" },
    { pattern: "osteria", category: "Restaurant & Ausgang" },
    { pattern: "grotto", category: "Restaurant & Ausgang" },
    { pattern: "brasserie", category: "Restaurant & Ausgang" },
    { pattern: "gasthof", category: "Restaurant & Ausgang" },
    { pattern: "kantine", category: "Restaurant & Ausgang" },
    { pattern: "mcdonald", category: "Restaurant & Ausgang" },
    { pattern: "burger", category: "Restaurant & Ausgang" },
    { pattern: "starbucks", category: "Restaurant & Ausgang" },
    { pattern: "kebab", category: "Restaurant & Ausgang" },
    { pattern: "kaffee", category: "Restaurant & Ausgang" },
    { pattern: "coffee", category: "Restaurant & Ausgang" },
    { pattern: "beiz", category: "Restaurant & Ausgang" },
    { pattern: "uber eats", category: "Restaurant & Ausgang" },
    { pattern: "eat.ch", category: "Restaurant & Ausgang" },
    { pattern: "lieferando", category: "Restaurant & Ausgang" },

    { pattern: "sbb", category: "Transport" },
    { pattern: "cff", category: "Transport" },
    { pattern: "vbz", category: "Transport" },
    { pattern: "postauto", category: "Transport" },
    { pattern: "deutsche bahn", category: "Transport" },
    { pattern: "db vertrieb", category: "Transport" },
    { pattern: "öbb", category: "Transport" },
    { pattern: "tankstelle", category: "Transport" },
    { pattern: "shell", category: "Transport" },
    { pattern: "socar", category: "Transport" },
    { pattern: "avia", category: "Transport" },
    { pattern: "agrola", category: "Transport" },
    { pattern: "migrol", category: "Transport" },
    { pattern: "parking", category: "Transport" },
    { pattern: "parkhaus", category: "Transport" },
    { pattern: "taxi", category: "Transport" },
    { pattern: "uber", category: "Transport" },
    { pattern: "mobility", category: "Transport" },
    { pattern: "autobahn", category: "Transport" },
    { pattern: "garage", category: "Transport" },
    { pattern: "strassenverkehrsamt", category: "Transport" },

    { pattern: "versicherung", category: "Versicherung" },
    { pattern: "assurance", category: "Versicherung" },
    { pattern: "axa", category: "Versicherung" },
    { pattern: "allianz", category: "Versicherung" },
    { pattern: "zurich vers", category: "Versicherung" },
    { pattern: "mobiliar", category: "Versicherung" },
    { pattern: "helvetia", category: "Versicherung" },
    { pattern: "baloise", category: "Versicherung" },
    { pattern: "suva", category: "Versicherung" },
    { pattern: "krankenkasse", category: "Versicherung" },
    { pattern: "css", category: "Versicherung" },
    { pattern: "helsana", category: "Versicherung" },
    { pattern: "swica", category: "Versicherung" },
    { pattern: "sanitas", category: "Versicherung" },
    { pattern: "concordia", category: "Versicherung" },
    { pattern: "visana", category: "Versicherung" },
    { pattern: "kpt", category: "Versicherung" },
    { pattern: "tk", category: "Versicherung" },
    { pattern: "barmer", category: "Versicherung" },

    { pattern: "apotheke", category: "Gesundheit" },
    { pattern: "pharmacie", category: "Gesundheit" },
    { pattern: "arzt", category: "Gesundheit" },
    { pattern: "praxis", category: "Gesundheit" },
    { pattern: "spital", category: "Gesundheit" },
    { pattern: "klinik", category: "Gesundheit" },
    { pattern: "zahnarzt", category: "Gesundheit" },
    { pattern: "physio", category: "Gesundheit" },
    { pattern: "optik", category: "Gesundheit" },

    { pattern: "swisscom", category: "Kommunikation & Abos" },
    { pattern: "sunrise", category: "Kommunikation & Abos" },
    { pattern: "salt mobile", category: "Kommunikation & Abos" },
    { pattern: "salt", category: "Kommunikation & Abos" },
    { pattern: "wingo", category: "Kommunikation & Abos" },
    { pattern: "telekom", category: "Kommunikation & Abos" },
    { pattern: "vodafone", category: "Kommunikation & Abos" },
    { pattern: "serafe", category: "Kommunikation & Abos" },
    { pattern: "billag", category: "Kommunikation & Abos" },
    { pattern: "rundfunk", category: "Kommunikation & Abos" },
    { pattern: "netflix", category: "Kommunikation & Abos" },
    { pattern: "spotify", category: "Kommunikation & Abos" },
    { pattern: "disney", category: "Kommunikation & Abos" },
    { pattern: "youtube", category: "Kommunikation & Abos" },
    { pattern: "apple.com/bill", category: "Kommunikation & Abos" },
    { pattern: "icloud", category: "Kommunikation & Abos" },
    { pattern: "google", category: "Kommunikation & Abos" },
    { pattern: "microsoft", category: "Kommunikation & Abos" },
    { pattern: "adobe", category: "Kommunikation & Abos" },
    { pattern: "dropbox", category: "Kommunikation & Abos" },
    { pattern: "abonnement", category: "Kommunikation & Abos" },
    { pattern: "abo", category: "Kommunikation & Abos" },

    { pattern: "zalando", category: "Shopping" },
    { pattern: "digitec", category: "Shopping" },
    { pattern: "galaxus", category: "Shopping" },
    { pattern: "amazon", category: "Shopping" },
    { pattern: "ikea", category: "Shopping" },
    { pattern: "h&m", category: "Shopping" },
    { pattern: "c&a", category: "Shopping" },
    { pattern: "manor", category: "Shopping" },
    { pattern: "globus", category: "Shopping" },
    { pattern: "interdiscount", category: "Shopping" },
    { pattern: "media markt", category: "Shopping" },
    { pattern: "mediamarkt", category: "Shopping" },
    { pattern: "otto", category: "Shopping" },
    { pattern: "dm-drogerie", category: "Shopping" },
    { pattern: "müller", category: "Shopping" },

    { pattern: "hotel", category: "Freizeit & Reisen" },
    { pattern: "airbnb", category: "Freizeit & Reisen" },
    { pattern: "booking.com", category: "Freizeit & Reisen" },
    { pattern: "swiss int", category: "Freizeit & Reisen" },
    { pattern: "easyjet", category: "Freizeit & Reisen" },
    { pattern: "lufthansa", category: "Freizeit & Reisen" },
    { pattern: "flug", category: "Freizeit & Reisen" },
    { pattern: "kino", category: "Freizeit & Reisen" },
    { pattern: "fitness", category: "Freizeit & Reisen" },
    { pattern: "sportcenter", category: "Freizeit & Reisen" },
    { pattern: "verein", category: "Freizeit & Reisen" },
    { pattern: "ticketcorner", category: "Freizeit & Reisen" },
    { pattern: "eventim", category: "Freizeit & Reisen" },
    { pattern: "museum", category: "Freizeit & Reisen" },
    { pattern: "lotto", category: "Freizeit & Reisen" },
    { pattern: "schwimmbad", category: "Freizeit & Reisen" },
    { pattern: "bergbahn", category: "Freizeit & Reisen" },
    { pattern: "skipass", category: "Freizeit & Reisen" },

    { pattern: "universität", category: "Bildung" },
    { pattern: "hochschule", category: "Bildung" },
    { pattern: "schule", category: "Bildung" },
    { pattern: "kursgebühr", category: "Bildung" },
    { pattern: "kurs", category: "Bildung" },
    { pattern: "weiterbildung", category: "Bildung" },
    { pattern: "kita", category: "Bildung" },

    { pattern: "steuer", category: "Steuern & Gebühren" },
    { pattern: "steueramt", category: "Steuern & Gebühren" },
    { pattern: "finanzamt", category: "Steuern & Gebühren" },
    { pattern: "gebühr", category: "Steuern & Gebühren" },
    { pattern: "kontoführung", category: "Steuern & Gebühren" },
    { pattern: "jahresgebühr", category: "Steuern & Gebühren" },
    { pattern: "mahngebühr", category: "Steuern & Gebühren" },
    { pattern: "gemeinde", category: "Steuern & Gebühren" },
    { pattern: "betreibung", category: "Steuern & Gebühren" },
    { pattern: "konkursamt", category: "Steuern & Gebühren" },
    { pattern: "notariat", category: "Steuern & Gebühren" },

    { pattern: "bargeldbezug", category: "Bargeld" },
    { pattern: "bancomat", category: "Bargeld" },
    { pattern: "postomat", category: "Bargeld" },
    { pattern: "bankomat", category: "Bargeld" },
    { pattern: "geldautomat", category: "Bargeld" },
    { pattern: "atm", category: "Bargeld" },
    { pattern: "auszahlung schalter", category: "Bargeld" },

    { pattern: "eigenübertrag", category: "Umbuchung & Sparen" },
    { pattern: "übertrag", category: "Umbuchung & Sparen" },
    { pattern: "umbuchung", category: "Umbuchung & Sparen" },
    { pattern: "sparkonto", category: "Umbuchung & Sparen" },
    { pattern: "säule 3a", category: "Umbuchung & Sparen" },
    { pattern: "3a", category: "Umbuchung & Sparen" },
    { pattern: "vorsorge", category: "Umbuchung & Sparen" },
    { pattern: "wertschrift", category: "Umbuchung & Sparen" },
    { pattern: "depot", category: "Umbuchung & Sparen" },
    { pattern: "twint", category: "Sonstiges" },
  ];

  /**
   * Vereinheitlicht Buchungstexte und Stichwörter: Kleinschreibung, Umlaute
   * ausgeschrieben, Satzzeichen zu Leerzeichen. Damit trifft "gebühr" auch
   * "GEBUEHR" und "Coop-Tankstelle" zerfällt in zwei Wörter.
   */
  function normalizeText(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/ä/g, "ae")
      .replace(/ö/g, "oe")
      .replace(/ü/g, "ue")
      .replace(/ß/g, "ss")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function escapeRegex(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  /**
   * Baut den Vergleichsausdruck zu einem Stichwort.
   *
   * Ein Stichwort trifft nur am Wortanfang – sonst landet "Risotto" wegen
   * "otto" beim Versandhaus und "Konkursamt" wegen "kurs" bei der Bildung.
   * Kurze Stichwörter (bis vier Zeichen) müssen zusätzlich am Wortende
   * aufhören, damit "spar" den Supermarkt trifft und nicht das Sparkonto,
   * "bar" die Bar und nicht den Bargeldbezug.
   *
   * Ein führender Stern schaltet auf die alte Suche im ganzen Wort um:
   * "*otto" trifft auch mitten im Wort.
   */
  function patternRegex(pattern) {
    var raw = String(pattern || "");
    var anywhere = raw.charAt(0) === "*";
    var normalized = normalizeText(anywhere ? raw.slice(1) : raw);
    if (!normalized) return null;

    if (anywhere) return new RegExp(escapeRegex(normalized));

    var letters = normalized.replace(/ /g, "");
    var tail = letters.length <= 4 ? "(?= |$)" : "";
    return new RegExp("(?:^| )" + escapeRegex(normalized) + tail);
  }

  function ruleRegex(rule) {
    if (rule.__source !== rule.pattern) {
      rule.__source = rule.pattern;
      rule.__regex = patternRegex(rule.pattern);
    }
    return rule.__regex;
  }

  /** Prüft eine Regel gegen einen bereits normalisierten Buchungstext. */
  function ruleMatches(rule, normalizedText, amount) {
    if (rule.sign === "in" && amount <= 0) return false;
    if (rule.sign === "out" && amount >= 0) return false;
    var regex = ruleRegex(rule);
    return !!regex && regex.test(normalizedText);
  }

  /**
   * Bestimmt die Kategorie. Reihenfolge: manuelle Zuweisung, dann Regeln von
   * oben nach unten, sonst "Einkommen" für Eingänge und "Sonstiges" für Ausgänge.
   */
  function categorize(tx, rules, overrides) {
    if (overrides && overrides[tx.key]) {
      return { category: overrides[tx.key], source: "manuell", rule: null };
    }
    var text = normalizeText(tx.description);
    for (var i = 0; i < rules.length; i++) {
      if (ruleMatches(rules[i], text, tx.amount)) {
        return { category: rules[i].category, source: "regel", rule: rules[i].pattern };
      }
    }
    // Ohne Treffer bleibt die Buchung offen – sichtbar über den Filter
    // "Nicht zugeordnet", damit sie nicht unbemerkt in einer Sammelkategorie
    // verschwindet.
    return {
      category: tx.amount > 0 ? "Einkommen" : "Sonstiges",
      source: "offen",
      rule: null,
    };
  }

  /* ------------------------------------------------ Wiederkehrende Zahlungen */

  /**
   * Reduziert einen Buchungstext auf seinen stabilen Kern: Referenznummern,
   * Datumsangaben und Kartennummern wechseln pro Buchung und müssen raus, damit
   * dieselbe Zahlung über Monate hinweg denselben Schlüssel bekommt.
   */
  function normalizeMerchant(description) {
    return String(description || "")
      .toLowerCase()
      .replace(/\d{1,2}[.\/-]\d{1,2}[.\/-]\d{2,4}/g, " ")
      .replace(/\b[a-z]{0,3}\d[\d\-*x]{3,}\b/g, " ")
      .replace(/\b\d+([.,]\d+)?\b/g, " ")
      .replace(/[^a-zäöüß&. ]/g, " ")
      .replace(/\b(karte|kartenzahlung|einkauf|zahlung|lastschrift|dauerauftrag|gutschrift|belastung|via|ref|referenz|nr|vom|den)\b/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .split(" ")
      .slice(0, 4)
      .join(" ");
  }

  function median(values) {
    var sorted = values.slice().sort(function (a, b) {
      return a - b;
    });
    var mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  }

  /**
   * Findet Ausgaben, die in mindestens drei verschiedenen Monaten mit ähnlichem
   * Betrag auftreten – das sind die Fixkosten, die den Monat bestimmen.
   */
  function detectRecurring(transactions) {
    var groups = {};

    transactions.forEach(function (tx) {
      if (tx.amount >= 0) return;
      var key = normalizeMerchant(tx.description);
      if (key.length < 3) return;
      if (!groups[key]) groups[key] = [];
      groups[key].push(tx);
    });

    var result = [];
    Object.keys(groups).forEach(function (key) {
      var items = groups[key];
      var months = {};
      items.forEach(function (tx) {
        months[tx.month] = true;
      });
      var monthCount = Object.keys(months).length;
      if (monthCount < 3) return;

      var amounts = items.map(function (tx) {
        return Math.abs(tx.amount);
      });
      var typical = median(amounts);
      if (!typical) return;

      var stable = amounts.filter(function (a) {
        return Math.abs(a - typical) <= Math.max(typical * 0.25, 2);
      }).length;
      if (stable < 3) return;

      var total = amounts.reduce(function (sum, a) {
        return sum + a;
      }, 0);
      var last = items[items.length - 1];

      result.push({
        label: items[items.length - 1].description,
        key: key,
        count: items.length,
        months: monthCount,
        typical: typical,
        total: total,
        perMonth: total / monthCount,
        lastDate: last.date,
        category: last.category,
      });
    });

    result.sort(function (a, b) {
      return b.total - a.total;
    });
    return result;
  }

  FB.categories = {
    list: CATEGORIES,
    normalizeText: normalizeText,
    defaultRules: DEFAULT_RULES,
    categorize: categorize,
    normalizeMerchant: normalizeMerchant,
    detectRecurring: detectRecurring,
  };
})(window.FB || (window.FB = {}));
