"""
Day 2 sanity check: can Python reach the Supabase database, and do all
4 tables exist? Run this before doing anything else.

    python test_connection.py
"""
import config
from database import get_client


def main():
    print("1) Checking .env values are present...")
    assert config.SUPABASE_URL, "SUPABASE_URL is empty in .env"
    assert config.SUPABASE_KEY, "SUPABASE_KEY is empty in .env"
    print(f"   URL = {config.SUPABASE_URL}")
    print(f"   KEY = {config.SUPABASE_KEY[:10]}... (rest hidden)")

    print("\n2) Connecting to Supabase...")
    sb = get_client()
    print("   Client created.")

    print("\n3) Verifying each table is reachable...")
    for table in ["contracts", "invoices", "usage_records", "leakage_findings"]:
        res = sb.table(table).select("*", count="exact").limit(1).execute()
        print(f"   - {table:<18} OK  (rows: {res.count})")

    print("\nSUCCESS - database is live and all 4 tables exist.")


if __name__ == "__main__":
    main()
