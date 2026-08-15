/* Finanzblick – Diagramme.
 *
 * Bewusst ohne Bibliothek: das Tool soll offline aus einer einzelnen Ordner-
 * kopie laufen. Alle Diagramme sind handgezeichnetes SVG, reagieren auf die
 * Fenstergrösse und liefern zu jedem Wert eine Tabellenansicht als Alternative
 * zum Hover.
 */
(function (FB) {
  "use strict";

  var NS = "http://www.w3.org/2000/svg";
  var registry = [];

  function el(name, attrs) {
    var node = document.createElementNS(NS, name);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        node.setAttribute(key, attrs[key]);
      });
    }
    return node;
  }

  function text(x, y, content, attrs) {
    var node = el("text", attrs || {});
    node.setAttribute("x", x);
    node.setAttribute("y", y);
    node.textContent = content; // Beschriftungen stammen aus der CSV – nie als HTML einsetzen.
    return node;
  }

  function token(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function theme() {
    return {
      surface: token("--surface-1"),
      grid: token("--grid"),
      axis: token("--axis"),
      muted: token("--muted"),
      textPrimary: token("--text-primary"),
      textSecondary: token("--text-secondary"),
      pos: token("--pos"),
      neg: token("--neg"),
    };
  }

  /** Achsenbeschriftungen sollen auf runden Zahlen liegen, nicht auf Datenwerten. */
  function niceTicks(min, max, count) {
    if (min === max) {
      min = min - 1;
      max = max + 1;
    }
    var span = max - min;
    var rawStep = span / Math.max(count, 1);
    var magnitude = Math.pow(10, Math.floor(Math.log10(Math.abs(rawStep) || 1)));
    var candidates = [1, 2, 2.5, 5, 10];
    var step = magnitude;
    for (var i = 0; i < candidates.length; i++) {
      if (candidates[i] * magnitude >= rawStep) {
        step = candidates[i] * magnitude;
        break;
      }
      step = candidates[candidates.length - 1] * magnitude;
    }
    var start = Math.floor(min / step) * step;
    var end = Math.ceil(max / step) * step;
    var ticks = [];
    for (var v = start; v <= end + step / 1000; v += step) {
      ticks.push(Math.abs(v) < step / 1000 ? 0 : v);
    }
    return ticks;
  }

  /** Balken sind an der Grundlinie eckig und am Datenende abgerundet. */
  function barPath(x, y, w, h, r, side) {
    r = Math.min(r, w / 2, Math.abs(h));
    if (h <= 0.5) return "M" + x + "," + y + "h" + w;
    if (side === "top") {
      return (
        "M" + x + "," + (y + h) +
        "V" + (y + r) +
        "a" + r + "," + r + " 0 0 1 " + r + "," + -r +
        "h" + (w - 2 * r) +
        "a" + r + "," + r + " 0 0 1 " + r + "," + r +
        "V" + (y + h) + "Z"
      );
    }
    if (side === "bottom") {
      return (
        "M" + x + "," + y +
        "V" + (y + h - r) +
        "a" + r + "," + r + " 0 0 0 " + r + "," + r +
        "h" + (w - 2 * r) +
        "a" + r + "," + r + " 0 0 0 " + r + "," + -r +
        "V" + y + "Z"
      );
    }
    // horizontal, Datenende rechts
    return (
      "M" + x + "," + y +
      "h" + Math.max(w - r, 0) +
      "a" + r + "," + r + " 0 0 1 " + r + "," + r +
      "v" + (h - 2 * r) +
      "a" + r + "," + r + " 0 0 1 " + -r + "," + r +
      "H" + x + "Z"
    );
  }

  /* ---------------------------------------------------------- Tooltip ---- */

  function tooltipFor(container) {
    var tip = container.querySelector(".chart-tooltip");
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "chart-tooltip";
      tip.setAttribute("role", "status");
      container.appendChild(tip);
    }
    return tip;
  }

  function showTooltip(container, tip, x, y, rows, title) {
    tip.textContent = "";
    var heading = document.createElement("div");
    heading.className = "chart-tooltip__title";
    heading.textContent = title;
    tip.appendChild(heading);

    rows.forEach(function (row) {
      var line = document.createElement("div");
      line.className = "chart-tooltip__row";
      if (row.color) {
        var key = document.createElement("span");
        key.className = "chart-tooltip__key";
        key.style.background = row.color;
        line.appendChild(key);
      }
      var value = document.createElement("span");
      value.className = "chart-tooltip__value";
      value.textContent = row.value;
      var label = document.createElement("span");
      label.className = "chart-tooltip__label";
      label.textContent = row.label;
      line.appendChild(value);
      line.appendChild(label);
      tip.appendChild(line);
    });

    tip.classList.add("is-visible");
    var bounds = container.getBoundingClientRect();
    var width = tip.offsetWidth;
    var left = Math.min(Math.max(x - width / 2, 4), bounds.width - width - 4);
    tip.style.left = left + "px";
    tip.style.top = Math.max(y - tip.offsetHeight - 12, 4) + "px";
  }

  function hideTooltip(tip) {
    tip.classList.remove("is-visible");
  }

  /* ------------------------------------------------------------ Rahmen --- */

  function prepare(container) {
    var tip = tooltipFor(container);
    Array.prototype.slice.call(container.querySelectorAll("svg")).forEach(function (node) {
      node.remove();
    });
    hideTooltip(tip);
    return { tip: tip, width: Math.max(container.clientWidth, 260) };
  }

  function register(container, render) {
    container.__fbRender = render;
    if (registry.indexOf(container) === -1) registry.push(container);
    render();
  }

  function rerenderAll() {
    registry.forEach(function (container) {
      if (container.isConnected && container.__fbRender) container.__fbRender();
    });
  }

  var resizeTimer = null;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(rerenderAll, 150);
  });

  /* -------------------------------------------------------- Liniendiagramm */

  /**
   * Saldoverlauf. Ein Fadenkreuz sucht den nächsten Punkt auf der X-Achse, damit
   * man auf ein Datum zielen kann statt auf eine 2px-Linie.
   */
  function line(container, opts) {
    register(container, function () {
      var t = theme();
      var frame = prepare(container);
      var points = opts.points;
      if (!points.length) return;

      var width = frame.width;
      var height = opts.height || 260;
      var pad = { top: 16, right: 64, bottom: 28, left: 8 };

      var values = points.map(function (p) {
        return p.y;
      });
      // Der Verlauf soll die Fläche füllen: die Achse folgt den Daten, die
      // Beschriftungen liegen trotzdem auf runden Zahlen innerhalb des Bereichs.
      var minValue = Math.min.apply(null, values);
      var maxValue = Math.max.apply(null, values);
      var padding = (maxValue - minValue) * 0.08 || Math.abs(maxValue || 1) * 0.1;
      var yMin = minValue - padding;
      var yMax = maxValue + padding;
      var ticks = niceTicks(minValue, maxValue, 4).filter(function (tick) {
        return tick >= yMin && tick <= yMax;
      });

      var plotW = width - pad.left - pad.right;
      var plotH = height - pad.top - pad.bottom;
      var xAt = function (i) {
        return pad.left + (points.length === 1 ? plotW / 2 : (i / (points.length - 1)) * plotW);
      };
      var yAt = function (v) {
        return pad.top + plotH - ((v - yMin) / (yMax - yMin || 1)) * plotH;
      };

      var svg = el("svg", {
        viewBox: "0 0 " + width + " " + height,
        width: "100%",
        height: height,
        role: "img",
        "aria-label": opts.ariaLabel || "Verlaufsdiagramm",
      });

      ticks.forEach(function (tick) {
        var y = yAt(tick);
        svg.appendChild(
          el("line", { x1: pad.left, x2: pad.left + plotW, y1: y, y2: y, stroke: tick === 0 ? t.axis : t.grid, "stroke-width": 1 })
        );
        var label = text(pad.left + plotW + 8, y + 4, opts.formatAxis(tick), {
          fill: t.muted, "font-size": 11, "text-anchor": "start",
        });
        label.style.fontVariantNumeric = "tabular-nums";
        svg.appendChild(label);
      });

      var areaPoints = points.map(function (p, i) {
        return xAt(i) + "," + yAt(p.y);
      });
      svg.appendChild(
        el("path", {
          d: "M" + pad.left + "," + yAt(yMin) + " L" + areaPoints.join(" L") + " L" + xAt(points.length - 1) + "," + yAt(yMin) + " Z",
          fill: opts.color || t.pos,
          "fill-opacity": 0.1,
        })
      );
      svg.appendChild(
        el("path", {
          d: "M" + areaPoints.join(" L"),
          fill: "none",
          stroke: opts.color || t.pos,
          "stroke-width": 2,
          "stroke-linejoin": "round",
          "stroke-linecap": "round",
        })
      );

      // X-Achse: höchstens sechs Beschriftungen, sonst kleben sie aneinander.
      var labelCount = Math.min(6, points.length);
      for (var i = 0; i < labelCount; i++) {
        var index = Math.round((i / Math.max(labelCount - 1, 1)) * (points.length - 1));
        var anchor = i === 0 ? "start" : i === labelCount - 1 ? "end" : "middle";
        svg.appendChild(
          text(xAt(index), height - 8, points[index].label, { fill: t.muted, "font-size": 11, "text-anchor": anchor })
        );
      }

      var last = points[points.length - 1];
      svg.appendChild(el("circle", { cx: xAt(points.length - 1), cy: yAt(last.y), r: 5, fill: opts.color || t.pos, stroke: t.surface, "stroke-width": 2 }));

      var crosshair = el("line", { y1: pad.top, y2: pad.top + plotH, stroke: t.axis, "stroke-width": 1, opacity: 0 });
      var marker = el("circle", { r: 5, fill: opts.color || t.pos, stroke: t.surface, "stroke-width": 2, opacity: 0 });
      svg.appendChild(crosshair);
      svg.appendChild(marker);

      var overlay = el("rect", { x: 0, y: 0, width: width, height: height, fill: "transparent" });
      svg.appendChild(overlay);

      function moveTo(event) {
        var rect = svg.getBoundingClientRect();
        var scale = width / rect.width;
        var px = (event.clientX - rect.left) * scale;
        var ratio = (px - pad.left) / (plotW || 1);
        var index = Math.round(ratio * (points.length - 1));
        index = Math.min(Math.max(index, 0), points.length - 1);

        var point = points[index];
        var cx = xAt(index);
        var cy = yAt(point.y);
        crosshair.setAttribute("x1", cx);
        crosshair.setAttribute("x2", cx);
        crosshair.setAttribute("opacity", 1);
        marker.setAttribute("cx", cx);
        marker.setAttribute("cy", cy);
        marker.setAttribute("opacity", 1);

        showTooltip(
          container, frame.tip,
          cx / scale, cy / scale,
          opts.tooltipRows(point),
          point.tooltipTitle || point.label
        );
      }

      overlay.addEventListener("pointermove", moveTo);
      overlay.addEventListener("pointerleave", function () {
        crosshair.setAttribute("opacity", 0);
        marker.setAttribute("opacity", 0);
        hideTooltip(frame.tip);
      });

      container.appendChild(svg);
    });
  }

  /* ------------------------------------------------------ Säulen (Gruppen) */

  /** Einnahmen und Ausgaben je Monat nebeneinander – gleiche Einheit, eine Achse. */
  function groupedColumns(container, opts) {
    register(container, function () {
      var t = theme();
      var frame = prepare(container);
      var groups = opts.groups;
      if (!groups.length) return;

      var width = frame.width;
      var height = opts.height || 280;
      var pad = { top: 16, right: 64, bottom: 30, left: 8 };
      var seriesCount = opts.series.length;

      var maxValue = 0;
      groups.forEach(function (group) {
        group.values.forEach(function (v) {
          maxValue = Math.max(maxValue, v);
        });
      });
      var ticks = niceTicks(0, maxValue, 4);
      var yMax = ticks[ticks.length - 1];

      var plotW = width - pad.left - pad.right;
      var plotH = height - pad.top - pad.bottom;
      var band = plotW / groups.length;
      var gap = 2; // Trennung durch Fläche, nicht durch Rahmen
      var barWidth = Math.min(24, Math.max((band * 0.62 - gap * (seriesCount - 1)) / seriesCount, 3));
      var groupWidth = barWidth * seriesCount + gap * (seriesCount - 1);

      var svg = el("svg", {
        viewBox: "0 0 " + width + " " + height,
        width: "100%",
        height: height,
        role: "img",
        "aria-label": opts.ariaLabel || "Säulendiagramm",
      });

      ticks.forEach(function (tick) {
        var y = pad.top + plotH - (tick / (yMax || 1)) * plotH;
        svg.appendChild(el("line", { x1: pad.left, x2: pad.left + plotW, y1: y, y2: y, stroke: tick === 0 ? t.axis : t.grid, "stroke-width": 1 }));
        var label = text(pad.left + plotW + 8, y + 4, opts.formatAxis(tick), { fill: t.muted, "font-size": 11, "text-anchor": "start" });
        label.style.fontVariantNumeric = "tabular-nums";
        svg.appendChild(label);
      });

      var labelEvery = Math.ceil(groups.length / Math.max(Math.floor(plotW / 56), 1));

      groups.forEach(function (group, gi) {
        var center = pad.left + band * gi + band / 2;
        var start = center - groupWidth / 2;

        group.values.forEach(function (value, si) {
          var h = (value / (yMax || 1)) * plotH;
          var x = start + si * (barWidth + gap);
          var y = pad.top + plotH - h;
          svg.appendChild(
            el("path", { d: barPath(x, y, barWidth, h, 4, "top"), fill: opts.series[si].color })
          );
        });

        if (gi % labelEvery === 0) {
          svg.appendChild(
            text(center, height - 10, group.label, { fill: t.muted, "font-size": 11, "text-anchor": "middle" })
          );
        }

        var hit = el("rect", { x: pad.left + band * gi, y: pad.top, width: band, height: plotH, fill: "transparent" });
        hit.addEventListener("pointerenter", function () {
          var rect = svg.getBoundingClientRect();
          var scale = rect.width / width;
          showTooltip(
            container, frame.tip,
            center * scale, pad.top * scale + 8,
            opts.tooltipRows(group),
            group.tooltipTitle || group.label
          );
        });
        hit.addEventListener("pointerleave", function () {
          hideTooltip(frame.tip);
        });
        svg.appendChild(hit);
      });

      container.appendChild(svg);
    });
  }

  /* -------------------------------------------------- Säulen (Abweichung) */

  /** Monatssaldo: über der Nulllinie Überschuss, darunter Defizit. */
  function divergingColumns(container, opts) {
    register(container, function () {
      var t = theme();
      var frame = prepare(container);
      var groups = opts.groups;
      if (!groups.length) return;

      var width = frame.width;
      var height = opts.height || 220;
      var pad = { top: 16, right: 64, bottom: 30, left: 8 };

      var values = groups.map(function (g) {
        return g.value;
      });
      var ticks = niceTicks(Math.min.apply(null, values.concat(0)), Math.max.apply(null, values.concat(0)), 4);
      var yMin = ticks[0];
      var yMax = ticks[ticks.length - 1];

      var plotW = width - pad.left - pad.right;
      var plotH = height - pad.top - pad.bottom;
      var band = plotW / groups.length;
      var barWidth = Math.min(24, Math.max(band * 0.6, 3));
      var yAt = function (v) {
        return pad.top + plotH - ((v - yMin) / (yMax - yMin || 1)) * plotH;
      };
      var zero = yAt(0);

      var svg = el("svg", {
        viewBox: "0 0 " + width + " " + height,
        width: "100%",
        height: height,
        role: "img",
        "aria-label": opts.ariaLabel || "Abweichungsdiagramm",
      });

      ticks.forEach(function (tick) {
        var y = yAt(tick);
        svg.appendChild(el("line", { x1: pad.left, x2: pad.left + plotW, y1: y, y2: y, stroke: tick === 0 ? t.axis : t.grid, "stroke-width": 1 }));
        var label = text(pad.left + plotW + 8, y + 4, opts.formatAxis(tick), { fill: t.muted, "font-size": 11, "text-anchor": "start" });
        label.style.fontVariantNumeric = "tabular-nums";
        svg.appendChild(label);
      });

      var labelEvery = Math.ceil(groups.length / Math.max(Math.floor(plotW / 56), 1));

      groups.forEach(function (group, gi) {
        var center = pad.left + band * gi + band / 2;
        var x = center - barWidth / 2;
        var value = group.value;
        var y = value >= 0 ? yAt(value) : zero;
        var h = Math.abs(yAt(value) - zero);
        svg.appendChild(
          el("path", {
            d: barPath(x, y, barWidth, h, 4, value >= 0 ? "top" : "bottom"),
            fill: value >= 0 ? t.pos : t.neg,
          })
        );

        if (gi % labelEvery === 0) {
          svg.appendChild(text(center, height - 10, group.label, { fill: t.muted, "font-size": 11, "text-anchor": "middle" }));
        }

        var hit = el("rect", { x: pad.left + band * gi, y: pad.top, width: band, height: plotH, fill: "transparent" });
        hit.addEventListener("pointerenter", function () {
          var rect = svg.getBoundingClientRect();
          var scale = rect.width / width;
          showTooltip(container, frame.tip, center * scale, pad.top * scale + 8, opts.tooltipRows(group), group.label);
        });
        hit.addEventListener("pointerleave", function () {
          hideTooltip(frame.tip);
        });
        svg.appendChild(hit);
      });

      container.appendChild(svg);
    });
  }

  /* ------------------------------------------------------ Balken (liegend) */

  /** Ausgaben je Kategorie – eine Reihe, eine Farbe, Wert am Balkenende. */
  function barsHorizontal(container, opts) {
    register(container, function () {
      var t = theme();
      var frame = prepare(container);
      var items = opts.items;
      if (!items.length) return;

      var width = frame.width;
      var rowHeight = 30;
      var height = items.length * rowHeight + 12;
      var labelWidth = Math.min(Math.max(width * 0.34, 96), 210);
      var valueWidth = 84;
      var plotW = Math.max(width - labelWidth - valueWidth - 8, 20);

      var maxValue = Math.max.apply(
        null,
        items.map(function (item) {
          return item.value;
        })
      );

      var svg = el("svg", {
        viewBox: "0 0 " + width + " " + height,
        width: "100%",
        height: height,
        role: "img",
        "aria-label": opts.ariaLabel || "Balkendiagramm",
      });

      items.forEach(function (item, i) {
        var y = i * rowHeight + 6;
        var barHeight = 16;
        var barY = y + (rowHeight - 12 - barHeight) / 2 + 4;
        var barLength = Math.max((item.value / (maxValue || 1)) * plotW, 2);

        var label = text(labelWidth - 10, barY + barHeight / 2 + 4, item.label, {
          fill: t.textSecondary, "font-size": 12, "text-anchor": "end",
        });
        svg.appendChild(label);

        svg.appendChild(
          el("path", { d: barPath(labelWidth, barY, barLength, barHeight, 4, "right"), fill: opts.color || t.pos })
        );

        var value = text(labelWidth + barLength + 8, barY + barHeight / 2 + 4, opts.formatValue(item.value), {
          fill: t.textPrimary, "font-size": 12, "text-anchor": "start",
        });
        value.style.fontVariantNumeric = "tabular-nums";
        svg.appendChild(value);

        var hit = el("rect", { x: 0, y: y, width: width, height: rowHeight, fill: "transparent" });
        hit.addEventListener("pointerenter", function () {
          var rect = svg.getBoundingClientRect();
          var scale = rect.width / width;
          showTooltip(
            container, frame.tip,
            (labelWidth + barLength / 2) * scale, (barY + 8) * scale,
            opts.tooltipRows(item), item.label
          );
        });
        hit.addEventListener("pointerleave", function () {
          hideTooltip(frame.tip);
        });
        svg.appendChild(hit);
      });

      container.appendChild(svg);
    });
  }

  /* ------------------------------------------------------------- Legende -- */

  function legend(container, series) {
    container.textContent = "";
    series.forEach(function (item) {
      var entry = document.createElement("span");
      entry.className = "legend__item";
      var swatch = document.createElement("span");
      swatch.className = "legend__swatch";
      swatch.style.background = item.color;
      var label = document.createElement("span");
      label.textContent = item.name;
      entry.appendChild(swatch);
      entry.appendChild(label);
      container.appendChild(entry);
    });
  }

  /** Tabellen-Zwilling: jeder Wert bleibt ohne Hover erreichbar. */
  function table(container, headers, rows) {
    container.textContent = "";
    var tableEl = document.createElement("table");
    tableEl.className = "data-table";

    var thead = document.createElement("thead");
    var headRow = document.createElement("tr");
    headers.forEach(function (header) {
      var th = document.createElement("th");
      th.textContent = header.label;
      if (header.numeric) th.className = "is-numeric";
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    tableEl.appendChild(thead);

    var tbody = document.createElement("tbody");
    rows.forEach(function (row) {
      var tr = document.createElement("tr");
      row.forEach(function (cell, i) {
        var td = document.createElement("td");
        td.textContent = cell;
        if (headers[i] && headers[i].numeric) td.className = "is-numeric";
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    tableEl.appendChild(tbody);
    container.appendChild(tableEl);
  }

  FB.charts = {
    line: line,
    groupedColumns: groupedColumns,
    divergingColumns: divergingColumns,
    barsHorizontal: barsHorizontal,
    legend: legend,
    table: table,
    rerenderAll: rerenderAll,
    theme: theme,
  };
})(window.FB || (window.FB = {}));
