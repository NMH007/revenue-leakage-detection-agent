"""
Agent 2 - Billing Anomaly Detector.   (pure math, no LLM)

Scans each customer's invoice history and flags two problems:
  DROP:    latest month is >20% below the average of the prior 3 months
  MISSING: customer was billed in earlier months but has NO invoice this month

DATA SOURCE: the 'invoices' table. In a production deployment you would point
this at Stripe instead (stripe.Invoice.list(customer=...)) and build the same
{period: amount} history -- the anomaly math below does not change at all.

Run:  python agent_billing.py
"""
from database import get_client

DROP_THRESHOLD = 0.20  # 20% below the recent average counts as a drop


def load_history(sb):
    """Return {customer_id: {billing_period: amount}} and the sorted period list."""
    invoices = (
        sb.table("invoices").select("*").order("billing_period").execute().data
    )
    history, periods = {}, set()
    for inv in invoices:
        cid = inv["customer_id"]
        history.setdefault(cid, {})[inv["billing_period"]] = float(inv["amount"])
        periods.add(inv["billing_period"])
    return history, sorted(periods)


def run():
    sb = get_client()
    # Idempotent: clear previous billing findings first.
    sb.table("leakage_findings").delete().eq("finding_type", "billing_anomaly").execute()

    history, all_periods = load_history(sb)
    latest_period = all_periods[-1]
    prior3 = all_periods[-4:-1]  # the 3 months immediately before the latest

    findings = []
    for cid, by_period in history.items():
        prior_amounts = [by_period[p] for p in prior3 if p in by_period]
        if not prior_amounts:
            continue  # not enough history to judge
        avg_prior = sum(prior_amounts) / len(prior_amounts)

        # --- MISSING invoice -------------------------------------------------
        if latest_period not in by_period:
            findings.append({
                "finding_type": "billing_anomaly",
                "customer_id": cid,
                "estimated_loss_usd": round(avg_prior, 2),
                "evidence": {
                    "anomaly": "missing_invoice",
                    "missing_period": latest_period,
                    "expected_amount": round(avg_prior, 2),
                    "note": f"No invoice generated for {latest_period}",
                },
            })
            print(f"{cid}: MISSING {latest_period} (expected ~${avg_prior:,.2f})")
            continue

        # --- DROP in spend ---------------------------------------------------
        current = by_period[latest_period]
        if current < avg_prior * (1 - DROP_THRESHOLD):
            drop = avg_prior - current
            pct = drop / avg_prior * 100
            findings.append({
                "finding_type": "billing_anomaly",
                "customer_id": cid,
                "estimated_loss_usd": round(drop, 2),
                "evidence": {
                    "anomaly": "spend_drop",
                    "period": latest_period,
                    "current": current,
                    "avg_prior_3mo": round(avg_prior, 2),
                    "drop_pct": round(pct, 1),
                    "note": f"Spend fell {pct:.0f}% vs prior 3-month average",
                },
            })
            print(f"{cid}: DROP {pct:.0f}% in {latest_period} "
                  f"(${current:,.2f} vs avg ${avg_prior:,.2f})")

    if findings:
        sb.table("leakage_findings").insert(findings).execute()

    total = sum(f["estimated_loss_usd"] for f in findings)
    print(f"\nBilling Anomaly Detector done: {len(findings)} anomaly(ies), "
          f"${total:,.2f}.")
    return findings


if __name__ == "__main__":
    run()
