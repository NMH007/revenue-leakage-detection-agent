"""
Generate realistic mock data for a ~$1M/year SaaS business and load it into
Supabase. We deliberately bake in 'leaks' so each agent has something to find:

  contract_gap    -> 3 customers billed LESS than their contract every month
  billing_anomaly -> 1 customer with a sudden spend drop, 1 with a missing invoice
  tier_mismatch   -> 2 customers using far more than their plan allows

Run:  python seed_data.py
Re-running is safe: it wipes the 3 source tables first, then reloads.
"""
from database import get_client

# (id,   name,                fee,   units, overage, end_date,     terms)
CUSTOMERS = [
    ("C001", "Acme Corp",          4000, 1000, 1.50, "2026-12-31", "Net 30"),
    ("C002", "Globex Inc",         2500, 2000, 0.80, "2027-03-31", "Net 30"),
    ("C003", "Initech LLC",        8000, 5000, 1.00, "2026-09-30", "Net 45"),
    ("C004", "Umbrella Co",        1200,  500, 2.00, "2027-01-31", "Net 15"),
    ("C005", "Stark Industries",  12000,10000, 0.50, "2026-11-30", "Net 60"),
    ("C006", "Wayne Enterprises",  6500, 4000, 1.20, "2027-06-30", "Net 30"),
    ("C007", "Soylent Corp",       3000, 1500, 1.00, "2026-10-31", "Net 30"),
    ("C008", "Hooli",              9500, 8000, 0.75, "2027-02-28", "Net 45"),
    ("C009", "Pied Piper",         1800,  800, 1.50, "2026-12-31", "Net 30"),
    ("C010", "Wonka Industries",   5000, 3000, 1.00, "2027-04-30", "Net 30"),
    ("C011", "Cyberdyne Systems",  7200, 6000, 0.90, "2026-08-31", "Net 30"),
    ("C012", "Tyrell Corp",        2200, 1000, 1.80, "2027-05-31", "Net 30"),
]

# The LLM (Agent 1) will read this prose to extract the real terms.
CONTRACT_TEMPLATE = (
    "MASTER SERVICES AGREEMENT\n\n"
    "This agreement is entered into between RevCloud Inc. ('Provider') and "
    "{name} ('Client').\n\n"
    "1. FEES. The Client shall pay a recurring monthly subscription fee of "
    "${fee:,.2f}.\n"
    "2. INCLUDED USAGE. The subscription includes {units:,} units per monthly "
    "billing period.\n"
    "3. OVERAGE. Usage in excess of the included units is billed at "
    "${overage:.2f} per additional unit.\n"
    "4. TERM. This agreement remains in effect through {end_date}.\n"
    "5. PAYMENT TERMS. All invoices are due {terms} from the invoice date.\n"
)

MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]

# --- Planted leaks --------------------------------------------------------
UNDERBILLED = {"C001": 3400, "C008": 9000, "C011": 6800}  # flat low bill, every month
DROP        = {"C010": ("2026-06", 3000)}                 # last month spend collapses
MISSING     = {"C007": "2026-06"}                         # last month invoice absent

# Usage in the latest period vs each plan's included units.
# C009 (limit 800) and C012 (limit 1000) blow past their plans.
USAGE_LATEST = {
    "C001": 850, "C002": 1500, "C003": 4200, "C004": 480,
    "C005": 9000, "C006": 3500, "C007": 1400, "C008": 7500,
    "C009": 1400, "C010": 2800, "C011": 5500, "C012": 1600,
}


def wipe(sb):
    """Delete all rows from the source tables so re-runs start clean."""
    for table in ["contracts", "invoices", "usage_records"]:
        sb.table(table).delete().gte("id", 0).execute()
    print("Cleared old contracts / invoices / usage_records.")


def build_contracts():
    rows = []
    for cid, name, fee, units, overage, end_date, terms in CUSTOMERS:
        text = CONTRACT_TEMPLATE.format(
            name=name, fee=fee, units=units, overage=overage,
            end_date=end_date, terms=terms,
        )
        rows.append({
            "customer_id": cid,
            "customer_name": name,
            "contract_text": text,
            "extracted_terms": None,   # Agent 1 (LLM) fills this in later
        })
    return rows


def build_invoices():
    rows = []
    for cid, name, fee, *_ in CUSTOMERS:
        for m in MONTHS:
            if cid in MISSING and MISSING[cid] == m:
                continue                      # invoice never generated
            amount = fee
            if cid in UNDERBILLED:
                amount = UNDERBILLED[cid]     # chronically under-billed
            if cid in DROP and DROP[cid][0] == m:
                amount = DROP[cid][1]         # sudden drop
            rows.append({
                "customer_id": cid,
                "amount": amount,
                "billing_period": m,
                "status": "paid",
            })
    return rows


def build_usage():
    rows = []
    for cid, used in USAGE_LATEST.items():
        rows.append({
            "customer_id": cid,
            "feature_name": "api_calls",
            "usage_count": used,
            "billing_period": "2026-06",
        })
    return rows


def main():
    sb = get_client()
    wipe(sb)

    contracts = build_contracts()
    invoices = build_invoices()
    usage = build_usage()

    sb.table("contracts").insert(contracts).execute()
    sb.table("invoices").insert(invoices).execute()
    sb.table("usage_records").insert(usage).execute()

    print(f"Inserted {len(contracts)} contracts")
    print(f"Inserted {len(invoices)} invoices (across {len(MONTHS)} months)")
    print(f"Inserted {len(usage)} usage records")
    print("\nDone. Source data is loaded and ready for the agents.")


if __name__ == "__main__":
    main()
