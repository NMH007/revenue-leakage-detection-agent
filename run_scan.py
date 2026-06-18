"""
Orchestrator: run all detection agents in sequence and summarize the results.
This is the single 'scan' that the Flask API endpoint and n8n will trigger.

Run:  python run_scan.py
"""
import agent_contract
import agent_billing
import agent_tier


def run_all():
    print("=" * 60)
    print("REVENUE LEAKAGE SCAN")
    print("=" * 60)

    print("\n--- Agent 1: Contract Auditor ---")
    contract = agent_contract.run()

    print("\n--- Agent 2: Billing Anomaly Detector ---")
    billing = agent_billing.run()

    print("\n--- Agent 3: Subscription Tier Analyzer ---")
    tier = agent_tier.run()

    all_findings = contract + billing + tier
    total = sum(f["estimated_loss_usd"] for f in all_findings)

    print("\n" + "=" * 60)
    print(f"SCAN COMPLETE: {len(all_findings)} findings, "
          f"${total:,.2f} total estimated leakage")
    print("=" * 60)

    return {
        "count": len(all_findings),
        "total_usd": round(total, 2),
        "by_type": {
            "contract_gap": sum(f["estimated_loss_usd"] for f in contract),
            "billing_anomaly": sum(f["estimated_loss_usd"] for f in billing),
            "tier_mismatch": sum(f["estimated_loss_usd"] for f in tier),
        },
        "findings": all_findings,
    }


if __name__ == "__main__":
    run_all()
