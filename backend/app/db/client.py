"""Supabase client for the service layer. Never imported by the engine (invariant 1).

The service-role key bypasses RLS, so it stays on the backend and is read only here.
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client

# .env sits at the repo root, two levels above backend/app/db.
_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


class MissingConfigError(RuntimeError):
    pass


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingConfigError(f"{name} is not set (see .env)")
    return value


@lru_cache(maxsize=1)
def get_client() -> Client:
    load_dotenv(_ENV_PATH)
    return create_client(_require("SUPABASE_URL"), _require("SUPABASE_SERVICE_ROLE_KEY"))
