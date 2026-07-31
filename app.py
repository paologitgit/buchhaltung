"""Gig-Finder – findet Auftrittsorte für Musiker in der Schweiz."""
import logging
import os
import secrets
import threading

from dotenv import load_dotenv

load_dotenv()

from flask import (Flask, Response, abort, flash, redirect, render_template,
                   request, url_for)

from gigfinder import addressbook, claude_enrich, plz, search, storage
from gigfinder.categories import grouped
from gigfinder.sources import google_places

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = Flask(__name__)
# nur für Flash-Meldungen; die App verwaltet keine Logins
app.secret_key = os.environ.get("FLASK_SECRET") or secrets.token_hex(16)

# Laufende Suchen (In-Memory; die App läuft in einem einzelnen Prozess)
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _run_job(job_id: str, plz_code: str, radius_km: int, keys: list[str],
             use_google: bool, use_claude: bool):
    job = _jobs[job_id]

    def progress(msg: str):
        job["messages"].append(msg)

    try:
        result = search.run_search(plz_code, radius_km, keys,
                                   use_google=use_google, use_claude=use_claude,
                                   progress=progress)
        job["result_id"] = storage.save(result)
        job["status"] = "done"
    except Exception as exc:
        logging.exception("Suche fehlgeschlagen")
        job["status"] = "error"
        job["error"] = str(exc)


@app.route("/")
def index():
    return render_template(
        "index.html",
        groups=grouped(),
        google_ok=bool(google_places.api_key()),
        claude_ok=claude_enrich.available(),
        claude_model=claude_enrich.model_name(),
    )


@app.route("/search", methods=["POST"])
def start_search():
    plz_code = request.form.get("plz", "").strip()
    if plz.lookup(plz_code) is None:
        return render_template("index.html", groups=grouped(),
                               google_ok=bool(google_places.api_key()),
                               claude_ok=claude_enrich.available(),
                               claude_model=claude_enrich.model_name(),
                               error=f"«{plz_code}» ist keine bekannte Schweizer PLZ."), 400
    try:
        radius_km = max(1, min(50, int(request.form.get("radius", "20"))))
    except ValueError:
        radius_km = 20
    keys = request.form.getlist("kategorien")
    if not keys:
        return render_template("index.html", groups=grouped(),
                               google_ok=bool(google_places.api_key()),
                               claude_ok=claude_enrich.available(),
                               claude_model=claude_enrich.model_name(),
                               error="Bitte mindestens eine Kategorie wählen."), 400

    import uuid
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {"status": "running", "messages": [], "result_id": None}
    threading.Thread(
        target=_run_job,
        args=(job_id, plz_code, radius_km, keys,
              request.form.get("google") == "on",
              request.form.get("claude") == "on"),
        daemon=True,
    ).start()
    return redirect(url_for("wait", job_id=job_id))


@app.route("/wait/<job_id>")
def wait(job_id):
    if job_id not in _jobs:
        abort(404)
    return render_template("wait.html", job_id=job_id)


@app.route("/status/<job_id>")
def status(job_id):
    job = _jobs.get(job_id)
    if job is None:
        abort(404)
    return {
        "status": job["status"],
        "messages": job["messages"][-5:],
        "result_id": job["result_id"],
        "error": job.get("error"),
    }


@app.route("/results/<search_id>")
def results(search_id):
    result = storage.load(search_id)
    if result is None:
        abort(404)
    return render_template(
        "results.html", r=result,
        gespeichert=addressbook.already_saved(result.get("locations", [])),
    )


@app.route("/results/<search_id>/uebernehmen", methods=["POST"])
def results_uebernehmen(search_id):
    result = storage.load(search_id)
    if result is None:
        abort(404)
    locations = result.get("locations", [])
    auswahl = []
    for raw in request.form.getlist("auswahl"):
        try:
            index = int(raw)
        except ValueError:
            continue
        if 0 <= index < len(locations):
            auswahl.append(locations[index])
    if not auswahl:
        flash("Es war keine Location ausgewählt.", "error")
        return redirect(url_for("results", search_id=search_id))

    stats = addressbook.add_entries(
        [addressbook.entry_from_location(loc) for loc in auswahl])
    wort = "Adresse" if stats["neu"] == 1 else "Adressen"
    teile = [f"{stats['neu']} {wort} ins Adressbuch übernommen"]
    if stats["ergaenzt"]:
        teile.append(f"{stats['ergaenzt']} bestehende ergänzt")
    if stats["uebersprungen"]:
        teile.append(f"{stats['uebersprungen']} bereits vorhanden")
    flash(", ".join(teile) + ".", "ok")
    return redirect(url_for("results", search_id=search_id))


@app.route("/results/<search_id>/csv")
def results_csv(search_id):
    result = storage.load(search_id)
    if result is None:
        abort(404)
    filename = f"gig-finder_{result['plz']}_{result['radius_km']}km.csv"
    return Response(
        storage.to_csv(result),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/claude-test", methods=["POST"])
def claude_test():
    """Prüft den Claude-Zugang mit einer einzigen kleinen Anfrage."""
    fehler = claude_enrich.check_access()
    if fehler:
        flash(f"Claude-Test fehlgeschlagen: {fehler}", "error")
    else:
        flash(f"Claude-Zugang funktioniert (Modell {claude_enrich.model_name()}). "
              "Beschreibungen werden erstellt.", "ok")
    return redirect(url_for("index"))


@app.route("/adressbuch")
def adressbuch():
    return render_template("adressbuch.html", eintraege=addressbook.list_all())


@app.route("/adressbuch/import", methods=["POST"])
def adressbuch_import():
    upload = request.files.get("datei")
    if upload is None or not upload.filename:
        flash("Bitte eine CSV-Datei auswählen.", "error")
        return redirect(url_for("adressbuch"))
    try:
        stats = addressbook.import_csv(upload.read())
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("adressbuch"))
    except Exception:
        logging.exception("CSV-Import fehlgeschlagen")
        flash("Die Datei konnte nicht gelesen werden.", "error")
        return redirect(url_for("adressbuch"))
    teile = [f"{stats['neu']} neu importiert"]
    if stats["ergaenzt"]:
        teile.append(f"{stats['ergaenzt']} bestehende ergänzt")
    if stats["uebersprungen"]:
        teile.append(f"{stats['uebersprungen']} Duplikate übersprungen")
    if stats["fehler"]:
        teile.append(f"{stats['fehler']} Zeilen ohne Namen ignoriert")
    flash(", ".join(teile) + ".", "ok")
    return redirect(url_for("adressbuch"))


@app.route("/adressbuch/csv")
def adressbuch_csv():
    return Response(
        addressbook.to_csv(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="adressbuch.csv"'},
    )


@app.route("/adressbuch/loeschen/<int:entry_id>", methods=["POST"])
def adressbuch_loeschen(entry_id):
    addressbook.delete(entry_id)
    flash("Eintrag gelöscht.", "ok")
    return redirect(url_for("adressbuch"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090, debug=False, threaded=True)
