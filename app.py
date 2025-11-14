
import os
import sqlite3
from datetime import date as _date
from flask import Flask, render_template, g

DB_PATH = os.path.join(os.path.dirname(__file__), "wellatlas_v4_demo.db")

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def division_class(division):
    return {
        "D": "drilling",
        "P": "domestic",
        "A": "ag",
        "E": "electrical",
    }.get(division, "drilling")

def status_class(status):
    key = (status or "").lower().replace(" ", "-")
    if key == "scheduled":
        return "scheduled"
    if key == "in-progress":
        return "in-progress"
    if key == "on-hold":
        return "on-hold"
    if key == "completed":
        return "completed"
    return "in-progress"

app = Flask(__name__)
app.teardown_appcontext(close_db)

@app.route("/")
def home():
    db = get_db()
    key = os.environ.get("MAPTILER_KEY", "")
    sites = db.execute(
        "SELECT s.id, s.name, s.latitude, s.longitude, c.name AS customer_name "
        "FROM sites s JOIN customers c ON s.customer_id=c.id"
    ).fetchall()

    pins = []
    fill_map = {"D":"#c03540","P":"#d9a441","A":"#2f8f4e","E":"#3e6bd8"}
    for s in sites:
        job = db.execute(
            "SELECT division, job_number FROM jobs WHERE site_id=? ORDER BY id LIMIT 1",
            (s["id"],)
        ).fetchone()
        div = job["division"] if job else "D"
        pins.append({
            "lat": s["latitude"],
            "lng": s["longitude"],
            "customer": s["customer_name"],
            "site": s["name"],
            "division_job": f"{job['division']} {job['job_number']}" if job else "",
            "fill": fill_map.get(div, "#c03540"),
            "border": "#ffffff",
        })

    today = _date(2025, 5, 15).isoformat()
    rows = db.execute(
        "SELECT j.*, s.name AS site_name, c.name AS customer_name "
        "FROM jobs j "
        "JOIN sites s ON j.site_id=s.id "
        "JOIN customers c ON s.customer_id=c.id "
        "WHERE j.start_date=?",
        (today,)
    ).fetchall()

    todays_jobs = []
    for j in rows:
        todays_jobs.append({
            "division": j["division"],
            "division_class": division_class(j["division"]),
            "job_number": j["job_number"],
            "customer_name": j["customer_name"],
            "site_name": j["site_name"],
            "status": j["status"],
            "status_class": status_class(j["status"]),
            "has_attachments": bool(j["has_attachments"]),
        })

    return render_template("index.html", maptiler_key=key, pins=pins, todays_jobs=todays_jobs)

@app.route("/customers")
def customers():
    db = get_db()
    rows = db.execute(
        "SELECT c.id, c.name, "
        "COUNT(DISTINCT s.id) AS site_count, "
        "COUNT(j.id) AS job_count "
        "FROM customers c "
        "LEFT JOIN sites s ON s.customer_id=c.id "
        "LEFT JOIN jobs j ON j.site_id=s.id "
        "GROUP BY c.id ORDER BY c.name"
    ).fetchall()
    return render_template("customers.html", customers=[dict(r) for r in rows])

@app.route("/customers/<int:customer_id>")
def customer_detail(customer_id):
    db = get_db()
    customer = db.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    if not customer:
        return "Customer not found", 404
    sites = db.execute(
        "SELECT s.id, s.name, COUNT(j.id) AS job_count "
        "FROM sites s LEFT JOIN jobs j ON j.site_id=s.id "
        "WHERE s.customer_id=? "
        "GROUP BY s.id ORDER BY s.name",
        (customer_id,)
    ).fetchall()
    jobs = db.execute(
        "SELECT j.*, s.name AS site_name "
        "FROM jobs j JOIN sites s ON j.site_id=s.id "
        "WHERE s.customer_id=? "
        "ORDER BY j.start_date DESC LIMIT 15",
        (customer_id,)
    ).fetchall()

    jobs_view = []
    for j in jobs:
        jobs_view.append({
            "division": j["division"],
            "division_class": division_class(j["division"]),
            "job_number": j["job_number"],
            "site_name": j["site_name"],
            "status": j["status"],
            "status_class": status_class(j["status"]),
            "has_attachments": bool(j["has_attachments"]),
        })

    return render_template(
        "customer_detail.html",
        customer=dict(customer),
        sites=[dict(s) for s in sites],
        jobs=jobs_view,
    )

@app.route("/sites/<int:site_id>")
def site_detail(site_id):
    db = get_db()
    site = db.execute("SELECT * FROM sites WHERE id=?", (site_id,)).fetchone()
    if not site:
        return "Site not found", 404
    customer = db.execute("SELECT * FROM customers WHERE id=?", (site["customer_id"],)).fetchone()
    jobs = db.execute(
        "SELECT * FROM jobs WHERE site_id=? ORDER BY start_date DESC",
        (site_id,)
    ).fetchall()

    jobs_view = []
    for j in jobs:
        jobs_view.append({
            "id": j["id"],
            "division": j["division"],
            "division_class": division_class(j["division"]),
            "job_number": j["job_number"],
            "title": j["title"],
            "status": j["status"],
            "status_class": status_class(j["status"]),
            "has_attachments": bool(j["has_attachments"]),
        })

    attachments = db.execute(
        "SELECT * FROM attachments WHERE site_id=?",
        (site_id,)
    ).fetchall()

    return render_template(
        "site_detail.html",
        site=dict(site),
        customer=dict(customer),
        jobs=jobs_view,
        attachments=[dict(a) for a in attachments],
    )

def build_job_gantt(job):
    start_raw = job["start_date"]
    if not start_raw:
        return None
    start = _date.fromisoformat(start_raw)
    status = job["status"] or ""
    end_raw = job["end_date"]

    if status == "Completed" and end_raw:
        effective_end = _date.fromisoformat(end_raw)
    elif status in ("In Progress", "On Hold"):
        effective_end = _date.today()
    else:  # Scheduled or weird
        effective_end = start

    if effective_end < start:
        effective_end = start

    total_days = max(1, (effective_end - start).days)
    return {
        "start": start.isoformat(),
        "end": effective_end.isoformat(),
        "duration_days": total_days,
        "width": 100,
        "offset": 0,
    }

@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    db = get_db()
    job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        return "Job not found", 404
    site = db.execute("SELECT * FROM sites WHERE id=?", (job["site_id"],)).fetchone()
    customer = db.execute("SELECT * FROM customers WHERE id=?", (site["customer_id"],)).fetchone()
    attachments = db.execute("SELECT * FROM attachments WHERE job_id=?", (job_id,)).fetchall()

    job_view = dict(job)
    job_view["status_class"] = status_class(job["status"])
    job_view["division_class"] = division_class(job["division"])

    gantt = build_job_gantt(job_view)

    return render_template(
        "job_detail.html",
        job=job_view,
        site=dict(site),
        customer=dict(customer),
        attachments=[dict(a) for a in attachments],
        gantt=gantt,
    )

@app.route("/calendar")
def calendar_view():
    db = get_db()
    rows = db.execute(
        "SELECT j.*, s.name AS site_name, c.name AS customer_name "
        "FROM jobs j "
        "JOIN sites s ON j.site_id=s.id "
        "JOIN customers c ON s.customer_id=c.id "
        "WHERE j.start_date IS NOT NULL "
        "ORDER BY j.start_date"
    ).fetchall()

    grouped = {}
    for j in rows:
        day = j["start_date"]
        grouped.setdefault(day, [])
        grouped[day].append({
            "id": j["id"],
            "division": j["division"],
            "division_class": division_class(j["division"]),
            "job_number": j["job_number"],
            "customer_name": j["customer_name"],
            "site_name": j["site_name"],
            "status": j["status"],
            "status_class": status_class(j["status"]),
            "has_attachments": bool(j["has_attachments"]),
        })

    return render_template("calendar.html", grouped=grouped)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
