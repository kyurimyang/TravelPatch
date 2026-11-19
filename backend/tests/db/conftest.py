"""Fixtures for tests against the dev Supabase project (decision 2026-11-19).

Run with `pytest -m db`. They need SUPABASE_URL, SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY
in the repo-root .env, and refuse to run when that URL is the one in .env.prod: tests create and
delete users, which must never happen on the production project.
"""

import os
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from dotenv import dotenv_values, load_dotenv
from supabase import Client, create_client

ROOT = Path(__file__).resolve().parents[3]
TEST_PLACE_PREFIX = "test-place:"  # place ids the tests insert; removed afterwards
PASSWORD = "test-Password-1234"


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"{name} is not set (see .env)")
    return value


@pytest.fixture(scope="session")
def supabase_url() -> str:
    load_dotenv(ROOT / ".env")
    url = _env("SUPABASE_URL")
    prod = (dotenv_values(ROOT / ".env.prod").get("SUPABASE_URL") or "").strip()
    if prod and prod == url:
        pytest.exit(".env points at the production project; db tests run on dev only", 2)
    return url


@pytest.fixture(scope="session")
def admin(supabase_url: str) -> Iterator[Client]:
    """Service-role client: bypasses RLS. Used only to set up and clean up."""
    client = create_client(supabase_url, _env("SUPABASE_SERVICE_ROLE_KEY"))
    yield client
    client.table("places").delete().like("place_id", f"{TEST_PLACE_PREFIX}%").execute()


@pytest.fixture
def anon(supabase_url: str) -> Client:
    """A visitor who is not signed in."""
    return create_client(supabase_url, _env("SUPABASE_ANON_KEY"))


@pytest.fixture
def make_user(supabase_url: str, admin: Client) -> Iterator[Callable[[], tuple[str, Client]]]:
    """Factory: a new confirmed user and a client signed in as them. Each test gets fresh users;
    deleting a user afterwards cascades to their trips, profiles and consents."""
    created: list[str] = []

    def make() -> tuple[str, Client]:
        email = f"test-{uuid.uuid4().hex[:12]}@example.com"
        user = admin.auth.admin.create_user(
            {"email": email, "password": PASSWORD, "email_confirm": True}
        ).user
        created.append(user.id)
        client = create_client(supabase_url, _env("SUPABASE_ANON_KEY"))
        client.auth.sign_in_with_password({"email": email, "password": PASSWORD})
        return user.id, client

    yield make
    for user_id in created:
        admin.auth.admin.delete_user(user_id)
