"""
Flask web app: dashboard + JSON API + scan/report triggers.

Routes
  GET  /                 -> redirect to /dashboard
  GET  /dashboard        -> HTML dashboard (KPIs, Chart.js chart, findings table)
  GET  /summary          -> JSON totals by type
  GET  /findings         -> JSON of all findings
  GET  /report           -> serves the most recent HTML report
  GET/POST /run-scan         -> runs all 3 agents      (protected if API key set)
  GET/POST /generate-report  -> regenerates the report (protected if API key set)
  GET  /health           -> {"ok": true}   (for Render health checks)

Run locally:  python app.py     then open  http://localhost:5000
"""
import os
from functools import wraps

from flask import (Flask, jsonify, request, redirect,
                   render_template, send_from_directory)

import config
from database import get_client
import run_scan
import report_generator

app = Flask(__name__)

TYPE_LABELS = {
    "contract_gap": "Contract Underbilling",
    "billing_anomaly": "Billing Anomaly",
    "tier_mismatch": "Subscription Tier Mismatch",
}
CHART_COLORS = {
    "contract_gap": "#c0392b",
    "billing_anomaly": "#e67e22",
    "tier_mismatch": "#2980b9",
}


def require_api_key(fn):
    """If DASHBOARD_API_KEY is set in .env, require it in the X-API-Key header.
    If it's blank (local dev), the endpoint is open. This lets the dashboard
    buttons work locally while n8n uses the key in production."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if config.DASHBOARD_API_KEY:
            if request.headers.get("X-API-Key") != config.DASHBOARD_API_KEY:
                return jsonify({"error": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper


def load_summary():
    sb = get_client()
    findings = (sb.table("leakage_findings")
                  .select("*")
                  .order("estimated_loss_usd", desc=True)
                  .execute().data)
    names = {r["customer_id"]: r["customer_name"]
             for r in sb.table("contracts")
                        .select("customer_id, customer_name").execute().data}

    by_type = {k: 0 for k in TYPE_LABELS}
    for f in findings:
        by_type[f["finding_type"]] = by_type.get(f["finding_type"], 0) + \
            float(f["estimated_loss_usd"])
    total = sum(float(f["estimated_loss_usd"]) for f in findings)
    return findings, names, by_type, total


@app.route("/")
def home():
    return redirect("/dashboard")


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/dashboard")
def dashboard():
    findings, names, by_type, total = load_summary()
    rows = [{
        "customer": names.get(f["customer_id"], f["customer_id"]),
        "type": TYPE_LABELS.get(f["finding_type"], f["finding_type"]),
        "amount": float(f["estimated_loss_usd"]),
        "note": (f.get("evidence") or {}).get("note", ""),
        "status": f.get("status", "open"),
    } for f in findings]

    return render_template(
        "dashboard.html",
        total=total,
        count=len(findings),
        by_type={TYPE_LABELS[k]: v for k, v in by_type.items()},
        rows=rows,
        chart_labels=[TYPE_LABELS[k] for k in TYPE_LABELS],
        chart_values=[by_type[k] for k in TYPE_LABELS],
        chart_colors=[CHART_COLORS[k] for k in TYPE_LABELS],
    )


@app.route("/summary")
def summary():
    _, _, by_type, total = load_summary()
    return jsonify({
        "total_usd": round(total, 2),
        "by_type": {TYPE_LABELS[k]: round(v, 2) for k, v in by_type.items()},
    })


@app.route("/findings")
def findings_json():
    findings, names, _, _ = load_summary()
    for f in findings:
        f["customer_name"] = names.get(f["customer_id"], f["customer_id"])
    return jsonify(findings)


@app.route("/report")
def report():
    path = os.path.join(report_generator.REPORTS_DIR, "latest.html")
    if not os.path.exists(path):
        return "No report yet. Trigger /generate-report first.", 404
    return send_from_directory(report_generator.REPORTS_DIR, "latest.html")


@app.route("/run-scan", methods=["GET", "POST"])
@require_api_key
def run_scan_endpoint():
    result = run_scan.run_all()
    result.pop("findings", None)  # keep the API response small
    return jsonify(result)


@app.route("/generate-report", methods=["GET", "POST"])
@require_api_key
def generate_report_endpoint():
    email = request.args.get("email") == "1"  # /generate-report?email=1 also emails it
    result = report_generator.generate(email=email)
    if not result:
        return jsonify({"error": "no findings; run /run-scan first"}), 400
    return jsonify({"total": result["total"], "summary": result["summary"]})


if __name__ == "__main__":
    # debug reloader off so our UTF-8 stdout tweak isn't applied twice.
    app.run(host="0.0.0.0", port=5000, debug=False)
