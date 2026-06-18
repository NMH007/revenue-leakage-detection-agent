"""
A single helper that hands back a connected Supabase client.

`create_client(url, key)` builds an object that talks to your database over
HTTPS. We reuse this everywhere so we never repeat the connection code.
"""
from supabase import create_client, Client
import config


def get_client() -> Client:
    if not config.SUPABASE_URL or not config.SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_KEY are missing. Check your .env file."
        )
    return create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
