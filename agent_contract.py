"""
Agent 1 - Contract Auditor.

Reads each contract, asks the LLM to pull structured terms out of the prose,
saves those terms back to Supabase, then compares the contracted monthly fee
against the customer's most recent invoice. Any shortfall above $10 becomes a
'contract_gap' finding (annualized, since being under-billed repeats monthly).

Run:  python agent_contract.py
"""
from collections import Counter

from database import get_client
import llm_client

GAP_THRESHOLD = 10  # ignore rounding-level differences

EXTRACT_PROMPT = (
    "You are a contracts analyst. Read the contract below and extract its "
    "terms. Respond with ONLY a JSON object, no commentary, using exactly "
    "these keys:\n"
    '  "monthly_fee": number,\n'
    '  "included_units": number,\n'
    '  "overage_rate": number,\n'
    '  "contract_end_date": "YYYY-MM-DD",\n'
    '  "payment_terms": string\n\n'
    "Contract:\n{contract}"
)


def typical_invoice_by_customer(sb):
    """Return {customer_id: amount} using each customer's MOST COMMON invoice
    amount -- their standard recurring charge. We compare the contract to this
    'normal' price, not the single latest invoice, so a one-off dip (which is
    the Billing agent's job) can't masquerade as a contract gap."""
    invoices = sb.table("invoices").select("*").execute().data
    by_customer = {}
    for inv in invoices:
        by_customer.setdefault(inv["customer_id"], []).append(float(inv["amount"]))
    typical = {}
    for cid, amounts in by_customer.items():
        typical[cid] = Counter(amounts).most_common(1)[0][0]
    return typical


def run():
    sb = get_client()

    # Idempotent: clear previous contract_gap findings so re-runs don't pile up.
    sb.table("leakage_findings").delete().eq("finding_type", "contract_gap").execute()

    contracts = sb.table("contracts").select("*").execute().data
    typical = typical_invoice_by_customer(sb)

    findings = []
    for c in contracts:
        cid = c["customer_id"]
        print(f"\nAuditing {cid} ({c.get('customer_name')})...")

        # 1. LLM reads the contract prose into structured terms (cache the result).
        terms = c.get("extracted_terms")
        if not terms:
            terms = llm_client.extract_json(
                EXTRACT_PROMPT.format(contract=c["contract_text"][:3000])
            )
            sb.table("contracts").update({"extracted_terms": terms}).eq(
                "id", c["id"]
            ).execute()
            print(f"  LLM extracted: {terms}")

        # 2. Compare contracted fee vs what we actually billed.
        contracted = float(terms.get("monthly_fee", 0) or 0)
        billed = typical.get(cid, 0)
        gap = contracted - billed
        print(f"  contracted ${contracted:,.2f} vs billed ${billed:,.2f} "
              f"-> gap ${gap:,.2f}")

        # 3. Record a finding if we're under-charging.
        if gap > GAP_THRESHOLD:
            annual = round(gap * 12, 2)
            findings.append({
                "finding_type": "contract_gap",
                "customer_id": cid,
                "estimated_loss_usd": annual,
                "evidence": {
                    "contracted_monthly": contracted,
                    "billed_monthly": billed,
                    "monthly_gap": round(gap, 2),
                    "annualized": annual,
                    "note": "Billed below contracted rate",
                },
            })

    if findings:
        sb.table("leakage_findings").insert(findings).execute()

    total = sum(f["estimated_loss_usd"] for f in findings)
    print(f"\nContract Auditor done: {len(findings)} gap(s), "
          f"${total:,.2f} annual leakage.")
    return findings


if __name__ == "__main__":
    run()
