"""Gig-Finder – findet Auftrittsorte für Musiker in der Schweiz."""
import logging
import threading

from dotenv import load_dotenv

load_dotenv()

from flask import (Flask, Response, abort, redirect, render_template, request,
                   url_for)

from gigfinder import claude_enrich, plz, search, storage
from gigfinder.categories import grouped
from gigfinder.sources import google_places

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = Flask(__name__)

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
    )


@app.route("/search", methods=["POST"])
def start_search():
    plz_code = request.form.get("plz", "").strip()
    if plz.lookup(plz_code) is None:
        return render_template("index.html", groups=grouped(),
                               google_ok=bool(google_places.api_key()),
                               claude_ok=claude_enrich.available(),
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
    return render_template("results.html", r=result)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090, debug=False, threaded=True)
