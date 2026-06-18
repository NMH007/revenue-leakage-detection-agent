"""
Central configuration.

Every other file imports its settings from here instead of reading the
environment directly. That way there's ONE place that knows about secrets.
`load_dotenv()` reads your .env file and loads each KEY=value into the
process environment so os.getenv() can see them.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()  # pull values from .env into the environment

# Windows consoles default to cp1252, which crashes when we print characters
# the LLM sometimes returns (e.g. curly quotes, non-breaking hyphens). Force
# UTF-8 so every script in this project can print freely.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# --- LLM (Cerebras) ---
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")
CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"

# --- Database (Supabase) ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# --- Billing (Stripe) ---
STRIPE_TEST_KEY = os.getenv("STRIPE_TEST_KEY")

# --- Email alerts ---
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
ALERT_RECIPIENT = os.getenv("ALERT_RECIPIENT")

# --- Dashboard ---
DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY")
