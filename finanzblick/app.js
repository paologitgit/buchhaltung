/* Finanzblick – Zustand, Oberfläche, Auswertung.
 *
 * Alles läuft im Browser: Dateien werden lokal gelesen, nie hochgeladen. Der
 * Zustand besteht aus den geladenen Dateien, den daraus gebauten Buchungen,
 * den Kategorie-Regeln und den Filtern.
 */
(function (FB) {
  "use strict";

  var STORAGE = {
    rules: "finanzblick.rules",
    overrides: "finanzblick.overrides",
    settings: "finanzblick.settings",
    data: "finanzblick.data",
  };

  var state = {
    files: [],
    transactions: [],
    rules: [],
    overrides: {},
    currency: "CHF",
    filters: {
      range: "all",
      from: null,
      to: null,
      account: "",
      category: "",
      assignment: "",
      search: "",
      excludeTransfers: false,
    },
    persist: false,
    limit: 200,
    nextFileId: 1,
  };

  var $ = function (id) {
    return document.getElementById(id);
  };

  /* ------------------------------------------------------------ Formate -- */

  function money(value, decimals) {
    try {
      return new Intl.NumberFormat("de-CH", {
        style: "currency",
        currency: state.currency,
        minimumFractionDigits: decimals == null ? 2 : decimals,
        maximumFractionDigits: decimals == null ? 2 : decimals,
      }).format(value);
    } catch (e) {
      return value.toFixed(decimals == null ? 2 : decimals) + " " + state.currency;
    }
  }

  /** Achsenbeschriftung: kurze Zahl ohne Währungszeichen, das steht im Titel. */
  function moneyShort(value) {
    var options =
      Math.abs(value) >= 10000
        ? { notation: "compact", maximumFractionDigits: 1 }
        : { maximumFractionDigits: 0 };
    try {
      return new Intl.NumberFormat("de-CH", options).format(value);
    } catch (e) {
      return String(Math.round(value));
    }
  }

  function signedMoney(value) {
    return (value > 0 ? "+" : value < 0 ? "−" : "") + money(Math.abs(value));
  }

  function formatDate(date) {
    return date.toLocaleDateString("de-CH", { day: "2-digit", month: "2-digit", year: "numeric" });
  }

  function monthLabel(monthKey) {
    var parts = monthKey.split("-");
    var date = new Date(+parts[0], +parts[1] - 1, 1);
    return date.toLocaleDateString("de-CH", { month: "short", year: "2-digit" });
  }

  function percent(value) {
    return new Intl.NumberFormat("de-CH", { style: "percent", maximumFractionDigits: 1 }).format(value);
  }

  /* ---------------------------------------------------------- Speicher --- */

  function loadStorage(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      return fallback;
    }
  }

  function saveStorage(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      message("Konnte nicht im Browser speichern (Speicher voll oder gesperrt).", true);
    }
  }

  function persistData() {
    if (!state.persist) {
      try { localStorage.removeItem(STORAGE.data); } catch (e) { /* egal */ }
      return;
    }
    saveStorage(
      STORAGE.data,
      state.files.map(function (file) {
        return {
          filename: file.filename,
          account: file.account,
          transactions: file.transactions.map(function (tx) {
            return {
              d: tx.dateKey,
              a: tx.amount,
              t: tx.description,
              b: tx.balance,
              c: tx.currency,
            };
          }),
        };
      })
    );
  }

  function restoreData() {
    var stored = loadStorage(STORAGE.data, null);
    if (!stored || !stored.length) return false;

    stored.forEach(function (file) {
      var transactions = file.transactions.map(function (raw) {
        var parts = raw.d.split("-");
        var date = new Date(+parts[0], +parts[1] - 1, +parts[2]);
        var tx = {
          date: date,
          dateKey: raw.d,
          month: parts[0] + "-" + parts[1],
          amount: raw.a,
          description: raw.t,
          balance: raw.b,
          currency: raw.c,
          account: file.account,
        };
        tx.key = [tx.dateKey, tx.amount.toFixed(2), tx.description.toLowerCase().replace(/\s+/g, " ")].join("|");
        return tx;
      });
      state.files.push({
        id: state.nextFileId++,
        filename: file.filename,
        account: file.account,
        transactions: transactions,
        restored: true,
        rowCount: transactions.length,
        skipped: 0,
      });
    });
    return true;
  }

  /* --------------------------------------------------------- Meldungen --- */

  function message(content, isError) {
    var box = document.createElement("p");
    box.className = "message" + (isError ? " message--error" : "");
    box.textContent = content;
    $("import-messages").appendChild(box);
  }

  function clearMessages() {
    $("import-messages").textContent = "";
  }

  /* ------------------------------------------------------------ Import -- */

  function readFiles(fileList) {
    clearMessages();
    var files = Array.prototype.slice.call(fileList);
    if (!files.length) return;

    var pending = files.length;
    var added = [];

    function finish() {
      if (--pending > 0) return;
      // Erst nach dem Zusammenführen steht fest, wie viele Buchungen einer
      // Datei schon aus einem früheren Export bekannt waren.
      rebuild();
      added.forEach(function (parsed) {
        if (!parsed.transactions.length) {
          message(
            '"' + parsed.filename + '": keine Buchungen erkannt. Bitte die Spaltenzuordnung unten prüfen.',
            true
          );
          return;
        }
        var parts = [parsed.transactions.length + " Buchungen gelesen"];
        if (parsed.duplicateCount) {
          parts.push(parsed.duplicateCount + " davon schon vorhanden und nicht doppelt gezählt");
        }
        if (parsed.skipped) parts.push(parsed.skipped + " Zeilen übersprungen");
        message('"' + parsed.filename + '": ' + parts.join(", ") + ". Konto: " + parsed.account);
      });
    }

    files.forEach(function (file) {
      var reader = new FileReader();
      reader.onload = function () {
        try {
          var parsed = FB.parse.readFile(reader.result, file.name, null);
          parsed.id = state.nextFileId++;
          state.files.push(parsed);
          added.push(parsed);
        } catch (error) {
          message('"' + file.name + '" konnte nicht gelesen werden: ' + error.message, true);
        }
        finish();
      };
      reader.onerror = function () {
        message('"' + file.name + '" konnte nicht gelesen werden.', true);
        finish();
      };
      reader.readAsArrayBuffer(file);
    });
  }

  /** Baut eine Datei mit geänderter Zuordnung neu auf. */
  function remapFile(file, changes) {
    var mapping = Object.assign({}, file.mapping, changes.mapping || {});
    Object.keys(mapping).forEach(function (role) {
      if (mapping[role] === -1 || mapping[role] == null) delete mapping[role];
    });
    var meta = {
      account: changes.account != null ? changes.account : file.account,
      invertSign: changes.invertSign != null ? changes.invertSign : file.invertSign,
    };
    var built = FB.parse.buildTransactions(file.rawRows, mapping, meta);
    file.mapping = mapping;
    file.account = meta.account;
    file.invertSign = meta.invertSign;
    file.transactions = built.transactions;
    file.skipped = built.skipped;
    rebuild();
  }

  /* ------------------------------------------------------- Neuaufbereitung */

  /**
   * Fasst alle Dateien zusammen, entfernt Dubletten (gleicher Tag, Betrag und
   * Text im selben Konto) und kategorisiert neu.
   */
  function rebuild() {
    var seen = {};
    var all = [];
    var duplicates = 0;

    state.files.forEach(function (file) {
      file.duplicateCount = 0;
      file.transactions.forEach(function (tx) {
        var key = file.account + "|" + tx.key;
        if (seen[key]) {
          duplicates++;
          file.duplicateCount++;
          return;
        }
        seen[key] = true;
        all.push(tx);
      });
    });

    all.sort(function (a, b) {
      return a.date - b.date || a.description.localeCompare(b.description);
    });

    var hits = {};
    all.forEach(function (tx) {
      var result = FB.categories.categorize(tx, state.rules, state.overrides);
      tx.category = result.category;
      tx.categorySource = result.source;
      tx.categoryRule = result.rule;
      if (result.rule) hits[result.rule] = (hits[result.rule] || 0) + 1;
    });
    state.ruleHits = hits;

    state.balanceInfo = computeBalances(all);
    state.transactions = all;
    state.currency = mostCommonCurrency(all);
    state.duplicates = duplicates;
    state.limit = 200;

    persistData();
    renderFileList();
    renderFilterOptions();
    render();
  }

  /**
   * Schreibt jeder Buchung den Kontostand nach ihrer Verbuchung zu.
   *
   * Liefert die Bank eine Saldospalte, wird sie unverändert übernommen. Sonst
   * wird ab dem Beginn der Daten aufsummiert – dann stimmt der Verlauf, nicht
   * aber die absolute Höhe.
   *
   * Gerechnet wird immer über alle Buchungen eines Kontos, nie über die
   * gefilterte Auswahl: der Kontostand einer Buchung hängt an allen Buchungen
   * davor, nicht daran, was gerade angezeigt wird.
   */
  function computeBalances(transactions) {
    var byAccount = {};
    transactions.forEach(function (tx) {
      if (!byAccount[tx.account]) byAccount[tx.account] = [];
      byAccount[tx.account].push(tx);
    });

    var info = {};
    Object.keys(byAccount).forEach(function (account) {
      var list = byAccount[account];
      var fromBank = list.every(function (tx) {
        return typeof tx.balance === "number" && isFinite(tx.balance);
      });
      var running = 0;
      list.forEach(function (tx) {
        running += tx.amount;
        tx.balanceRunning = fromBank ? tx.balance : running;
      });
      info[account] = {
        fromBank: fromBank,
        last: list.length ? list[list.length - 1].balanceRunning : 0,
      };
    });
    return info;
  }

  /** Stammen alle Konten der Auswahl aus einer Saldospalte der Bank? */
  function balancesAreAbsolute(transactions) {
    var info = state.balanceInfo || {};
    var accounts = {};
    transactions.forEach(function (tx) {
      accounts[tx.account] = true;
    });
    var names = Object.keys(accounts);
    return names.length > 0 && names.every(function (account) {
      return info[account] && info[account].fromBank;
    });
  }

  function mostCommonCurrency(transactions) {
    var counts = {};
    transactions.forEach(function (tx) {
      var code = (tx.currency || "CHF").toUpperCase();
      counts[code] = (counts[code] || 0) + 1;
    });
    var best = "CHF";
    var bestCount = 0;
    Object.keys(counts).forEach(function (code) {
      if (counts[code] > bestCount && /^[A-Z]{3}$/.test(code)) {
        best = code;
        bestCount = counts[code];
      }
    });
    return best;
  }

  /* ------------------------------------------------------------ Filter --- */

  function rangeBounds() {
    var filters = state.filters;
    if (!state.transactions.length) return { from: null, to: null };

    var last = state.transactions[state.transactions.length - 1].date;
    var from = null;
    var to = null;

    if (filters.range === "custom") {
      from = filters.from ? new Date(filters.from) : null;
      to = filters.to ? new Date(filters.to) : null;
    } else if (filters.range === "ytd") {
      from = new Date(last.getFullYear(), 0, 1);
    } else if (filters.range === "12m" || filters.range === "6m" || filters.range === "3m") {
      var months = parseInt(filters.range, 10);
      from = new Date(last.getFullYear(), last.getMonth() - months + 1, 1);
    }
    if (to) to.setHours(23, 59, 59, 999);
    return { from: from, to: to };
  }

  function filteredTransactions(options) {
    var filters = state.filters;
    var bounds = rangeBounds();
    var needle = filters.search.trim().toLowerCase();
    // Für den Kontostand zählen nur Zeitraum und Konto: eine Buchung fällt
    // nicht aus dem Saldo, weil gerade nach einer Kategorie gefiltert wird.
    var balanceScope = !!(options && options.balanceScope);

    return state.transactions.filter(function (tx) {
      if (bounds.from && tx.date < bounds.from) return false;
      if (bounds.to && tx.date > bounds.to) return false;
      if (filters.account && tx.account !== filters.account) return false;
      if (balanceScope) return true;
      if (filters.category && tx.category !== filters.category) return false;
      if (filters.assignment && tx.categorySource !== filters.assignment) return false;
      if (filters.excludeTransfers && tx.category === "Umbuchung & Sparen") return false;
      if (needle && tx.description.toLowerCase().indexOf(needle) === -1) return false;
      return true;
    });
  }

  /* ------------------------------------------------------- Aggregationen -- */

  function monthKeysBetween(first, last) {
    var keys = [];
    var year = first.getFullYear();
    var month = first.getMonth();
    var endYear = last.getFullYear();
    var endMonth = last.getMonth();

    while (year < endYear || (year === endYear && month <= endMonth)) {
      keys.push(year + "-" + String(month + 1).padStart(2, "0"));
      month++;
      if (month > 11) {
        month = 0;
        year++;
      }
    }
    return keys;
  }

  function monthlyTotals(transactions) {
    if (!transactions.length) return [];
    var buckets = {};
    transactions.forEach(function (tx) {
      if (!buckets[tx.month]) buckets[tx.month] = { income: 0, expense: 0, count: 0 };
      if (tx.amount > 0) buckets[tx.month].income += tx.amount;
      else buckets[tx.month].expense += -tx.amount;
      buckets[tx.month].count++;
    });

    return monthKeysBetween(transactions[0].date, transactions[transactions.length - 1].date).map(
      function (key) {
        var bucket = buckets[key] || { income: 0, expense: 0, count: 0 };
        return {
          key: key,
          label: monthLabel(key),
          income: bucket.income,
          expense: bucket.expense,
          net: bucket.income - bucket.expense,
          count: bucket.count,
        };
      }
    );
  }

  /**
   * Saldoreihe. Liefert die Bank eine Saldospalte und ist genau ein Konto im
   * Blick, wird der echte Kontostand gezeigt; sonst die aufsummierte
   * Veränderung ab dem Anfang des Zeitraums.
   */
  function balanceSeries(transactions) {
    if (!transactions.length) return { points: [], absolute: false };

    var hasBalance = balancesAreAbsolute(transactions);
    var levels = {}; // letzter bekannter Stand je Konto
    var byDay = {};
    var order = [];

    transactions.forEach(function (tx) {
      if (!byDay[tx.dateKey]) {
        byDay[tx.dateKey] = { date: tx.date, value: 0, change: 0, count: 0 };
        order.push(tx.dateKey);
      }
      byDay[tx.dateKey].change += tx.amount;
      byDay[tx.dateKey].count++;

      // Bei mehreren Konten ist der Gesamtstand die Summe der zuletzt
      // bekannten Stände – ein Konto ohne Buchung an diesem Tag behält seinen.
      levels[tx.account] = tx.balanceRunning;
      var total = 0;
      Object.keys(levels).forEach(function (account) {
        total += levels[account];
      });
      byDay[tx.dateKey].value = total;
    });

    var points = order.map(function (key) {
      var day = byDay[key];
      return {
        x: day.date,
        y: day.value,
        change: day.change,
        count: day.count,
        label: day.date.toLocaleDateString("de-CH", { month: "short", year: "2-digit" }),
        tooltipTitle: formatDate(day.date),
      };
    });

    return { points: points, absolute: hasBalance };
  }

  function categoryTotals(transactions) {
    var buckets = {};
    transactions.forEach(function (tx) {
      if (tx.amount >= 0) return;
      buckets[tx.category] = (buckets[tx.category] || 0) + -tx.amount;
    });
    return Object.keys(buckets)
      .map(function (name) {
        return { label: name, value: buckets[name] };
      })
      .sort(function (a, b) {
        return b.value - a.value;
      });
  }

  function topPayees(transactions, limit) {
    var buckets = {};
    transactions.forEach(function (tx) {
      if (tx.amount >= 0) return;
      var key = FB.categories.normalizeMerchant(tx.description) || tx.description.toLowerCase();
      if (!buckets[key]) {
        buckets[key] = { label: tx.description, total: 0, count: 0, category: tx.category };
      }
      buckets[key].total += -tx.amount;
      buckets[key].count++;
      buckets[key].category = tx.category;
    });
    return Object.keys(buckets)
      .map(function (key) {
        return buckets[key];
      })
      .sort(function (a, b) {
        return b.total - a.total;
      })
      .slice(0, limit);
  }

  /* --------------------------------------------------------- Darstellung -- */

  function render() {
    var hasData = state.transactions.length > 0;
    ["filters", "kpis", "charts", "recurring-card", "top-card", "transactions-card", "rules-card"].forEach(
      function (id) {
        $(id).hidden = !hasData;
      }
    );
    $("clear-button").hidden = !state.files.length;
    if (!hasData) return;

    var transactions = filteredTransactions();
    renderSummary(transactions);
    renderKpis(transactions);
    // Der Saldoverlauf zeigt den echten Kontostand und darf deshalb nicht auf
    // Kategorie, Suche oder Zuordnung reagieren – sonst wäre er die Summe
    // einer Teilmenge und nicht mehr der Kontostand.
    renderCharts(transactions, filteredTransactions({ balanceScope: true }));
    renderRecurring(transactions);
    renderTopPayees(transactions);
    renderTransactions(transactions);
    renderRules();
  }

  function renderSummary(transactions) {
    var parts = [transactions.length + " von " + state.transactions.length + " Buchungen"];
    if (transactions.length) {
      parts.push(
        formatDate(transactions[0].date) + " bis " + formatDate(transactions[transactions.length - 1].date)
      );
    }
    if (state.duplicates) parts.push(state.duplicates + " Dubletten übersprungen");

    var open = transactions.filter(function (tx) {
      return tx.categorySource === "offen";
    }).length;
    if (open) parts.push(open + " ohne passende Regel");

    $("filter-summary").textContent = parts.join(" · ");
  }

  function renderKpis(transactions) {
    var income = 0;
    var expense = 0;
    transactions.forEach(function (tx) {
      if (tx.amount > 0) income += tx.amount;
      else expense += -tx.amount;
    });
    var net = income - expense;

    var months = monthlyTotals(transactions);
    var activeMonths = months.filter(function (m) {
      return m.count > 0;
    }).length || 1;

    var netEl = $("kpi-net");
    netEl.textContent = signedMoney(net);
    netEl.className = "kpi__hero " + (net >= 0 ? "is-positive" : "is-negative");
    $("kpi-net-meta").textContent =
      net >= 0
        ? "Überschuss über " + activeMonths + " Monate mit Buchungen"
        : "Fehlbetrag über " + activeMonths + " Monate mit Buchungen";

    $("kpi-in").textContent = money(income, 0);
    $("kpi-in-meta").textContent = money(income / activeMonths, 0) + " pro Monat";

    $("kpi-out").textContent = money(expense, 0);
    $("kpi-out-meta").textContent =
      transactions.filter(function (tx) { return tx.amount < 0; }).length + " Belastungen";

    $("kpi-burn").textContent = money(expense / activeMonths, 0);
    var medianMonth = months
      .filter(function (m) { return m.count > 0; })
      .map(function (m) { return m.expense; })
      .sort(function (a, b) { return a - b; });
    $("kpi-burn-meta").textContent = medianMonth.length
      ? "Median " + money(medianMonth[Math.floor(medianMonth.length / 2)], 0)
      : "";

    var rate = income > 0 ? net / income : 0;
    var rateEl = $("kpi-rate");
    rateEl.textContent = income > 0 ? percent(rate) : "–";
    rateEl.className = "kpi__value " + (rate >= 0 ? "is-positive" : "is-negative");
    $("kpi-rate-meta").textContent = income > 0 ? "Anteil der Einnahmen, der übrig bleibt" : "Keine Einnahmen im Zeitraum";
  }

  function renderCharts(transactions, balanceTransactions) {
    var t = FB.charts.theme();

    /* Saldoverlauf */
    var balance = balanceSeries(balanceTransactions || transactions);
    $("chart-balance-subtitle").textContent =
      (balance.absolute
        ? "Kontostand laut Saldospalte der Bank"
        : "Aufsummiert ab Beginn der Daten – der Verlauf stimmt, die absolute Höhe nicht") +
      " · nur Zeitraum und Konto wirken hier";

    FB.charts.line($("chart-balance"), {
      points: balance.points,
      color: t.pos,
      height: 260,
      ariaLabel: "Saldoverlauf",
      formatAxis: moneyShort,
      tooltipRows: function (point) {
        return [
          { label: balance.absolute ? "Saldo" : "kumuliert", value: money(point.y, 0), color: t.pos },
          { label: point.count === 1 ? "Buchung" : "Buchungen", value: signedMoney(point.change) },
        ];
      },
    });
    FB.charts.table(
      $("table-balance"),
      [{ label: "Datum" }, { label: "Veränderung", numeric: true }, { label: balance.absolute ? "Saldo" : "Kumuliert", numeric: true }],
      balance.points.map(function (point) {
        return [formatDate(point.x), signedMoney(point.change), money(point.y)];
      })
    );

    /* Einnahmen und Ausgaben pro Monat */
    var months = monthlyTotals(transactions);
    var series = [
      { name: "Einnahmen", color: t.pos },
      { name: "Ausgaben", color: t.neg },
    ];
    FB.charts.legend($("legend-monthly"), series);
    FB.charts.groupedColumns($("chart-monthly"), {
      groups: months.map(function (month) {
        return { label: month.label, values: [month.income, month.expense], month: month };
      }),
      series: series,
      height: 280,
      ariaLabel: "Einnahmen und Ausgaben pro Monat",
      formatAxis: moneyShort,
      tooltipRows: function (group) {
        return [
          { label: "Einnahmen", value: money(group.month.income, 0), color: t.pos },
          { label: "Ausgaben", value: money(group.month.expense, 0), color: t.neg },
          { label: "Netto", value: signedMoney(group.month.net) },
        ];
      },
    });
    FB.charts.table(
      $("table-monthly"),
      [{ label: "Monat" }, { label: "Einnahmen", numeric: true }, { label: "Ausgaben", numeric: true }, { label: "Netto", numeric: true }],
      months.map(function (month) {
        return [month.label, money(month.income), money(month.expense), signedMoney(month.net)];
      })
    );

    /* Monatssaldo */
    FB.charts.divergingColumns($("chart-net"), {
      groups: months.map(function (month) {
        return { label: month.label, value: month.net, month: month };
      }),
      height: 220,
      ariaLabel: "Monatssaldo",
      formatAxis: moneyShort,
      tooltipRows: function (group) {
        return [
          { label: group.value >= 0 ? "Überschuss" : "Fehlbetrag", value: signedMoney(group.value) },
          { label: "Ausgaben", value: money(group.month.expense, 0) },
        ];
      },
    });
    FB.charts.table(
      $("table-net"),
      [{ label: "Monat" }, { label: "Netto", numeric: true }],
      months.map(function (month) {
        return [month.label, signedMoney(month.net)];
      })
    );

    /* Kategorien */
    var categories = categoryTotals(transactions);
    var totalExpense = categories.reduce(function (sum, item) {
      return sum + item.value;
    }, 0);
    // Über acht Kategorien hinaus wird die Restmenge zusammengefasst, statt die
    // Liste beliebig zu verlängern.
    var shown = categories.slice(0, 8);
    if (categories.length > 8) {
      var rest = categories.slice(8).reduce(function (sum, item) {
        return sum + item.value;
      }, 0);
      shown.push({ label: "Übrige (" + (categories.length - 8) + ")", value: rest });
    }
    $("chart-categories-subtitle").textContent = totalExpense
      ? "Summe " + money(totalExpense, 0) + " im gewählten Zeitraum"
      : "Keine Ausgaben im gewählten Zeitraum";

    FB.charts.barsHorizontal($("chart-categories"), {
      items: shown,
      color: t.neg,
      ariaLabel: "Ausgaben nach Kategorie",
      formatValue: function (value) {
        return money(value, 0);
      },
      tooltipRows: function (item) {
        return [
          { label: "Ausgaben", value: money(item.value), color: t.neg },
          { label: "Anteil", value: totalExpense ? percent(item.value / totalExpense) : "–" },
        ];
      },
    });
    FB.charts.table(
      $("table-categories"),
      [{ label: "Kategorie" }, { label: "Ausgaben", numeric: true }, { label: "Anteil", numeric: true }],
      categories.map(function (item) {
        return [item.label, money(item.value), totalExpense ? percent(item.value / totalExpense) : "–"];
      })
    );
  }

  function renderRecurring(transactions) {
    var recurring = FB.categories.detectRecurring(transactions);
    var total = recurring.reduce(function (sum, item) {
      return sum + item.total;
    }, 0);
    // Auf die Länge des Zeitraums bezogen, damit die Zahl mit der Kennzahl
    // "Ausgaben pro Monat" vergleichbar bleibt.
    var periodMonths = monthlyTotals(transactions).length || 1;

    $("recurring-total").textContent = recurring.length
      ? money(total / periodMonths, 0) + " pro Monat"
      : "";
    $("recurring-card").hidden = recurring.length === 0;

    FB.charts.table(
      $("table-recurring"),
      [
        { label: "Zahlung" },
        { label: "Kategorie" },
        { label: "Typisch", numeric: true },
        { label: "Buchungen", numeric: true },
        { label: "Monate", numeric: true },
        { label: "Summe", numeric: true },
        { label: "Zuletzt" },
      ],
      recurring.slice(0, 25).map(function (item) {
        return [
          item.label.length > 60 ? item.label.slice(0, 60) + "…" : item.label,
          item.category,
          money(item.typical),
          String(item.count),
          String(item.months),
          money(item.total),
          formatDate(item.lastDate),
        ];
      })
    );
  }

  function renderTopPayees(transactions) {
    var payees = topPayees(transactions, 15);
    FB.charts.table(
      $("table-top"),
      [{ label: "Empfänger / Text" }, { label: "Kategorie" }, { label: "Buchungen", numeric: true }, { label: "Summe", numeric: true }],
      payees.map(function (item) {
        return [
          item.label.length > 60 ? item.label.slice(0, 60) + "…" : item.label,
          item.category,
          String(item.count),
          money(item.total),
        ];
      })
    );
    $("top-card").hidden = payees.length === 0;
  }

  /** Buchungstabelle mit direkt änderbarer Kategorie. */
  function renderTransactions(transactions) {
    var container = $("table-transactions");
    container.textContent = "";

    var rows = transactions.slice().reverse();
    var visible = rows.slice(0, state.limit);
    var absolute = balancesAreAbsolute(transactions);

    $("transactions-count").textContent =
      transactions.length +
      " Buchungen im Filter · Kategorie in der Tabelle änderbar · Kontostand " +
      (absolute ? "laut Saldospalte der Bank" : "aufsummiert ab Beginn der Daten");

    var table = document.createElement("table");
    table.className = "data-table";

    var thead = document.createElement("thead");
    var headRow = document.createElement("tr");
    ["Datum", "Buchungstext", "Kategorie", "Konto", "Betrag", "Kontostand"].forEach(
      function (label, i) {
        var th = document.createElement("th");
        th.textContent = label;
        if (i >= 4) th.className = "is-numeric";
        if (label === "Kontostand") {
          th.title = absolute
            ? "Kontostand nach dieser Buchung, laut Saldospalte der Bank"
            : "Aufsummiert ab Beginn der Daten – die CSV enthält keine Saldospalte";
        }
        headRow.appendChild(th);
      }
    );
    thead.appendChild(headRow);
    table.appendChild(thead);

    var tbody = document.createElement("tbody");
    visible.forEach(function (tx) {
      var tr = document.createElement("tr");

      var dateCell = document.createElement("td");
      dateCell.textContent = formatDate(tx.date);
      tr.appendChild(dateCell);

      var textCell = document.createElement("td");
      textCell.className = "is-text";
      textCell.textContent = tx.description;
      tr.appendChild(textCell);

      var categoryCell = document.createElement("td");
      var select = document.createElement("select");
      select.className = "table-cell-select";
      select.setAttribute("aria-label", "Kategorie für Buchung vom " + formatDate(tx.date));
      FB.categories.list.forEach(function (name) {
        var option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        if (name === tx.category) option.selected = true;
        select.appendChild(option);
      });
      select.addEventListener("change", function () {
        state.overrides[tx.key] = select.value;
        saveStorage(STORAGE.overrides, state.overrides);
        rebuild();
      });
      // Woher die Kategorie stammt, gehört sichtbar gemacht – sonst lässt sich
      // eine falsche Zuordnung nicht gezielt korrigieren.
      select.title =
        tx.categorySource === "manuell"
          ? "Von Hand gesetzt"
          : tx.categorySource === "regel"
          ? 'Regel "' + tx.categoryRule + '"'
          : "Keine Regel passt – Vorgabe nach Vorzeichen";
      categoryCell.appendChild(select);

      if (tx.categorySource !== "regel") {
        var tag = document.createElement("span");
        tag.className = "tag" + (tx.categorySource === "offen" ? " tag--open" : "");
        tag.textContent = tx.categorySource === "manuell" ? "manuell" : "offen";
        categoryCell.appendChild(document.createTextNode(" "));
        categoryCell.appendChild(tag);
      }

      var ruleButton = document.createElement("button");
      ruleButton.type = "button";
      ruleButton.className = "button button--ghost button--small";
      ruleButton.textContent = "Regel";
      ruleButton.title = "Aus diesem Buchungstext eine Regel bauen";
      ruleButton.addEventListener("click", function () {
        prefillRule(tx);
      });
      categoryCell.appendChild(document.createTextNode(" "));
      categoryCell.appendChild(ruleButton);
      tr.appendChild(categoryCell);

      var accountCell = document.createElement("td");
      accountCell.textContent = tx.account;
      tr.appendChild(accountCell);

      var amountCell = document.createElement("td");
      amountCell.className = "is-numeric " + (tx.amount >= 0 ? "is-positive" : "is-negative");
      amountCell.textContent = signedMoney(tx.amount);
      tr.appendChild(amountCell);

      var balanceCell = document.createElement("td");
      balanceCell.className = "is-numeric";
      balanceCell.textContent =
        typeof tx.balanceRunning === "number" ? money(tx.balanceRunning) : "–";
      tr.appendChild(balanceCell);

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);

    var more = $("more-button");
    more.hidden = rows.length <= state.limit;
    more.textContent = "Weitere " + Math.min(200, rows.length - state.limit) + " Buchungen anzeigen";
  }

  /**
   * Übernimmt den stabilen Kern eines Buchungstextes ins Regelformular. Der
   * Weg von "diese Buchung ist falsch einsortiert" zu "alle Buchungen dieses
   * Händlers sind richtig einsortiert" soll ein Klick sein.
   */
  function prefillRule(tx) {
    var suggestion = FB.categories.normalizeMerchant(tx.description);
    if (!suggestion) suggestion = FB.categories.normalizeText(tx.description).split(" ").slice(0, 2).join(" ");

    $("rule-pattern").value = suggestion;
    $("rule-category").value = tx.category;
    $("rule-sign").value = tx.amount > 0 ? "in" : "out";

    $("rules-card").scrollIntoView({ behavior: "smooth", block: "center" });
    $("rule-pattern").focus();
    $("rule-pattern").select();
  }

  /* ------------------------------------------------------------ Dateien -- */

  function renderFileList() {
    var container = $("file-list");
    container.textContent = "";

    state.files.forEach(function (file) {
      var card = document.createElement("div");
      card.className = "file";

      var head = document.createElement("div");
      head.className = "file__head";

      var left = document.createElement("div");
      var name = document.createElement("p");
      name.className = "file__name";
      name.textContent = file.filename;
      var meta = document.createElement("p");
      meta.className = "file__meta";
      meta.textContent = file.restored
        ? file.transactions.length + " Buchungen (aus dem lokalen Speicher)"
        : [
            file.transactions.length + " Buchungen",
            "Trennzeichen " + (file.delimiter === "\t" ? "Tabulator" : '"' + file.delimiter + '"'),
            file.encoding,
            file.skipped ? file.skipped + " Zeilen übersprungen" : null,
          ].filter(Boolean).join(" · ");
      left.appendChild(name);
      left.appendChild(meta);

      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "button button--ghost button--small";
      remove.textContent = "Entfernen";
      remove.addEventListener("click", function () {
        state.files = state.files.filter(function (item) {
          return item.id !== file.id;
        });
        rebuild();
      });

      head.appendChild(left);
      head.appendChild(remove);
      card.appendChild(head);

      if (!file.restored) card.appendChild(mappingControls(file));
      container.appendChild(card);
    });
  }

  /** Zuordnung von Spalten – die automatische Erkennung ist nur ein Vorschlag. */
  function mappingControls(file) {
    var wrap = document.createElement("div");
    wrap.className = "mapping";

    var roles = [
      { key: "date", label: "Datum" },
      { key: "amount", label: "Betrag" },
      { key: "debit", label: "Belastung" },
      { key: "credit", label: "Gutschrift" },
      { key: "description", label: "Text" },
      { key: "description2", label: "Text (zusätzlich)" },
      { key: "balance", label: "Saldo" },
    ];

    roles.forEach(function (role) {
      var field = document.createElement("label");
      field.className = "field";
      var label = document.createElement("span");
      label.className = "field__label";
      label.textContent = role.label;

      var select = document.createElement("select");
      var none = document.createElement("option");
      none.value = "-1";
      none.textContent = "– keine –";
      select.appendChild(none);

      file.header.forEach(function (columnName, index) {
        var option = document.createElement("option");
        option.value = String(index);
        option.textContent = columnName || "Spalte " + (index + 1);
        if (file.mapping[role.key] === index) option.selected = true;
        select.appendChild(option);
      });

      select.addEventListener("change", function () {
        var changes = { mapping: {} };
        changes.mapping[role.key] = parseInt(select.value, 10);
        remapFile(file, changes);
      });

      field.appendChild(label);
      field.appendChild(select);
      wrap.appendChild(field);
    });

    var accountField = document.createElement("label");
    accountField.className = "field";
    var accountLabel = document.createElement("span");
    accountLabel.className = "field__label";
    accountLabel.textContent = "Kontoname";
    var accountInput = document.createElement("input");
    accountInput.type = "text";
    accountInput.value = file.account;
    accountInput.addEventListener("change", function () {
      remapFile(file, { account: accountInput.value.trim() || file.filename });
    });
    accountField.appendChild(accountLabel);
    accountField.appendChild(accountInput);
    wrap.appendChild(accountField);

    var invertField = document.createElement("label");
    invertField.className = "field";
    var invertLabel = document.createElement("span");
    invertLabel.className = "field__label";
    invertLabel.textContent = "Vorzeichen";
    var invertSelect = document.createElement("select");
    [
      { value: "0", text: "Ausgaben sind negativ" },
      { value: "1", text: "Vorzeichen umkehren" },
    ].forEach(function (item) {
      var option = document.createElement("option");
      option.value = item.value;
      option.textContent = item.text;
      if (file.invertSign === (item.value === "1")) option.selected = true;
      invertSelect.appendChild(option);
    });
    invertSelect.addEventListener("change", function () {
      remapFile(file, { invertSign: invertSelect.value === "1" });
    });
    invertField.appendChild(invertLabel);
    invertField.appendChild(invertSelect);
    wrap.appendChild(invertField);

    return wrap;
  }

  /* ------------------------------------------------------------- Regeln -- */

  function renderRules() {
    var container = $("table-rules");
    container.textContent = "";

    var table = document.createElement("table");
    table.className = "data-table";

    var thead = document.createElement("thead");
    var headRow = document.createElement("tr");
    ["Stichwort", "Kategorie", "Gilt für", "Treffer", ""].forEach(function (label) {
      var th = document.createElement("th");
      th.textContent = label;
      if (label === "Treffer") th.className = "is-numeric";
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    var tbody = document.createElement("tbody");
    state.rules.forEach(function (rule, index) {
      var tr = document.createElement("tr");

      var patternCell = document.createElement("td");
      patternCell.textContent = rule.pattern;
      tr.appendChild(patternCell);

      var categoryCell = document.createElement("td");
      categoryCell.textContent = rule.category;
      tr.appendChild(categoryCell);

      var signCell = document.createElement("td");
      signCell.textContent =
        rule.sign === "in" ? "Einnahmen" : rule.sign === "out" ? "Ausgaben" : "alle";
      tr.appendChild(signCell);

      var hitCell = document.createElement("td");
      hitCell.className = "is-numeric";
      hitCell.textContent = String((state.ruleHits && state.ruleHits[rule.pattern]) || 0);
      tr.appendChild(hitCell);

      var actionCell = document.createElement("td");
      var up = document.createElement("button");
      up.type = "button";
      up.className = "button button--ghost button--small";
      up.textContent = "▲";
      up.title = "Regel nach oben – frühere Regeln gewinnen";
      up.disabled = index === 0;
      up.addEventListener("click", function () {
        var moved = state.rules.splice(index, 1)[0];
        state.rules.splice(index - 1, 0, moved);
        saveStorage(STORAGE.rules, state.rules);
        rebuild();
      });

      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "button button--ghost button--small";
      remove.textContent = "Löschen";
      remove.addEventListener("click", function () {
        state.rules.splice(index, 1);
        saveStorage(STORAGE.rules, state.rules);
        rebuild();
      });

      actionCell.appendChild(up);
      actionCell.appendChild(document.createTextNode(" "));
      actionCell.appendChild(remove);
      tr.appendChild(actionCell);

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);
  }

  /* ------------------------------------------------------------ Auswahl -- */

  function renderFilterOptions() {
    var accounts = {};
    var categories = {};
    state.transactions.forEach(function (tx) {
      accounts[tx.account] = true;
      categories[tx.category] = true;
    });

    fillSelect($("filter-account"), Object.keys(accounts).sort(), "Alle Konten", state.filters.account);
    fillSelect($("filter-category"), Object.keys(categories).sort(), "Alle Kategorien", state.filters.category);
  }

  function fillSelect(select, values, allLabel, current) {
    select.textContent = "";
    var all = document.createElement("option");
    all.value = "";
    all.textContent = allLabel;
    select.appendChild(all);
    values.forEach(function (value) {
      var option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      if (value === current) option.selected = true;
      select.appendChild(option);
    });
  }

  /* ------------------------------------------------------------- Export -- */

  function exportCsv() {
    var rows = [["Datum", "Buchungstext", "Kategorie", "Konto", "Betrag", "Kontostand", "Währung"]];
    filteredTransactions().forEach(function (tx) {
      rows.push([
        tx.dateKey,
        tx.description,
        tx.category,
        tx.account,
        tx.amount.toFixed(2),
        typeof tx.balanceRunning === "number" ? tx.balanceRunning.toFixed(2) : "",
        tx.currency,
      ]);
    });

    var csv = rows
      .map(function (row) {
        return row
          .map(function (cell) {
            var value = String(cell);
            return /[";\n]/.test(value) ? '"' + value.replace(/"/g, '""') + '"' : value;
          })
          .join(";");
      })
      .join("\r\n");

    // BOM, damit Excel die Umlaute richtig liest.
    download(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }), "finanzblick-export.csv");
  }

  function download(blob, filename) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 1000);
  }

  /* -------------------------------------------------------- Beispieldaten */

  /**
   * Erzeugt eine realistische Beispiel-CSV im Schweizer Format und schickt sie
   * durch denselben Import-Weg wie echte Dateien.
   */
  function demoCsv() {
    var seed = 42;
    function random() {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      return seed / 2147483648;
    }
    function amount(base, spread) {
      return (base + (random() - 0.5) * spread).toFixed(2);
    }

    var lines = [
      "Beispielbank – Kontoauszug",
      "Konto;CH00 0000 0000 0000 0000 0",
      "",
      "Datum;Buchungstext;Belastung;Gutschrift;Saldo",
    ];

    var balance = 4200;
    var today = new Date();
    var start = new Date(today.getFullYear(), today.getMonth() - 23, 1); // zwei Jahre

    var fixed = [
      { text: "Mietzins Wohnung Musterstrasse 12", value: 1650, day: 1 },
      { text: "Krankenkasse Helsana Praemie", value: 412.5, day: 3 },
      { text: "Swisscom Mobile Abo", value: 59.9, day: 5 },
      { text: "Serafe Radio und TV", value: 27.9, day: 8 },
      { text: "Netflix.com Abonnement", value: 19.9, day: 12 },
      { text: "Spotify AB Stockholm", value: 12.95, day: 14 },
      { text: "AXA Versicherung Hausrat", value: 38.4, day: 18 },
      { text: "Dauerauftrag Sparkonto Eigenuebertrag", value: 500, day: 25 },
    ];

    var variable = [
      { text: "Migros Supermarkt Zuerich", base: 62, spread: 45, perMonth: 7 },
      { text: "Coop Pronto Tankstelle", base: 74, spread: 40, perMonth: 2 },
      { text: "Restaurant Sonne Mittagsmenu", base: 24, spread: 14, perMonth: 5 },
      { text: "SBB Billett Fernverkehr", base: 38, spread: 30, perMonth: 3 },
      { text: "Bargeldbezug Bancomat Hauptbahnhof", base: 100, spread: 60, perMonth: 2 },
      { text: "Digitec Galaxus AG Onlinekauf", base: 89, spread: 120, perMonth: 1 },
      { text: "Apotheke Zentrum", base: 34, spread: 25, perMonth: 1 },
      { text: "Kaffee Kiosk Karte", base: 6, spread: 4, perMonth: 6 },
    ];

    function push(date, textValue, debit, credit) {
      balance += credit ? +credit : -debit;
      lines.push(
        [
          String(date.getDate()).padStart(2, "0") + "." + String(date.getMonth() + 1).padStart(2, "0") + "." + date.getFullYear(),
          textValue,
          debit ? formatSwiss(debit) : "",
          credit ? formatSwiss(credit) : "",
          formatSwiss(balance),
        ].join(";")
      );
    }

    function formatSwiss(value) {
      var num = Number(value);
      var parts = Math.abs(num).toFixed(2).split(".");
      parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, "'");
      return (num < 0 ? "-" : "") + parts.join(".");
    }

    var cursor = new Date(start);
    while (cursor <= today) {
      var year = cursor.getFullYear();
      var month = cursor.getMonth();
      var entries = [];

      entries.push({ day: 25, text: "Lohnzahlung Muster AG Salaer", credit: amount(6400, 300) });
      if (month === 11) entries.push({ day: 20, text: "Lohnzahlung Muster AG 13. Monatslohn", credit: amount(5900, 200) });
      if (month === 2) entries.push({ day: 14, text: "Steueramt Kanton Steuern Rate", debit: amount(1450, 300) });
      if (month === 8) entries.push({ day: 9, text: "Steueramt Kanton Steuern Rate", debit: amount(1450, 300) });
      if (month === 6) entries.push({ day: 11, text: "Hotel Seeblick Ferien", debit: amount(890, 200) });
      if (month === 6) entries.push({ day: 3, text: "Swiss International Air Lines Flug", debit: amount(520, 160) });

      fixed.forEach(function (item) {
        entries.push({ day: item.day, text: item.text, debit: item.value.toFixed(2) });
      });

      variable.forEach(function (item) {
        for (var i = 0; i < item.perMonth; i++) {
          entries.push({
            day: 1 + Math.floor(random() * 27),
            text: item.text,
            debit: amount(item.base, item.spread),
          });
        }
      });

      entries
        .sort(function (a, b) {
          return a.day - b.day;
        })
        .forEach(function (entry) {
          var date = new Date(year, month, entry.day);
          if (date > today) return;
          push(date, entry.text, entry.debit, entry.credit);
        });

      cursor = new Date(year, month + 1, 1);
    }

    return lines.join("\n");
  }

  function loadDemo() {
    clearMessages();
    var text = demoCsv();
    var bytes = new TextEncoder().encode(text);
    try {
      var parsed = FB.parse.readFile(bytes.buffer, "Beispieldaten.csv", null);
      parsed.id = state.nextFileId++;
      parsed.account = "Beispielkonto";
      parsed.transactions.forEach(function (tx) {
        tx.account = "Beispielkonto";
      });
      state.files.push(parsed);
      message("Beispieldaten geladen: " + parsed.transactions.length + " Buchungen.");
      rebuild();
    } catch (error) {
      message("Beispieldaten konnten nicht erzeugt werden: " + error.message, true);
    }
  }

  /* ------------------------------------------------------------ Ereignisse */

  function bindImport() {
    var dropzone = $("dropzone");
    var input = $("file-input");

    dropzone.addEventListener("click", function () {
      input.click();
    });
    dropzone.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        input.click();
      }
    });
    input.addEventListener("change", function () {
      readFiles(input.files);
      input.value = "";
    });

    ["dragenter", "dragover"].forEach(function (type) {
      dropzone.addEventListener(type, function (event) {
        event.preventDefault();
        dropzone.classList.add("is-over");
      });
    });
    ["dragleave", "drop"].forEach(function (type) {
      dropzone.addEventListener(type, function (event) {
        event.preventDefault();
        dropzone.classList.remove("is-over");
      });
    });
    dropzone.addEventListener("drop", function (event) {
      if (event.dataTransfer && event.dataTransfer.files.length) readFiles(event.dataTransfer.files);
    });

    $("demo-button").addEventListener("click", loadDemo);
    $("clear-button").addEventListener("click", function () {
      state.files = [];
      clearMessages();
      rebuild();
    });

    $("persist-toggle").addEventListener("change", function (event) {
      state.persist = event.target.checked;
      saveStorage(STORAGE.settings, { persist: state.persist, theme: document.documentElement.dataset.theme || "" });
      persistData();
    });
  }

  function bindFilters() {
    $("filter-range").addEventListener("change", function (event) {
      state.filters.range = event.target.value;
      var custom = state.filters.range === "custom";
      $("field-from").hidden = !custom;
      $("field-to").hidden = !custom;
      render();
    });
    $("filter-from").addEventListener("change", function (event) {
      state.filters.from = event.target.value || null;
      render();
    });
    $("filter-to").addEventListener("change", function (event) {
      state.filters.to = event.target.value || null;
      render();
    });
    $("filter-account").addEventListener("change", function (event) {
      state.filters.account = event.target.value;
      render();
    });
    $("filter-category").addEventListener("change", function (event) {
      state.filters.category = event.target.value;
      render();
    });
    $("filter-assignment").addEventListener("change", function (event) {
      state.filters.assignment = event.target.value;
      state.limit = 200;
      render();
    });
    $("filter-exclude-transfers").addEventListener("change", function (event) {
      state.filters.excludeTransfers = event.target.checked;
      render();
    });

    var searchTimer = null;
    $("filter-search").addEventListener("input", function (event) {
      clearTimeout(searchTimer);
      var value = event.target.value;
      searchTimer = setTimeout(function () {
        state.filters.search = value;
        state.limit = 200;
        render();
      }, 180);
    });

    $("filter-reset").addEventListener("click", function () {
      state.filters = {
        range: "all", from: null, to: null, account: "", category: "",
        assignment: "", search: "", excludeTransfers: false,
      };
      $("filter-range").value = "all";
      $("filter-from").value = "";
      $("filter-to").value = "";
      $("filter-account").value = "";
      $("filter-category").value = "";
      $("filter-assignment").value = "";
      $("filter-search").value = "";
      $("filter-exclude-transfers").checked = false;
      $("field-from").hidden = true;
      $("field-to").hidden = true;
      render();
    });

    $("more-button").addEventListener("click", function () {
      state.limit += 200;
      render();
    });
    $("export-button").addEventListener("click", exportCsv);
  }

  function bindRules() {
    $("rule-form").addEventListener("submit", function (event) {
      event.preventDefault();
      var pattern = $("rule-pattern").value.trim().toLowerCase();
      if (!pattern) return;
      state.rules.unshift({
        pattern: pattern,
        category: $("rule-category").value,
        sign: $("rule-sign").value,
      });
      saveStorage(STORAGE.rules, state.rules);
      $("rule-pattern").value = "";
      rebuild();
    });

    $("rules-reset").addEventListener("click", function () {
      state.rules = FB.categories.defaultRules.slice();
      saveStorage(STORAGE.rules, state.rules);
      rebuild();
    });

    $("rules-export").addEventListener("click", function () {
      download(
        new Blob([JSON.stringify({ rules: state.rules, overrides: state.overrides }, null, 2)], {
          type: "application/json",
        }),
        "finanzblick-regeln.json"
      );
    });

    $("rules-import-button").addEventListener("click", function () {
      $("rules-import").click();
    });

    $("rules-import").addEventListener("change", function (event) {
      var file = event.target.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        try {
          var data = JSON.parse(reader.result);
          if (Array.isArray(data.rules)) state.rules = data.rules;
          if (data.overrides) state.overrides = data.overrides;
          saveStorage(STORAGE.rules, state.rules);
          saveStorage(STORAGE.overrides, state.overrides);
          rebuild();
          message("Regeln übernommen.");
        } catch (error) {
          message("Regeldatei konnte nicht gelesen werden.", true);
        }
      };
      reader.readAsText(file);
      event.target.value = "";
    });
  }

  function bindTableToggles() {
    Array.prototype.slice.call(document.querySelectorAll("[data-table-toggle]")).forEach(function (button) {
      button.addEventListener("click", function () {
        var target = $(button.getAttribute("data-table-toggle"));
        target.hidden = !target.hidden;
        button.textContent = target.hidden ? "Tabelle" : "Tabelle ausblenden";
      });
    });
  }

  function bindTheme() {
    $("theme-toggle").addEventListener("click", function () {
      var current = document.documentElement.dataset.theme;
      var next = current === "dark" ? "light" : current === "light" ? "" : "dark";
      if (next) document.documentElement.dataset.theme = next;
      else delete document.documentElement.dataset.theme;
      saveStorage(STORAGE.settings, { persist: state.persist, theme: next });
      FB.charts.rerenderAll();
      render();
    });

    if (window.matchMedia) {
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
        if (!document.documentElement.dataset.theme) render();
      });
    }
  }

  /* --------------------------------------------------------------- Start -- */

  function init() {
    var settings = loadStorage(STORAGE.settings, { persist: false, theme: "" });
    if (settings.theme) document.documentElement.dataset.theme = settings.theme;
    state.persist = !!settings.persist;
    $("persist-toggle").checked = state.persist;

    state.rules = loadStorage(STORAGE.rules, null) || FB.categories.defaultRules.slice();
    state.overrides = loadStorage(STORAGE.overrides, {}) || {};

    var ruleCategory = $("rule-category");
    FB.categories.list.forEach(function (name) {
      var option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      if (name === "Lebensmittel") option.selected = true;
      ruleCategory.appendChild(option);
    });

    bindImport();
    bindFilters();
    bindRules();
    bindTableToggles();
    bindTheme();

    if (state.persist && restoreData()) rebuild();
    else render();
  }

  document.addEventListener("DOMContentLoaded", init);
})(window.FB || (window.FB = {}));
