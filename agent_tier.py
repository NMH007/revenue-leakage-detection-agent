"""
Agent 3 - Subscription Tier Analyzer.   (pure math, no LLM)

Compares each customer's actual usage against the plan limits the LLM already
pulled from their contract (contracts.extracted_terms). If a customer uses more
than their included units but is never charged overage, that's recoverable
upsell revenue:

    overage_units         = actual_usage - included_units
    monthly_overage_value = overage_units * overage_rate
    annual_estimate       = monthly_overage_value * 12

Note how this agent REUSES Agent 1's LLM extraction instead of calling the LLM
again -- structured data, once extracted, is shared across the system.

Run:  python agent_tier.py
"""
from database import get_client

OVERAGE_TRIGGER = 1.10  # only flag if usage exceeds the limit by more than 10%


def run():
    sb = get_client()
    # Idempotent: clear previous tier findings first.
    sb.table("leakage_findings").delete().eq("finding_type", "tier_mismatch").execute()

    contracts = sb.table("contracts").select("*").execute().data
    usage_rows = sb.table("usage_records").select("*").execute().data

    # Plan limits per customer, taken from the LLM-extracted contract terms.
    plan = {}
    for c in contracts:
        terms = c.get("extracted_terms") or {}
        plan[c["customer_id"]] = {
            "included_units": float(terms.get("included_units", 0) or 0),
            "overage_rate": float(terms.get("overage_rate", 0) or 0),
            "name": c.get("customer_name"),
        }

    # Total usage per customer in the latest period.
    usage = {}
    for u in usage_rows:
        cid = u["customer_id"]
        usage[cid] = usage.get(cid, 0) + float(u["usage_count"])

    findings = []
    for cid, used in usage.items():
        p = plan.get(cid)
        if not p or p["included_units"] <= 0:
            continue
        limit = p["included_units"]
        if used > limit * OVERAGE_TRIGGER:
            overage_units = used - limit
            monthly_value = overage_units * p["overage_rate"]
            annual = round(monthly_value * 12, 2)
            ratio = used / limit
            findings.append({
                "finding_type": "tier_mismatch",
                "customer_id": cid,
                "estimated_loss_usd": annual,
                "evidence": {
                    "included_units": limit,
                    "actual_usage": used,
                    "usage_ratio": round(ratio, 2),
                    "overage_units": overage_units,
                    "overage_rate": p["overage_rate"],
                    "monthly_overage_value": round(monthly_value, 2),
                    "annualized": annual,
                    "note": f"Using {ratio:.1f}x plan limit, never upsold",
                },
            })
            print(f"{cid} ({p['name']}): {used:.0f} used vs {limit:.0f} limit "
                  f"({ratio:.1f}x) -> ${annual:,.2f}/yr")

    if findings:
        sb.table("leakage_findings").insert(findings).execute()

    total = sum(f["estimated_loss_usd"] for f in findings)
    print(f"\nTier Analyzer done: {len(findings)} mismatch(es), "
          f"${total:,.2f} annual.")
    return findings


if __name__ == "__main__":
    run()
