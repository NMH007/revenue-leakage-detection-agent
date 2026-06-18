"""
Agent 4 - Report Generator.

Pulls every finding from leakage_findings, ranks them by dollar value, asks the
LLM to write a plain-English executive summary, then renders a polished HTML
report into the reports/ folder. (Email delivery is added next.)

Run:  python report_generator.py
"""
import json
import os
from datetime import datetime

from database import get_client
import llm_client

REPORTS_DIR = "reports"

TYPE_LABELS = {
    "contract_gap": "Contract Underbilling",
    "billing_anomaly": "Billing Anomaly",
    "tier_mismatch": "Subscription Tier Mismatch",
}

SUMMARY_PROMPT = (
    "You are a senior revenue analyst. Below is JSON of revenue-leakage findings "
    "detected today across our customer base. Write a concise executive summary "
    "for company leadership with exactly these parts:\n"
    "1. A one-sentence headline stating the total estimated annual leakage.\n"
    "2. 'Top 3 urgent items:' as a short list - each with the customer, the "
    "issue, the dollar amount, and ONE recommended action.\n"
    "3. A one-sentence closing note on the overall pattern.\n"
    "Plain English, under 220 words, no markdown symbols or headers.\n\n"
    "Findings JSON:\n{findings}"
)

# CSS kept out of f-strings so its { } braces don't confuse Python formatting.
STYLE = """
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif;
         background:#f4f5f7; color:#1a1a2e; margin:0; padding:24px; }
  .wrap { max-width:760px; margin:0 auto; background:#fff; border-radius:14px;
          overflow:hidden; box-shadow:0 6px 24px rgba(0,0,0,.08); }
  .head { background:linear-gradient(135deg,#1a1a2e,#16213e); color:#fff;
          padding:28px 32px; }
  .head h1 { margin:0; font-size:22px; }
  .head p  { margin:6px 0 0; opacity:.8; font-size:13px; }
  .kpi { text-align:center; padding:28px 16px; border-bottom:1px solid #eee; }
  .kpi .big { font-size:44px; font-weight:800; color:#c0392b; }
  .kpi .lbl { font-size:13px; color:#666; text-transform:uppercase;
              letter-spacing:1px; }
  .cards { display:flex; gap:12px; padding:20px 24px; }
  .card { flex:1; background:#f8f9fb; border-radius:10px; padding:14px;
          text-align:center; }
  .card .n { font-size:22px; font-weight:700; }
  .card .t { font-size:12px; color:#777; margin-top:4px; }
  .summary { padding:8px 32px 24px; line-height:1.6; font-size:15px; }
  .summary h2 { font-size:16px; color:#16213e; }
  table { width:100%; border-collapse:collapse; font-size:14px; }
  th,td { text-align:left; padding:10px 32px; border-bottom:1px solid #eee; }
  th { background:#fafafa; color:#555; font-size:12px; text-transform:uppercase; }
  .amt { text-align:right; font-weight:700; color:#c0392b; white-space:nowrap; }
  .foot { padding:18px 32px; color:#999; font-size:12px; text-align:center; }
</style>
"""


def fetch_findings(sb):
    return (sb.table("leakage_findings")
              .select("*")
              .order("estimated_loss_usd", desc=True)
              .execute().data)


def customer_names(sb):
    rows = sb.table("contracts").select("customer_id, customer_name").execute().data
    return {r["customer_id"]: r["customer_name"] for r in rows}


def render_html(summary_text, findings, names):
    total = sum(float(f["estimated_loss_usd"]) for f in findings)
    by_type = {}
    for f in findings:
        by_type.setdefault(f["finding_type"], 0)
        by_type[f["finding_type"]] += float(f["estimated_loss_usd"])

    cards = ""
    for t, label in TYPE_LABELS.items():
        cards += (f"<div class='card'><div class='n'>${by_type.get(t,0):,.0f}</div>"
                  f"<div class='t'>{label}</div></div>")

    rows = ""
    for f in findings:
        name = names.get(f["customer_id"], f["customer_id"])
        label = TYPE_LABELS.get(f["finding_type"], f["finding_type"])
        note = (f.get("evidence") or {}).get("note", "")
        rows += (f"<tr><td>{name}</td><td>{label}</td>"
                 f"<td class='amt'>${float(f['estimated_loss_usd']):,.2f}</td>"
                 f"<td>{note}</td></tr>")

    summary_html = summary_text.replace("\n", "<br>")
    stamp = datetime.now().strftime("%B %d, %Y at %H:%M")

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{STYLE}</head>
<body><div class="wrap">
  <div class="head">
    <h1>Revenue Leakage Report</h1>
    <p>Generated {stamp} &middot; {len(findings)} findings</p>
  </div>
  <div class="kpi">
    <div class="big">${total:,.0f}</div>
    <div class="lbl">Total Estimated Annual Leakage</div>
  </div>
  <div class="cards">{cards}</div>
  <div class="summary">
    <h2>Executive Summary</h2>
    <p>{summary_html}</p>
  </div>
  <table>
    <tr><th>Customer</th><th>Issue</th><th>Est. Loss</th><th>Detail</th></tr>
    {rows}
  </table>
  <div class="foot">Generated automatically by the Revenue Leakage Detection Agent</div>
</div></body></html>"""


def generate(email=False):
    sb = get_client()
    findings = fetch_findings(sb)
    names = customer_names(sb)

    if not findings:
        print("No findings to report. Run run_scan.py first.")
        return None

    # Build a compact payload for the LLM.
    payload = [{
        "customer": names.get(f["customer_id"], f["customer_id"]),
        "type": TYPE_LABELS.get(f["finding_type"], f["finding_type"]),
        "estimated_annual_loss_usd": float(f["estimated_loss_usd"]),
        "detail": (f.get("evidence") or {}).get("note", ""),
    } for f in findings]

    print("Asking the LLM to write the executive summary...")
    summary = llm_client.chat(
        SUMMARY_PROMPT.format(findings=json.dumps(payload, indent=2)),
        temperature=0.3,
    )

    html = render_html(summary, findings, names)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    fname = datetime.now().strftime("report_%Y%m%d_%H%M%S.html")
    path = os.path.join(REPORTS_DIR, fname)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    # Stable filename the dashboard can always link to.
    with open(os.path.join(REPORTS_DIR, "latest.html"), "w", encoding="utf-8") as fh:
        fh.write(html)

    total = sum(float(f["estimated_loss_usd"]) for f in findings)
    print(f"\nReport saved to {path}")
    print(f"Total leakage: ${total:,.2f} across {len(findings)} findings")
    print("\n--- EXECUTIVE SUMMARY ---\n")
    print(summary)

    if email:
        from mailer import send_html_email
        subject = f"Revenue Leakage Report - ${total:,.0f} detected"
        send_html_email(subject, html)

    return {"path": path, "html": html, "summary": summary, "total": total}


if __name__ == "__main__":
    import sys
    generate(email=("--email" in sys.argv))
