// Sortiert Tabellenspalten mit data-sort ("text" oder "num") per Klick.
// Der Spaltenindex kommt aus cellIndex, damit zusätzliche Spalten
// (z. B. Auswahl-Kästchen) die Zuordnung nicht verschieben.
document.querySelectorAll("table th[data-sort]").forEach(th => {
  th.addEventListener("click", () => {
    const table = th.closest("table");
    const tbody = table.querySelector("tbody");
    const rows = [...tbody.querySelectorAll("tr")];
    const idx = th.cellIndex;
    const numeric = th.dataset.sort === "num";
    const asc = th.dataset.asc !== "true";
    table.querySelectorAll("th[data-sort]").forEach(other => {
      if (other !== th) delete other.dataset.asc;
    });
    th.dataset.asc = asc;
    rows.sort((a, b) => {
      const ca = a.cells[idx], cb = b.cells[idx];
      const va = numeric ? parseFloat(ca.dataset.value ?? ca.textContent)
                         : (ca.dataset.value ?? ca.textContent).trim().toLowerCase();
      const vb = numeric ? parseFloat(cb.dataset.value ?? cb.textContent)
                         : (cb.dataset.value ?? cb.textContent).trim().toLowerCase();
      return (va < vb ? -1 : va > vb ? 1 : 0) * (asc ? 1 : -1);
    });
    rows.forEach(row => tbody.appendChild(row));
  });
});

// Hinweis einblenden, wenn die Tabelle breiter ist als das Fenster –
// sonst übersieht man die Spalten am rechten Rand.
document.querySelectorAll(".table-wrap").forEach(wrap => {
  const hinweis = document.createElement("p");
  hinweis.className = "scroll-hint";
  hinweis.textContent = "→ Die Tabelle lässt sich seitlich scrollen; rechts stehen weitere Spalten.";
  wrap.after(hinweis);
  const pruefen = () => {
    hinweis.style.display = wrap.scrollWidth > wrap.clientWidth + 2 ? "" : "none";
  };
  pruefen();
  window.addEventListener("resize", pruefen);
  wrap.addEventListener("scroll", () => {
    const amEnde = wrap.scrollLeft + wrap.clientWidth >= wrap.scrollWidth - 2;
    hinweis.style.visibility = amEnde ? "hidden" : "visible";
  });
});

// "Alle auswählen"-Kästchen im Tabellenkopf
const toggleAll = document.getElementById("alle-auswaehlen");
if (toggleAll) {
  const boxes = () => [...document.querySelectorAll(
    'tbody input[type=checkbox][name="auswahl"]:not(:disabled)')];
  toggleAll.addEventListener("change", () => {
    boxes().forEach(box => { box.checked = toggleAll.checked; });
  });
  document.querySelectorAll('tbody input[type=checkbox][name="auswahl"]')
    .forEach(box => box.addEventListener("change", () => {
      const all = boxes();
      toggleAll.checked = all.length > 0 && all.every(b => b.checked);
    }));
}
